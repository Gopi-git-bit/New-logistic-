"""M5-B route integration tests with stubbed dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from conftest import (
    AGENT_SUBJECT,
    EXECUTOR_SUBJECT,
    OWNER_SUBJECT,
    StubDatabase,
    StubPaperclipDatabase,
)
from fastapi.testclient import TestClient

from api.main import create_app
from api.repositories import RequestIdentity
from api.repositories_paperclip import GovernanceResult


class StubCoreRepository:
    def resolve_identity(self, connection, platform_id, external_subject):
        roles = set()
        if external_subject == OWNER_SUBJECT:
            roles.add("admin")
        if external_subject == AGENT_SUBJECT:
            roles.add("admin")
            roles.add("agent")
        if external_subject == EXECUTOR_SUBJECT:
            roles.add("executor")
        return RequestIdentity(
            platform_id,
            UUID("c0000000-0000-0000-0000-000000000001"),
            None,
            frozenset(roles or {"agent"}),
        )

    def execute(self, _connection, _identity, _tool, _payload, _idempotency_key, _correlation_id):
        return None


class _FakeRepo:
    def __init__(self) -> None:
        self.last = None

    def create_proposal(self, **kwargs):
        self.last = ("create_proposal", kwargs)
        return GovernanceResult(
            allowed=True,
            reason_code="PROPOSAL_CREATED",
            governance_id=UUID("40000000-0000-0000-0000-000000000001"),
        )

    def record_invariant(self, **kwargs):
        self.last = ("record_invariant", kwargs)

    def acquire_decision_lock(self, **kwargs):
        self.last = ("acquire_decision_lock", kwargs)
        return GovernanceResult(True, "LOCK_ACQUIRED", UUID("50000000-0000-0000-0000-000000000001"))

    def release_decision_lock(self, **kwargs):
        self.last = ("release_decision_lock", kwargs)
        return GovernanceResult(True, "LOCK_RELEASED", UUID("60000000-0000-0000-0000-000000000001"))

    def decide(self, **kwargs):
        self.last = ("decide", kwargs)
        return GovernanceResult(True, "DECISION_RECORDED", UUID("70000000-0000-0000-0000-000000000001"))

    def issue_grant(self, **kwargs):
        self.last = ("issue_grant", kwargs)
        return GovernanceResult(True, "GRANT_ISSUED", UUID("80000000-0000-0000-0000-000000000001"))

    def revoke_grant(self, **kwargs):
        self.last = ("revoke_grant", kwargs)
        return GovernanceResult(True, "GRANT_REVOKED", UUID("90000000-0000-0000-0000-000000000001"))

    def consume_grant(self, **kwargs):
        self.last = ("consume_grant", kwargs)
        return GovernanceResult(True, "GRANT_CONSUMED", UUID("80000000-0000-0000-0000-000000000001"))

    def record_execution_attempt(self, **kwargs):
        self.last = ("record_execution_attempt", kwargs)
        return GovernanceResult(True, "ATTEMPT_RECORDED", UUID("80000000-0000-0000-0000-000000000001"))

    def record_heartbeat(self, **kwargs):
        self.last = ("record_heartbeat", kwargs)
        return GovernanceResult(True, "HEARTBEAT_RECORDED", UUID("a0000000-0000-0000-0000-000000000001"))

    def record_token_cost(self, **kwargs):
        self.last = ("record_token_cost", kwargs)
        return GovernanceResult(True, "TOKEN_COST_RECORDED", UUID("b0000000-0000-0000-0000-000000000001"))

    def evaluate_loop_guard(self, **kwargs):
        self.last = ("evaluate_loop_guard", kwargs)
        return GovernanceResult(True, "LOOP_GUARD_PASSED", UUID("40000000-0000-0000-0000-000000000001"))


def _client(settings, owner_token, fake_repo=None):
    app = create_app(
        settings=settings,
        database=StubDatabase(),
        repository=StubCoreRepository(),
        paperclip_database=StubPaperclipDatabase(ready=True),
        finance_repository=fake_repo or _FakeRepo(),
        dispatch_repository=fake_repo or _FakeRepo(),
    )
    return TestClient(app)


def test_create_proposal_route(settings, agent_token):
    with _client(settings, agent_token) as client:
        response = client.post(
            "/api/v1/governance/proposals",
            json={
                "action_key": "UPDATE_ORDER_STATUS",
                "target_system": "ZIPPY",
                "entity_type": "order",
                "entity_id": "ord-123",
                "payload": {"status": "shipped"},
                "idempotency_key": "00000000-0000-4000-8000-000000000001",
                "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
            headers={
                "Authorization": f"Bearer {agent_token}",
                "Idempotency-Key": "00000000-0000-4000-8000-000000000001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert data["reason_code"] == "PROPOSAL_CREATED"


def test_decide_route_requires_owner(settings, agent_token):
    with _client(settings, agent_token) as client:
        response = client.post(
            "/api/v1/governance/proposals/40000000-0000-0000-0000-000000000001/decisions",
            json={
                "decision": "approved",
                "reason": "looks good",
                "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


def test_unauthorized_subject_rejected(settings, unauthorized_token):
    with _client(settings, unauthorized_token) as client:
        response = client.post(
            "/api/v1/governance/proposals",
            json={
                "action_key": "UPDATE_ORDER_STATUS",
                "target_system": "ZIPPY",
                "entity_type": "order",
                "entity_id": "ord-123",
                "payload": {"status": "shipped"},
                "idempotency_key": "00000000-0000-4000-8000-000000000002",
                "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
            headers={
                "Authorization": f"Bearer {unauthorized_token}",
                "Idempotency-Key": "00000000-0000-4000-8000-000000000002",
            },
        )
        assert response.status_code == 403


def test_no_get_status_route_exists(settings, owner_token):
    with _client(settings, owner_token) as client:
        response = client.get("/api/v1/governance/proposals/40000000-0000-0000-0000-000000000001")
        assert response.status_code in (404, 405)


def test_authority_fields_are_rejected(settings, agent_token):
    with _client(settings, agent_token) as client:
        for field in ("tenant_id", "agent_id", "policy_id", "approver_ref", "executor_subject", "role", "payload_hash", "policy_checksum"):
            response = client.post("/api/v1/governance/proposals", headers={"Authorization": f"Bearer {agent_token}", "Idempotency-Key": "synthetic-idempotency-key"}, json={"action_key": "REFUND", "target_system": "ZIPPY", "entity_type": "order", "entity_id": "synthetic", "payload": {}, "idempotency_key": "synthetic-key", "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(), field: "untrusted"})
            assert response.status_code == 422
            assert "untrusted" not in response.text


def test_forged_claims_do_not_authorize_owner(settings):
    import jwt

    forged = jwt.encode({"sub": "random-subject", "aud": "zippy-api", "exp": datetime.now(UTC) + timedelta(minutes=5), "role": "admin", "user_metadata": {"role": "admin", "owner": True}}, settings.auth_jwt_secret, algorithm="HS256")
    with _client(settings, forged) as client:
        response = client.post("/api/v1/governance/proposals/40000000-0000-0000-0000-000000000001/decisions", headers={"Authorization": f"Bearer {forged}"}, json={"decision": "approved", "reason": "synthetic", "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()})
        assert response.status_code == 403
        assert forged not in response.text
