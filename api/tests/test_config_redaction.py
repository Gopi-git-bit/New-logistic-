"""Regression tests for the M4 secret-redaction correction (D-27).

The retained failed M4 proof (2026-09-23, log id `2zIomoO3`) exposed the
synthetic webhook/JWT test secrets in a pytest failure traceback because
`Settings` used the default dataclass `repr()`, which prints every field
verbatim. That historical log is left unmodified as evidence; these tests
prove the underlying defect is fixed and cannot recur.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import UUID

from api.config import Settings

SENTINEL_DATABASE_URL = "postgresql://synthetic_user:SENTINEL_DB_PASSWORD@db.invalid/zippy"
SENTINEL_JWT_SECRET = "SENTINEL-JWT-SECRET-VALUE-DO-NOT-LEAK"
SENTINEL_WEBHOOK_SECRET = "SENTINEL-WEBHOOK-SECRET-VALUE-DO-NOT-LEAK"


def _settings() -> Settings:
    return Settings(
        database_url=SENTINEL_DATABASE_URL,
        app_env="test",
        auth_mode="test_jwt",
        auth_jwt_secret=SENTINEL_JWT_SECRET,
        platform_id=UUID("10000000-0000-0000-0000-000000000001"),
        pricing_policy_version="test-v1",
        pricing_currency="INR",
        pricing_base_amount=Decimal("100.00"),
        pricing_per_km=Decimal("12.50"),
        pricing_per_kg=Decimal("0.75"),
        razorpay_webhook_secret=SENTINEL_WEBHOOK_SECRET,
    )


def _assert_no_secrets(text: str) -> None:
    assert SENTINEL_DATABASE_URL not in text
    assert "SENTINEL_DB_PASSWORD" not in text
    assert SENTINEL_JWT_SECRET not in text
    assert SENTINEL_WEBHOOK_SECRET not in text


def test_settings_repr_excludes_secrets():
    text = repr(_settings())
    _assert_no_secrets(text)
    # Non-secret fields must still be visible; this is a targeted exclusion,
    # not a blanket repr suppression.
    assert "app_env='test'" in text
    assert "10000000-0000-0000-0000-000000000001" in text


def test_settings_str_excludes_secrets():
    _assert_no_secrets(str(_settings()))


def test_dataclasses_replace_still_excludes_secrets():
    """`replace()` (used throughout the test suite to override database_url)
    must not reintroduce the secret into any string representation."""
    settings = _settings()
    replaced = replace(settings, database_url="postgresql://unused")
    _assert_no_secrets(repr(replaced))
    # the original sentinel is gone because it was replaced, but the new
    # (non-secret placeholder) value's repr-suppression still holds
    assert "database_url" not in repr(replaced)


def test_settings_appears_safely_in_a_simulated_pytest_failure_repr():
    """Reproduces the exact failure shape from the retained failed M4 proof
    log (2zIomoO3): a Settings instance captured in an assertion/traceback
    context must not leak secrets via its repr."""
    settings = _settings()

    def _boom(value: Settings) -> None:
        raise AssertionError(f"settings = {value!r}")

    try:
        _boom(settings)
    except AssertionError as exc:
        _assert_no_secrets(str(exc))
    else:  # pragma: no cover - defensive
        raise AssertionError("expected AssertionError was not raised")
