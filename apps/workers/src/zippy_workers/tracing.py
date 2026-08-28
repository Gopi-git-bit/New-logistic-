"""§16 observability: Langfuse ingestion with offline-safe no-op fallback.

Trace root = heartbeat_id (per correlation contract). Spans are fire-and-
forget; tracing must never fail task execution.
"""

from __future__ import annotations

import base64
import contextlib
import uuid
from typing import Any

import httpx


class Tracer:
    """Minimal Langfuse span emitter; no-op when keys are absent."""

    def __init__(self, public_key: str | None, secret_key: str | None,
                 host: str = "https://us.cloud.langfuse.com",
                 trace_id: str | None = None) -> None:
        self.enabled = bool(public_key and secret_key)
        self.host = host.rstrip("/")
        self.trace_id = trace_id or str(uuid.uuid4())
        self._auth = None
        if self.enabled:
            raw = f"{public_key}:{secret_key}".encode()
            self._auth = "Basic " + base64.b64encode(raw).decode()

    @contextlib.contextmanager
    def span(self, name: str, metadata: dict[str, Any] | None = None,
             parent_id: str | None = None):
        sid = str(uuid.uuid4())
        try:
            yield sid
        finally:
            if self.enabled:
                payload = {
                    "id": sid,
                    "traceId": self.trace_id,
                    "name": name,
                    "startTime": _now_iso(),
                    "endTime": _now_iso(),
                    "type": "span",
                    "metadata": metadata or {},
                }
                if parent_id:
                    payload["parentObservationId"] = parent_id
                try:
                    httpx.post(
                        f"{self.host}/api/public/ingestion",
                        json={"batch": [{"type": "span-create", "body": payload}]},
                        headers={"Authorization": self._auth},  # type: ignore[arg-type]
                        timeout=3.0,
                    )
                except Exception:  # noqa: BLE001 - observability is best-effort
                    pass


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.UTC).isoformat()


def heartbeat_trace(settings) -> Tracer:
    return Tracer(settings.langfuse_public_key, settings.langfuse_secret_key,
                  settings.langfuse_host)
