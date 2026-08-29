"""Pluggable multi-channel notification sender.

Providers are stubs by default; swap in real SDKs (Twilio, Resend, Firebase)
when production credentials land. The handler never talks to providers directly —
it calls through this port.

Usage:
    sender = make_notification_sender("stub")
    result = sender.send("sms", "+919000000000", "Hello", "Zippy")
    print(result.ok, result.external_id)
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    provider: str
    external_id: str | None = None
    error: str | None = None


@runtime_checkable
class NotificationSender(Protocol):
    """Protocol every channel provider must satisfy."""

    @property
    def provider_name(self) -> str: ...

    def send(
        self, destination: str, title: str, body: str, payload: dict | None = None
    ) -> DeliveryResult: ...


class StubSender:
    """No-op provider for dev/test — always succeeds."""

    @property
    def provider_name(self) -> str:
        return "stub"

    def send(
        self, destination: str, title: str, body: str, payload: dict | None = None
    ) -> DeliveryResult:
        return DeliveryResult(ok=True, provider="stub", external_id=f"stub_{uuid.uuid4().hex[:8]}")


class TwilioSMSSender:
    """Stub for Twilio SMS (replace with real SDK when credentials land)."""

    def __init__(self, account_sid: str = "", auth_token: str = "", from_number: str = ""):
        self._sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self._token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from = from_number or os.getenv("TWILIO_FROM_NUMBER", "")

    @property
    def provider_name(self) -> str:
        return "twilio_sms"

    def send(
        self, destination: str, title: str, body: str, payload: dict | None = None
    ) -> DeliveryResult:
        if not self._sid or not self._token:
            return DeliveryResult(
                ok=False, provider="twilio_sms", error="twilio credentials not configured"
            )
        # TODO: replace with real twilio SDK call
        return DeliveryResult(
            ok=True, provider="twilio_sms", external_id=f"tw_{uuid.uuid4().hex[:8]}"
        )


class ResendEmailSender:
    """Stub for Resend email (replace with real SDK when credentials land)."""

    def __init__(self, api_key: str = "", from_email: str = ""):
        self._key = api_key or os.getenv("RESEND_API_KEY", "")
        self._from = from_email or os.getenv("RESEND_FROM_EMAIL", "noreply@zippy.local")

    @property
    def provider_name(self) -> str:
        return "resend_email"

    def send(
        self, destination: str, title: str, body: str, payload: dict | None = None
    ) -> DeliveryResult:
        if not self._key:
            return DeliveryResult(
                ok=False, provider="resend_email", error="resend api key not configured"
            )
        # TODO: replace with real resend SDK call
        return DeliveryResult(
            ok=True, provider="resend_email", external_id=f"re_{uuid.uuid4().hex[:8]}"
        )


def make_notification_sender(channel: str | None = None) -> NotificationSender:
    """Factory — dispatches by channel type to the right provider stub."""
    ch = channel or os.getenv("NOTIFICATION_PROVIDER", "stub")
    mapping: dict[str, type] = {
        "stub": StubSender,
        "sms": TwilioSMSSender,
        "email": ResendEmailSender,
    }
    cls = mapping.get(ch)
    if cls is None:
        raise ValueError(f"Unknown notification provider: {ch!r}")
    return cls()
