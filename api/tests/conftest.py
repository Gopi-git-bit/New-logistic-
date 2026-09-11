from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import jwt
import pytest

from api.config import Settings

PLATFORM_ID = UUID("10000000-0000-0000-0000-000000000001")
JWT_SECRET = "m3-test-secret-that-is-at-least-32-bytes"


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
    )


@pytest.fixture
def order_payload() -> dict[str, object]:
    return {
        "pickup": {
            "address": "Origin",
            "latitude": "18.5204",
            "longitude": "73.8567",
            "accuracy_meters": "5",
        },
        "delivery": {
            "address": "Destination",
            "latitude": "19.0760",
            "longitude": "72.8777",
            "accuracy_meters": "7",
        },
        "cargo_description": "Sealed cartons",
        "cargo_weight_kg": "20.000",
        "distance_km": "10.000",
        "service": {
            "vehicle_class": "light",
            "body_type": "closed",
            "hazardous": False,
            "return_trip": False,
        },
        "requested_pickup_at": "2030-01-02T10:00:00+05:30",
    }


@pytest.fixture
def token() -> str:
    return jwt.encode(
        {
            "sub": "customer-subject",
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "admin",
        },
        JWT_SECRET,
        algorithm="HS256",
    )
