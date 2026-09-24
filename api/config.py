"""Configuration for the M3 deterministic application core."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import UUID


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


def _decimal(name: str) -> Decimal:
    try:
        value = Decimal(os.environ.get(name, ""))
    except InvalidOperation as exc:
        raise RuntimeError(f"{name} must be a finite decimal") from exc
    if not value.is_finite() or value < 0:
        raise RuntimeError(f"{name} must be a finite non-negative decimal")
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
