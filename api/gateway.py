"""Razorpay sandbox webhook verification and event classification.

Pure standard-library functions: no I/O, no logging, no secrets retained.
The webhook endpoint operates on the exact raw request body; signature
verification is HMAC-SHA256 with constant-time comparison and fails closed
when the secret, signature, or provider event ID is missing.

Order linkage contract (corrected): the provider-side order reference
(`payload.payment.entity.order_id`, mirroring Razorpay's documented Orders
API linkage — NOT VERIFIED against a live Razorpay account) is the only
value used to resolve a Zippy order, and only through the authoritative,
server-controlled mapping recorded in `zippy.external_references` /
`zippy.payment_intents` (see `FinanceRepository.prepare_payment_intent`).
`notes.zippy_order_id` is parsed and preserved for evidence/diagnostics only
and is never used to establish or authorize a payment-to-order link, even
when the webhook signature is valid.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# Selected safe integer/database range for Razorpay minor-unit amounts: keeps
# every accepted value comfortably inside PostgreSQL bigint, IEEE-754/JS
# safe-integer (2**53 - 1), and the existing numeric(18,2) storage columns.
MAX_AMOUNT_MINOR_UNITS = 999_999_999_999


class MalformedEventError(Exception):
    """Raised when the webhook body cannot be parsed into a usable event."""


@dataclass(frozen=True)
class GatewayEvent:
    provider: str
    provider_event_id: str
    event_type: str
    provider_reference_id: str | None
    payment_id: str | None
    refund_id: str | None
    amount_minor_units: int | None
    currency: str | None
    notes: dict[str, Any]
    evidence_hash: str


# Approved D-26 mapping: only compatible operational projections.
EVENT_PROJECTION_STATUS: dict[str, str] = {
    "payment.authorized": "pending",
    "payment.captured": "evidence_verified",
    "payment.failed": "failed",
}
RECONCILE_ONLY_EVENTS = frozenset({"refund.processed"})
SUPPORTED_EVENTS = frozenset(EVENT_PROJECTION_STATUS) | RECONCILE_ONLY_EVENTS


def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Constant-time HMAC-SHA256 check. Fails closed on missing inputs."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _minor_units(value: Any) -> int | None:
    """Strictly validate a Razorpay-style integer minor-unit amount.

    Rejects booleans (`bool` is an `int` subclass in Python), floats,
    strings, negative or zero values, and values outside the selected safe
    range. Performs no implicit rupee-to-paise conversion.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0 or value > MAX_AMOUNT_MINOR_UNITS:
        return None
    return value


def minor_units_to_major(amount_minor_units: int) -> Decimal:
    """Exact minor-to-major currency conversion for storage (Decimal only).

    100 minor units == 1.00 major unit for INR. Division by 100 with a
    fixed two-decimal quantize is exact for every value accepted by
    `_minor_units`; no binary floating-point arithmetic is used.
    """
    return (Decimal(amount_minor_units) / Decimal(100)).quantize(Decimal("0.01"))


def major_units_to_minor(amount_major_units: Decimal) -> int:
    """Exact major-to-minor conversion used for reconciliation comparisons."""
    return int((amount_major_units * 100).to_integral_exact())


def parse_event(raw_body: bytes) -> GatewayEvent:
    """Parse and shape a Razorpay sandbox webhook body.

    `payload.payment.entity.order_id` (the provider order reference) is
    extracted for authoritative mapping lookup; `notes` is preserved
    unmodified as untrusted evidence only. Events without a usable provider
    reference or monetary data parse successfully but resolve to no
    projection in the persistence layer.
    """
    try:
        document = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MalformedEventError("body is not valid JSON") from exc
    if not isinstance(document, dict):
        raise MalformedEventError("body is not a JSON object")

    provider_event_id = document.get("id")
    if not isinstance(provider_event_id, str) or not provider_event_id:
        raise MalformedEventError("missing provider event id")
    event_type = document.get("event")
    if not isinstance(event_type, str) or not event_type:
        raise MalformedEventError("missing event type")

    payload_raw = document.get("payload")
    payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}
    entity: dict[str, Any] = {}
    payment_id: str | None = None
    refund_id: str | None = None
    provider_reference_id: str | None = None
    if event_type.startswith("refund."):
        refund = payload.get("refund")
        refund_entity = refund.get("entity") if isinstance(refund, dict) else {}
        entity = refund_entity if isinstance(refund_entity, dict) else {}
        refund_id = entity.get("id") if isinstance(entity.get("id"), str) else None
    else:
        payment = payload.get("payment")
        payment_entity = payment.get("entity") if isinstance(payment, dict) else {}
        entity = payment_entity if isinstance(payment_entity, dict) else {}
        payment_id = entity.get("id") if isinstance(entity.get("id"), str) else None
        order_id_field = entity.get("order_id")
        provider_reference_id = order_id_field if isinstance(order_id_field, str) else None

    notes = entity.get("notes")
    notes = notes if isinstance(notes, dict) else {}
    currency = entity.get("currency")
    return GatewayEvent(
        provider="razorpay",
        provider_event_id=provider_event_id,
        event_type=event_type,
        provider_reference_id=provider_reference_id,
        payment_id=payment_id,
        refund_id=refund_id,
        amount_minor_units=_minor_units(entity.get("amount")),
        currency=currency if isinstance(currency, str) else None,
        notes=notes,
        evidence_hash=payload_hash(raw_body),
    )
