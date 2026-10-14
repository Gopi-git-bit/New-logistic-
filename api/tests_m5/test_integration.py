"""Real D-28 calls, enabled only by the private disposable proof harness."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from psycopg.conninfo import conninfo_to_dict

from api.auth import AuthenticatedSubject
from api.config import SecretStr
from api.database import PaperclipDatabase
from api.repositories import RequestIdentity
from api.repositories_paperclip import GovernanceDenied, PaperclipRepository
from api.services.paperclip import PaperclipService
from api.services.paperclip_envelope import EnvelopeSigner
from api.services.synthetic_executor import SyntheticExecutor

pytestmark = pytest.mark.skipif(
    os.environ.get("PAPERCLIP_DISPOSABLE_PROOF") != "YES",
    reason="requires the private M5-B disposable PostgreSQL proof",
)
TENANT = UUID("11111111-1111-1111-1111-111111111111")
AGENT = UUID("11111111-1111-1111-1111-111111111112")
POLICY = UUID("11111111-1111-1111-1111-111111111113")


@pytest.fixture
def proof(settings):
    url = os.environ["PAPERCLIP_DATABASE_URL"]
    params = conninfo_to_dict(url)
    assert params["host"].startswith("/tmp/paperclip-m5b.")
    assert params["dbname"].startswith("paperclip_m5_disposable_")
    assert params["user"] == "paperclip_m5_app_login"
    assert params.get("hostaddr", "") == ""
    cfg = replace(
        settings, platform_id=TENANT, paperclip_policy_id=POLICY,
        paperclip_database_url=SecretStr(url),
        paperclip_owner_subject=os.environ["PAPERCLIP_OWNER_SUBJECT"],
        paperclip_executor_subject=os.environ["PAPERCLIP_EXECUTOR_SUBJECT"],
        paperclip_agent_bindings={"paperclip-agent-test": AGENT},
        paperclip_envelope_signing_key=SecretStr(os.environ["PAPERCLIP_ENVELOPE_SIGNING_KEY"]),
    )
    db = PaperclipDatabase(url)
    db.open()
    repo = PaperclipRepository(db)
    service = PaperclipService(repo, EnvelopeSigner(cfg.paperclip_envelope_signing_key.reveal().encode()), SyntheticExecutor(repo), cfg)
    try:
        yield service, repo, cfg
    finally:
        db.close()


def proposal(proof, *, entity=None, payload=None, key=None):
    service, _, _ = proof
    entity = entity or str(uuid4())
    payload = payload if payload is not None else {"ref": "synthetic", "nested": {"long": 1, "a": [True, 1.25, "é"]}}
    result = service.create_proposal(
        AuthenticatedSubject("paperclip-agent-test"), "REFUND", "ZIPPY", "order", entity,
        payload, key or str(uuid4()), datetime.now(UTC) + timedelta(minutes=5), uuid4(),
    )
    return result, entity, payload


def approved_grant(proof):
    service, _, cfg = proof
    result, entity, payload = proposal(proof)
    assert result.allowed
    owner = AuthenticatedSubject(cfg.paperclip_owner_subject)
    identity = RequestIdentity(TENANT, uuid4(), None, frozenset({"admin"}))
    assert service.decide(owner, identity, result.governance_id, True, datetime.now(UTC) + timedelta(minutes=5)).allowed
    grant = service.issue_grant(owner, identity, result.governance_id)
    assert grant.allowed
    envelope = service.issue_grant_envelope(
        AuthenticatedSubject("paperclip-agent-test"), result.governance_id, grant.governance_id,
        "REFUND", "ZIPPY", "order", entity, payload,
    )
    return grant, envelope


def test_create_proposal_flow(proof):
    result, _, _ = proposal(proof)
    assert result.allowed and result.reason_code == "PROPOSAL_CREATED"
    assert result.governance_id is not None


def test_synthetic_execution_and_replay(proof):
    service, _, cfg = proof
    grant, envelope = approved_grant(proof)
    subject = AuthenticatedSubject(cfg.paperclip_executor_subject)
    assert service.consume_grant(subject, envelope.to_string(), grant.governance_id).allowed
    with pytest.raises(GovernanceDenied):
        service.consume_grant(subject, envelope.to_string(), grant.governance_id)


def test_concurrent_consumption_exactly_one(proof):
    service, _, cfg = proof
    grant, envelope = approved_grant(proof)
    barrier = Barrier(2)

    def consume():
        barrier.wait(timeout=10)
        try:
            return service.consume_grant(AuthenticatedSubject(cfg.paperclip_executor_subject), envelope.to_string(), grant.governance_id).allowed
        except GovernanceDenied:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert results.count(True) == 1 and results.count(False) == 1
    print("m5b_concurrency=PASS successes=1 denials=1")


@pytest.mark.parametrize("field,value", [
    ("agent_id", UUID("11111111-1111-1111-1111-111111111114")),
    ("action_key", "OTHER_ACTION"), ("target_system", "ODOO"),
    ("entity_id", "different"), ("payload_hash", "0" * 64),
    ("tenant_id", UUID("22222222-2222-2222-2222-222222222222")),
])
def test_database_grant_binding_denial(proof, field, value):
    _, repo, _ = proof
    grant, env = approved_grant(proof)
    args = {"tenant_id": TENANT, "grant_id": grant.governance_id, "agent_id": AGENT,
            "action_key": env.action, "target_system": env.target_system,
            "entity_type": env.entity_type, "entity_id": env.entity_id, "payload_hash": env.payload_hash}
    args[field] = value
    assert not repo.consume_grant(**args).allowed


def test_missing_approval_rejection_lock_invariant_and_revocation(proof):
    _, repo, cfg = proof
    result, _, _ = proposal(proof)
    pid = result.governance_id
    assert not repo.issue_grant(TENANT, pid).allowed
    assert repo.acquire_decision_lock(TENANT, pid, cfg.paperclip_owner_subject, "synthetic review").allowed
    assert not repo.issue_grant(TENANT, pid).allowed
    assert repo.release_decision_lock(TENANT, pid, cfg.paperclip_owner_subject).allowed
    repo.record_invariant(TENANT, pid, "synthetic", False)
    assert repo.decide(TENANT, pid, cfg.paperclip_owner_subject, True, datetime.now(UTC) + timedelta(minutes=5)).allowed
    assert not repo.issue_grant(TENANT, pid).allowed
    grant, env = approved_grant(proof)
    assert repo.revoke_grant(TENANT, grant.governance_id, cfg.paperclip_owner_subject, "synthetic revoke").allowed
    assert not repo.consume_grant(TENANT, grant.governance_id, AGENT, env.action, env.target_system, env.entity_type, env.entity_id, env.payload_hash).allowed


def test_loop_budget_heartbeat_and_inactive_policy(proof):
    _, repo, _ = proof
    entity = str(uuid4())
    rows = [proposal(proof, entity=entity)[0] for _ in range(3)]
    assert rows[0].allowed and rows[1].allowed and not rows[2].allowed
    assert not repo.evaluate_loop_guard(TENANT, rows[2].governance_id).allowed
    heartbeat = repo.record_heartbeat(TENANT, AGENT, None, str(uuid4()))
    assert heartbeat.allowed
    assert repo.record_token_cost(TENANT, AGENT, heartbeat.governance_id, Decimal(0)).allowed
    zero = UUID("11111111-1111-1111-1111-111111111114")
    assert not repo.record_token_cost(TENANT, zero, None, Decimal(1)).allowed
    assert not repo.create_proposal(TENANT, AGENT, UUID("11111111-1111-1111-1111-111111111115"), "REFUND", "ZIPPY", "order", str(uuid4()), {}, str(uuid4()), datetime.now(UTC) + timedelta(minutes=5)).allowed


def test_authenticated_http_lifecycle(proof):
    import jwt
    from fastapi.testclient import TestClient

    from api.main import create_app
    from api.tests_m5.conftest import StubDatabase

    _, repo, cfg = proof

    class Core:
        def resolve_identity(self, connection, platform_id, external_subject):
            return RequestIdentity(platform_id, uuid4(), None, frozenset({"admin"}) if external_subject == cfg.paperclip_owner_subject else frozenset())

    def headers(subject, **extra):
        token = jwt.encode({"sub": subject, "aud": "zippy-api", "exp": datetime.now(UTC) + timedelta(minutes=5)}, cfg.auth_jwt_secret, algorithm="HS256")
        return {"Authorization": "Bearer " + token, **extra}

    with TestClient(create_app(cfg, StubDatabase(), Core(), paperclip_database=repo._database)) as client:
        result = client.post("/api/v1/governance/proposals", headers=headers("paperclip-agent-test", **{"Idempotency-Key": str(uuid4())}), json={"action_key": "REFUND", "target_system": "ZIPPY", "entity_type": "order", "entity_id": str(uuid4()), "payload": {"ref": "http-synthetic"}, "idempotency_key": str(uuid4()), "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()})
        assert result.status_code == 200
        proposal_data = result.json()
        pid = proposal_data["governance_id"]
        decision = client.post(f"/api/v1/governance/proposals/{pid}/decisions", headers=headers(cfg.paperclip_owner_subject), json={"decision": "approved", "reason": "synthetic review", "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()})
        assert decision.status_code == 200 and decision.json()["allowed"]
        grant = client.post(f"/api/v1/governance/proposals/{pid}/grants", headers=headers(cfg.paperclip_owner_subject, **{"X-Governance-Envelope": proposal_data["envelope"]}))
        assert grant.status_code == 200 and grant.json()["allowed"]
        data = grant.json()
        consumed = client.post(f"/api/v1/governance/grants/{data['governance_id']}/consumption", headers=headers(cfg.paperclip_executor_subject, **{"X-Governance-Envelope": data["envelope"]}))
        assert consumed.status_code == 200 and consumed.json()["consumed"]
