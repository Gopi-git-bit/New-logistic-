"""M6-A telemetry redaction — fail-closed at the telemetry boundary.

If an event cannot be proven safe, the telemetry event is dropped while
the underlying business operation continues normally. Redaction runs
BEFORE any export call.

D-31: redaction must fail closed; telemetry export must fail open.
"""

from __future__ import annotations

import re
from typing import Any

from .telemetry_contract import (
    FieldClassification,
    classify_field,
)

HIGH_ENTROPY_SECRET = re.compile(r"^(pk_|sk_|rk_|rzp_|whsec_|eyJ|AIza|ghp_|glpat-|xox[bpasr]-)")

UUID_LIKE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


class RedactionResult:
    __slots__ = ("accepted", "event", "dropped_fields", "reason")

    def __init__(
        self,
        accepted: bool,
        event: dict[str, Any] | None,
        dropped_fields: list[str] | None = None,
        reason: str | None = None,
    ) -> None:
        self.accepted = accepted
        self.event = event
        self.dropped_fields = dropped_fields or []
        self.reason = reason


def _looks_like_secret(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) < 8:
        return False
    if HIGH_ENTROPY_SECRET.match(value):
        return True
    if "@" in value and "." in value.split("@")[-1]:
        return True
    if "/" in value and "." in value and len(value) > 30:
        return True
    return False


def _classify_value(key: str, value: Any) -> FieldClassification:
    field_cls = classify_field(key)
    if field_cls == FieldClassification.PROHIBITED:
        return FieldClassification.PROHIBITED
    if isinstance(value, str) and _looks_like_secret(value):
        return FieldClassification.PROHIBITED
    if isinstance(value, (dict, list)):
        return FieldClassification.RESTRICTED
    return field_cls


def redact_event(event: dict[str, Any]) -> RedactionResult:
    """Redact a telemetry event. Fail-closed: if any field cannot be classified
    as safe, the entire event is dropped.

    Returns RedactionResult with accepted=False when the event must be dropped.
    The business operation that triggered this event is unaffected.
    """
    if not isinstance(event, dict):
        return RedactionResult(False, None, reason="event_not_dict")

    cleaned: dict[str, Any] = {}
    dropped: list[str] = []
    unclassifiable: list[str] = []

    for key, value in event.items():
        cls = _classify_value(key, value)

        if cls == FieldClassification.PERMITTED:
            cleaned[key] = _redact_value(value)
        elif cls == FieldClassification.RESTRICTED:
            if isinstance(value, str) and not UUID_LIKE.match(value):
                unclassifiable.append(key)
            else:
                cleaned[key] = _redact_value(value)
        else:
            dropped.append(key)

    if unclassifiable:
        return RedactionResult(
            False,
            None,
            dropped_fields=dropped + unclassifiable,
            reason=f"unclassifiable_fields:{','.join(sorted(unclassifiable))}",
        )

    if dropped:
        return RedactionResult(
            False, None, dropped_fields=dropped, reason="prohibited_fields_present"
        )

    return RedactionResult(True, cleaned, dropped_fields=dropped)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        if _looks_like_secret(value):
            return "[REDACTED]"
        return value
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def scrub_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Scrub a metadata dict for safe inclusion in a span. Drops any key
    classified as PROHIBITED; replaces RESTRICTED string values that don't
    look like UUIDs with [REDACTED].
    """
    if not metadata:
        return {}
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        cls = _classify_value(key, value)
        if cls == FieldClassification.PROHIBITED:
            continue
        if cls == FieldClassification.RESTRICTED:
            if isinstance(value, str) and not UUID_LIKE.match(value):
                continue
        out[key] = _redact_value(value)
    return out
