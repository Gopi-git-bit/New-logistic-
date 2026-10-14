"""Configuration for the M3 deterministic application core and M5-B governance."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import UUID


class ConfigurationError(RuntimeError):
    """Raised when server-controlled configuration is missing or unsafe."""


@dataclass(frozen=True)
class SecretStr:
    """Redacted secret value for safe Settings representation."""

    value: str

    def __repr__(self) -> str:
        return "***REDACTED***"

    def __str__(self) -> str:
        return "***REDACTED***"

    def reveal(self) -> str:
        return self.value


@dataclass(frozen=True)
class Settings:
    # repr=False on every secret-bearing field: the default dataclass repr()
    # (used implicitly by pytest failure output, str(), and logging of this
    # object) must never print a connection string or webhook/JWT secret.
    database_url: str = field(repr=False)
    app_env: str
    auth_mode: str
    auth_jwt_secret: str = field(repr=False)
    platform_id: UUID
    pricing_policy_version: str
    pricing_currency: str
    pricing_base_amount: Decimal
    pricing_per_km: Decimal
    pricing_per_kg: Decimal
    task_max_attempts: int = 3
    task_lease_seconds: int = 30
    retry_base_seconds: int = 5
    retry_max_seconds: int = 300
    razorpay_webhook_secret: str = field(default="", repr=False)
    # M5-B server-controlled governance configuration.
    paperclip_database_url: SecretStr = field(default=SecretStr(""), repr=False)
    paperclip_owner_subject: str = field(default="")
    paperclip_executor_subject: str = field(default="")
    paperclip_policy_id: UUID | None = field(default=None)
    paperclip_agent_bindings: dict[str, UUID] = field(default_factory=dict, repr=False)
    paperclip_envelope_signing_key: SecretStr = field(default=SecretStr(""), repr=False)
    paperclip_envelope_ttl_seconds: int = 300


def _decimal(name: str) -> Decimal:
    try:
        value = Decimal(os.environ.get(name, ""))
    except InvalidOperation as exc:
        raise RuntimeError(f"{name} must be a finite decimal") from exc
    if not value.is_finite() or value < 0:
        raise RuntimeError(f"{name} must be a finite non-negative decimal")
    return value


def _uuid(name: str) -> UUID:
    try:
        return UUID(os.environ.get(name, "").strip())
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a valid UUID") from exc


def _non_empty(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _agent_bindings() -> dict[str, UUID]:
    raw = os.environ.get("PAPERCLIP_AGENT_BINDINGS_JSON", "").strip()
    if not raw:
        raise ConfigurationError("PAPERCLIP_AGENT_BINDINGS_JSON is required")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            "PAPERCLIP_AGENT_BINDINGS_JSON must be valid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ConfigurationError(
            "PAPERCLIP_AGENT_BINDINGS_JSON must be an object"
        )
    bindings: dict[str, UUID] = {}
    seen_uuids: set[UUID] = set()
    for key, value in parsed.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigurationError(
                "PAPERCLIP_AGENT_BINDINGS_JSON keys must be non-empty strings"
            )
        try:
            agent_id = UUID(str(value))
        except ValueError as exc:
            raise ConfigurationError(
                f"PAPERCLIP_AGENT_BINDINGS_JSON value for {key} must be a UUID"
            ) from exc
        if agent_id in seen_uuids:
            raise ConfigurationError(
                "PAPERCLIP_AGENT_BINDINGS_JSON contains duplicate agent UUID"
            )
        seen_uuids.add(agent_id)
        bindings[key.strip()] = agent_id
    if not bindings:
        raise ConfigurationError(
            "PAPERCLIP_AGENT_BINDINGS_JSON must contain at least one binding"
        )
    return bindings


def _envelope_ttl() -> int:
    raw = os.environ.get("PAPERCLIP_ENVELOPE_TTL_SECONDS", "300").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            "PAPERCLIP_ENVELOPE_TTL_SECONDS must be an integer"
        ) from exc
    if value < 1 or value > 300:
        raise ConfigurationError(
            "PAPERCLIP_ENVELOPE_TTL_SECONDS must be between 1 and 300"
        )
    return value


def load_settings() -> Settings:
    try:
        platform_id = UUID(os.environ.get("ZIPPY_PLATFORM_ID", ""))
    except ValueError as exc:
        raise RuntimeError("ZIPPY_PLATFORM_ID must be a UUID") from exc
    settings = Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        app_env=os.environ.get("APP_ENV", "development"),
        auth_mode=os.environ.get("AUTH_MODE", "disabled"),
        auth_jwt_secret=os.environ.get("AUTH_JWT_SECRET", ""),
        platform_id=platform_id,
        pricing_policy_version=os.environ.get("M3_PRICING_POLICY_VERSION", ""),
        pricing_currency=os.environ.get("M3_PRICING_CURRENCY", ""),
        pricing_base_amount=_decimal("M3_PRICING_BASE_AMOUNT"),
        pricing_per_km=_decimal("M3_PRICING_PER_KM"),
        pricing_per_kg=_decimal("M3_PRICING_PER_KG"),
        razorpay_webhook_secret=os.environ.get("RAZORPAY_WEBHOOK_SECRET", ""),
        paperclip_database_url=SecretStr(
            _non_empty("PAPERCLIP_DATABASE_URL")
        ),
        paperclip_owner_subject=_non_empty("PAPERCLIP_OWNER_SUBJECT"),
        paperclip_executor_subject=_non_empty("PAPERCLIP_EXECUTOR_SUBJECT"),
        paperclip_policy_id=_uuid("PAPERCLIP_POLICY_ID"),
        paperclip_agent_bindings=_agent_bindings(),
        paperclip_envelope_signing_key=SecretStr(
            _non_empty("PAPERCLIP_ENVELOPE_SIGNING_KEY")
        ),
        paperclip_envelope_ttl_seconds=_envelope_ttl(),
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if settings.auth_mode != "test_jwt" or settings.app_env not in {
        "development",
        "test",
    }:
        raise RuntimeError(
            "M3 supports only the isolated test/dev authentication adapter"
        )
    if len(settings.auth_jwt_secret) < 32:
        raise RuntimeError("AUTH_JWT_SECRET must contain at least 32 characters")
    if not settings.pricing_policy_version.startswith("test-"):
        raise RuntimeError("M3 pricing must use an explicitly test-only policy version")
    if (
        len(settings.pricing_currency) != 3
        or not settings.pricing_currency.isalpha()
        or not settings.pricing_currency.isupper()
    ):
        raise RuntimeError("M3_PRICING_CURRENCY must be an uppercase ISO-style code")
    if not settings.paperclip_database_url.reveal():
        raise ConfigurationError("PAPERCLIP_DATABASE_URL is required")
    if not settings.paperclip_owner_subject:
        raise ConfigurationError("PAPERCLIP_OWNER_SUBJECT is required")
    if not settings.paperclip_executor_subject:
        raise ConfigurationError("PAPERCLIP_EXECUTOR_SUBJECT is required")
    if not settings.paperclip_agent_bindings:
        raise ConfigurationError("PAPERCLIP_AGENT_BINDINGS_JSON is required")
    if len(settings.paperclip_envelope_signing_key.reveal()) < 32:
        raise ConfigurationError(
            "PAPERCLIP_ENVELOPE_SIGNING_KEY must be at least 32 bytes"
        )
    if settings.paperclip_owner_subject == settings.paperclip_executor_subject:
        raise ConfigurationError(
            "PAPERCLIP_OWNER_SUBJECT and PAPERCLIP_EXECUTOR_SUBJECT must differ"
        )

    if settings.paperclip_policy_id is None or not 1 <= settings.paperclip_envelope_ttl_seconds <= 300:
        raise ConfigurationError("Paperclip policy and bounded lifetime are required")
    if settings.paperclip_owner_subject in settings.paperclip_agent_bindings:
        raise ConfigurationError("Owner cannot also be a proposal agent")
    if settings.paperclip_executor_subject in settings.paperclip_agent_bindings:
        raise ConfigurationError("Executor cannot also be a proposal agent")
