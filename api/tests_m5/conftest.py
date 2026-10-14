"""Shared fixtures for M5-B governance tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import jwt
import pytest

from api.config import SecretStr, Settings

PLATFORM_ID = UUID("10000000-0000-0000-0000-000000000001")
JWT_SECRET = "m3-test-secret-that-is-at-least-32-bytes"

OWNER_SUBJECT = "paperclip-owner-test"
EXECUTOR_SUBJECT = "paperclip-executor-test"
AGENT_SUBJECT = "paperclip-agent-test"
AGENT_ID = UUID("20000000-0000-0000-0000-000000000001")
POLICY_ID = UUID("30000000-0000-0000-0000-000000000001")


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
        paperclip_database_url=SecretStr("postgresql://unused-paperclip"),
        paperclip_owner_subject=OWNER_SUBJECT,
        paperclip_executor_subject=EXECUTOR_SUBJECT,
        paperclip_policy_id=POLICY_ID,
        paperclip_agent_bindings={AGENT_SUBJECT: AGENT_ID},
        paperclip_envelope_signing_key=SecretStr("paperclip-test-signing-key-32-bytes"),
        paperclip_envelope_ttl_seconds=300,
    )


@pytest.fixture
def owner_token() -> str:
    return jwt.encode(
        {
            "sub": OWNER_SUBJECT,
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "admin",
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def executor_token() -> str:
    return jwt.encode(
        {
            "sub": EXECUTOR_SUBJECT,
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "executor",
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def agent_token() -> str:
    return jwt.encode(
        {
            "sub": AGENT_SUBJECT,
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "agent",
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def unauthorized_token() -> str:
    return jwt.encode(
        {
            "sub": "random-subject",
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "admin",
        },
        JWT_SECRET,
        algorithm="HS256",
    )


class StubDatabase:
    """Fakes the Zippy operational database for transaction/identity lookup."""

    def __init__(self, ready: bool = True) -> None:
        self.is_ready = ready
        self.transactions = 0

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def ready(self) -> bool:
        return self.is_ready

    @contextmanager
    def transaction(self, platform_id):
        self.transactions += 1
        yield object()


class _FakeConnection:
    def execute(self, *args, **kwargs):
        return self

    def fetchone(self):
        return {"allowed": True, "reason_code": "PROPOSAL_CREATED", "governance_id": "40000000-0000-0000-0000-000000000001"}


class StubPaperclipDatabase:
    """Fakes the Paperclip governance database pool."""

    def __init__(self, ready: bool = True) -> None:
        self.is_ready = ready
        self.transactions = 0

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def ready(self) -> bool:
        return self.is_ready

    @contextmanager
    def transaction(self, tenant_id):
        self.transactions += 1
        yield _FakeConnection()
