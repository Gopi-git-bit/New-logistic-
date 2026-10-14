from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from api.auth import authenticate_subject
from api.config import validate_settings
from api.models.core import OrderCreate, TransitionRequest
from api.pricing import calculate_price
from api.repositories import canonical_fingerprint, retry_at


def test_price_is_deterministic_decimal_and_versioned(settings, order_payload):
    order = OrderCreate.model_validate(order_payload)

    first = calculate_price(order, settings)
    second = calculate_price(order, settings)

    assert first == second
    assert first.amount == Decimal("240.00")
    assert first.policy_version == "test-m3-v1"
    assert first.currency == "INR"
    assert len(first.input_hash) == 64


def test_order_fingerprint_is_canonical(settings, order_payload):
    first = OrderCreate.model_validate(order_payload)
    reordered = OrderCreate.model_validate(dict(reversed(list(order_payload.items()))))

    assert canonical_fingerprint(first) == canonical_fingerprint(reordered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cargo_weight_kg", "0"),
        ("distance_km", "NaN"),
        ("requested_pickup_at", "2030-01-02T10:00:00"),
    ],
)
def test_order_rejects_invalid_business_input(order_payload, field, value):
    order_payload[field] = value
    with pytest.raises(ValidationError):
        OrderCreate.model_validate(order_payload)


def test_order_rejects_hazardous_and_return_trip(order_payload):
    order_payload["service"] = {
        "vehicle_class": "light",
        "body_type": "closed",
        "hazardous": True,
        "return_trip": True,
    }
    with pytest.raises(ValidationError):
        OrderCreate.model_validate(order_payload)


def test_transition_status_is_bounded():
    with pytest.raises(ValidationError):
        TransitionRequest(
            expected_status="pending",
            expected_version=1,
            next_status="invented",
            reason="test",
        )


def test_authentication_uses_only_signed_subject(settings):
    token = jwt.encode(
        {
            "sub": "customer-subject",
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "admin",
        },
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )

    subject = authenticate_subject(
        request, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert subject.external_subject == "customer-subject"
    assert not hasattr(subject, "role")


def test_authentication_rejects_invalid_token(settings):
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )
    with pytest.raises(HTTPException) as raised:
        authenticate_subject(
            request,
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"),
        )
    assert raised.value.status_code == 401


def test_authentication_requires_expiry(settings):
    token = jwt.encode(
        {"sub": "customer-subject", "aud": "zippy-api"},
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )
    with pytest.raises(HTTPException) as raised:
        authenticate_subject(
            request, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )
    assert raised.value.status_code == 401


def test_configuration_fails_closed_outside_test_or_development(settings):
    with pytest.raises(RuntimeError, match="test/dev"):
        validate_settings(replace(settings, app_env="production"))


def test_retry_backoff_is_bounded():
    before = datetime.now(UTC)
    scheduled = retry_at(20, base_seconds=5, max_seconds=300)
    after = datetime.now(UTC)
    assert (
        before + timedelta(seconds=300) <= scheduled <= after + timedelta(seconds=300)
    )
