"""M6-A tenant/actor pseudonymization — HMAC-SHA256 with server-side pepper.

Client-provided identifiers may NOT establish telemetry identity or authority.
Tenant, actor, workflow, and correlation identifiers must be generated or
resolved by trusted server logic. Any identifiers used in tests must be
synthetic and pseudonymized.

D-31: server-generated stable hash; never export raw tenant UUID/name.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid


def generate_pepper() -> str:
    return secrets.token_hex(32)


def pseudonymize(raw_id: str, pepper: str, domain: str = "tenant") -> str:
    if not raw_id or not pepper:
        return ""
    msg = f"{domain}:{raw_id}".encode()
    key = pepper.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:24]


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def generate_span_id() -> str:
    return uuid.uuid4().hex[:16]


def generate_correlation_id() -> str:
    return str(uuid.uuid4())
