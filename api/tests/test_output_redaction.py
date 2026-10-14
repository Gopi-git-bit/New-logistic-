"""Focused output-redaction tests for the M3 deterministic core.

The M3 application defines no logging sinks. These tests prove that the only
application output channels (HTTP error envelopes and configuration errors)
never echo credentials, bearer tokens, database URLs, passwords, or sensitive
request field values. No logging is added as a test target.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from api.config import load_settings
from api.main import create_app
from api.tests.test_api import StubDatabase, StubRepository, _client

IDEMPOTENCY_HEADER = {"Idempotency-Key": "00000000-0000-4000-8000-00000000000a"}


def test_presented_invalid_bearer_token_is_not_echoed(settings, order_payload):
    presented = "m3synthetic-bearer-token-must-not-leak"
    with _client(settings, StubDatabase(), StubRepository()) as client:
        response = client.post(
            "/api/v1/orders",
            json=order_payload,
            headers={"Authorization": f"Bearer {presented}", **IDEMPOTENCY_HEADER},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert presented not in response.text


def test_valid_jwt_is_not_echoed_in_error_responses(settings, order_payload, token):
    with TestClient(
        create_app(settings, StubDatabase(), StubRepository(OperationalError("db down"))),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/api/v1/orders",
            json=order_payload,
            headers={"Authorization": f"Bearer {token}", **IDEMPOTENCY_HEADER},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert token not in response.text
    assert settings.auth_jwt_secret not in response.text


def test_validation_error_does_not_echo_sensitive_payload_values(
    settings, order_payload, token
):
    sensitive_value = "postgresql://m3user:m3secretpw@db.invalid:5432/zippy"
    payload = dict(order_payload)
    payload["distance_km"] = sensitive_value
    with _client(settings, StubDatabase(), StubRepository()) as client:
        response = client.post(
            "/api/v1/orders",
            json=payload,
            headers={"Authorization": f"Bearer {token}", **IDEMPOTENCY_HEADER},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert sensitive_value not in response.text
    assert "m3secretpw" not in response.text
    assert "db.invalid" not in response.text


def test_internal_error_does_not_leak_database_url_or_password(
    settings, order_payload, token
):
    poisoned_url = "postgresql://m3user:m3supersecretpw@db.invalid:5432/zippy"
    poisoned = replace(settings, database_url=poisoned_url)
    failure = RuntimeError(f"connection failed for {poisoned_url}")
    with TestClient(
        create_app(poisoned, StubDatabase(), StubRepository(failure)),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/api/v1/orders",
            json=order_payload,
            headers={"Authorization": f"Bearer {token}", **IDEMPOTENCY_HEADER},
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert poisoned_url not in response.text
    assert "m3supersecretpw" not in response.text
    assert "db.invalid" not in response.text


def test_config_validation_does_not_echo_secret_values(monkeypatch):
    short_secret = "m3-short-jwt-secret-fixture"
    database_password = "m3configdbpw"
    for key, value in {
        "DATABASE_URL": f"postgresql://m3user:{database_password}@db.invalid/zippy",
        "AUTH_JWT_SECRET": short_secret,
        "ZIPPY_PLATFORM_ID": "10000000-0000-0000-0000-000000000001",
        "M3_PRICING_POLICY_VERSION": "test-m3-v1",
        "M3_PRICING_CURRENCY": "INR",
        "M3_PRICING_BASE_AMOUNT": "100.00",
        "M3_PRICING_PER_KM": "12.50",
        "M3_PRICING_PER_KG": "0.75",
        "APP_ENV": "test",
        "AUTH_MODE": "test_jwt",
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError) as excinfo:
        load_settings()
    message = str(excinfo.value)
    assert short_secret not in message
    assert database_password not in message
    assert "db.invalid" not in message
