from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import jwt
import pytest

from api.config import Settings
from api.database import Database
from api.repositories_finance import FinanceRepository

PLATFORM_ID = UUID("10000000-0000-0000-0000-000000000001")
CROSS_TENANT_PLATFORM_ID = UUID("10000000-0000-0000-0000-000000000002")
JWT_SECRET = "m3-test-secret-that-is-at-least-32-bytes"
WEBHOOK_SECRET = "m4-synthetic-webhook-secret-32bytes!"

ADMIN = "admin-subject"
ADMIN2 = "admin2-subject"
CUSTOMER = "customer-subject"
VENDOR = "vendor-subject"
OTHER_CUSTOMER = "other-customer-subject"
DRIVER_1 = "driver1-subject"
DRIVER_2 = "driver2-subject"

ORDER_A = UUID("30000000-0000-0000-0000-00000000000a")
ORDER_B = UUID("30000000-0000-0000-0000-00000000000b")
ORDER_C = UUID("30000000-0000-0000-0000-00000000000c")
ORDER_D = UUID("30000000-0000-0000-0000-00000000000d")
ORDER_E = UUID("30000000-0000-0000-0000-00000000000e")
CROSS_TENANT_ORDER = UUID("30000000-0000-0000-0000-000000000c99")
TRIP_A = UUID("50000000-0000-0000-0000-00000000000a")

VENDOR_PROFILE = UUID("e0000000-0000-0000-0000-000000000001")
VEHICLE_MODEL = UUID("61000000-0000-0000-0000-000000000001")
VEHICLE_1 = UUID("62000000-0000-0000-0000-000000000001")
VEHICLE_2 = UUID("62000000-0000-0000-0000-000000000002")
DRIVER_PROFILE_1 = UUID("70000000-0000-0000-0000-000000000001")
DRIVER_PROFILE_2 = UUID("70000000-0000-0000-0000-000000000002")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql://unused",
        app_env="test",
        auth_mode="test_jwt",
        auth_jwt_secret=JWT_SECRET,
        platform_id=PLATFORM_ID,
        pricing_policy_version="test-m3-v1",
        pricing_currency="INR",
        pricing_base_amount=Decimal("100.00"),
        pricing_per_km=Decimal("12.50"),
        pricing_per_kg=Decimal("0.75"),
        razorpay_webhook_secret=WEBHOOK_SECRET,
    )


def make_token(subject: str, secret: str = JWT_SECRET) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )


def auth_headers(subject: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(subject)}", **extra}


def prepare_payment_intent(
    database_url: str,
    order_id: UUID,
    provider_reference_id: str,
    expected_amount_minor_units: int,
    expected_currency_code: str = "INR",
    platform_id: UUID = PLATFORM_ID,
) -> UUID:
    """Synthetic fixture standing in for the approved server-side
    payment-intent/order preparation path (D-26/D-27 correction): it
    registers the authoritative provider-reference mapping the webhook must
    resolve through. It never creates a Razorpay order; it only records the
    mapping a real preparation call would have made after doing so.
    """
    repository = FinanceRepository()
    database = Database(database_url)
    database.open()
    try:
        with database.transaction(platform_id) as connection:
            payment_intent_id, _duplicate = repository.prepare_payment_intent(
                connection,
                platform_id,
                order_id,
                provider_reference_id,
                expected_amount_minor_units,
                expected_currency_code,
                uuid4(),
            )
        return payment_intent_id
    finally:
        database.close()
