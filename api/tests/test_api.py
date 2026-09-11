from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from api.main import create_app
from api.models.core import OrderAccepted
from api.repositories import ConflictError, ForbiddenError, RequestIdentity


class StubDatabase:
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


class StubRepository:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure

    def resolve_identity(self, connection, platform_id, external_subject):
        if self.failure:
            raise self.failure
        return RequestIdentity(
            platform_id,
            UUID("c0000000-0000-0000-0000-000000000001"),
            UUID("c1000000-0000-0000-0000-000000000001"),
            frozenset({"customer"}),
        )

    def create_order(
        self,
        connection,
        identity,
        order,
        quote,
        idempotency_key,
        correlation_id,
        fingerprint,
        task_max_attempts,
    ):
        return OrderAccepted(
            order_id=UUID("30000000-0000-0000-0000-000000000001"),
            workflow_id=UUID("40000000-0000-0000-0000-000000000001"),
            status="pending",
            correlation_id=correlation_id,
            accepted_at=datetime(2030, 1, 1, tzinfo=UTC),
            idempotency_replay=False,
        )


def _client(settings, database: StubDatabase, repository: StubRepository) -> TestClient:
    return TestClient(create_app(settings, database, repository))


def test_health_and_readiness(settings):
    database = StubDatabase()
    with _client(settings, database, StubRepository()) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/api/v1/ready").json() == {"status": "ready"}


def test_not_ready_uses_error_envelope(settings):
    with _client(settings, StubDatabase(ready=False), StubRepository()) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert response.json()["error"]["retryable"] is True


def test_order_requires_authentication(settings, order_payload):
    database = StubDatabase()
    with _client(settings, database, StubRepository()) as client:
        response = client.post(
            "/api/v1/orders",
            json=order_payload,
            headers={"Idempotency-Key": "00000000-0000-4000-8000-000000000001"},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert database.transactions == 0


def test_order_acceptance_returns_202_workflow_and_correlation(
    settings, order_payload, token
):
    correlation_id = "50000000-0000-4000-8000-000000000001"
    with _client(settings, StubDatabase(), StubRepository()) as client:
        response = client.post(
            "/api/v1/orders",
            json=order_payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "60000000-0000-4000-8000-000000000001",
                "X-Correlation-ID": correlation_id,
            },
        )
    assert response.status_code == 202
    assert response.json()["workflow_id"] == "40000000-0000-0000-0000-000000000001"
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_validation_and_malformed_json_use_stable_errors(settings, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "60000000-0000-4000-8000-000000000001",
        "content-type": "application/json",
    }
    with _client(settings, StubDatabase(), StubRepository()) as client:
        malformed = client.post("/api/v1/orders", content="{", headers=headers)
        invalid = client.post("/api/v1/orders", json={}, headers=headers)
    assert (malformed.status_code, malformed.json()["error"]["code"]) == (
        400,
        "MALFORMED_REQUEST",
    )
    assert (invalid.status_code, invalid.json()["error"]["code"]) == (
        422,
        "VALIDATION_FAILED",
    )


def test_repository_conflicts_and_denials_are_sanitized(settings, order_payload, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "60000000-0000-4000-8000-000000000001",
    }
    with _client(
        settings, StubDatabase(), StubRepository(ConflictError("key conflict"))
    ) as client:
        conflict = client.post("/api/v1/orders", json=order_payload, headers=headers)
    with _client(
        settings, StubDatabase(), StubRepository(ForbiddenError("actor denied"))
    ) as client:
        forbidden = client.post("/api/v1/orders", json=order_payload, headers=headers)
    assert (conflict.status_code, conflict.json()["error"]["code"]) == (
        409,
        "IDEMPOTENCY_CONFLICT",
    )
    assert (forbidden.status_code, forbidden.json()["error"]["code"]) == (
        403,
        "FORBIDDEN",
    )
