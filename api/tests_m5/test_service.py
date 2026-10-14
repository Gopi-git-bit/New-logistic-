"""M5-B service layer unit tests (repository faked)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from conftest import (
    AGENT_ID,
    AGENT_SUBJECT,
    EXECUTOR_SUBJECT,
    OWNER_SUBJECT,
    PLATFORM_ID,
    POLICY_ID,
)

from api.auth import AuthenticatedSubject
from api.repositories import ForbiddenError, RequestIdentity
from api.repositories_paperclip import (
    GovernanceDenied,
    GovernanceResult,
    PaperclipRepository,
)
from api.services.paperclip import PaperclipService
from api.services.paperclip_envelope import EnvelopeError, EnvelopeSigner
from api.services.synthetic_executor import SyntheticExecutor


class StubCoreRepository:
    def resolve_identity(self, connection, platform_id, external_subject):
        roles = {"admin"} if external_subject == OWNER_SUBJECT else set()
        if external_subject == AGENT_SUBJECT:
            roles.add("agent")
        if external_subject == EXECUTOR_SUBJECT:
            roles.add("executor")
        return RequestIdentity(
            platform_id,
            UUID("c0000000-0000-0000-0000-000000000001"),
            None,
            frozenset(roles or {"agent"}),
        )


def _make_service(repo: PaperclipRepository) -> PaperclipService:
    settings = MagicMock()
    settings.platform_id = PLATFORM_ID
    settings.paperclip_owner_subject = OWNER_SUBJECT
    settings.paperclip_executor_subject = EXECUTOR_SUBJECT
    settings.paperclip_policy_id = POLICY_ID
    settings.paperclip_agent_bindings = {AGENT_SUBJECT: AGENT_ID}
    settings.paperclip_envelope_ttl_seconds = 300
    signer = EnvelopeSigner(b"test-signing-key-thirty-two-characters")
    executor = SyntheticExecutor(repo)
    return PaperclipService(repo, signer, executor, settings)


def test_create_proposal_resolves_agent():
    repo = MagicMock(spec=PaperclipRepository)
    repo.create_proposal.return_value = GovernanceResult(
        allowed=True, reason_code="PROPOSAL_CREATED", governance_id=UUID("40000000-0000-0000-0000-000000000001")
    )
    service = _make_service(repo)
    subject = AuthenticatedSubject(AGENT_SUBJECT)
    result = service.create_proposal(
        subject,
        action_key="UPDATE_ORDER_STATUS",
        target_system="ZIPPY",
        entity_type="order",
        entity_id="ord-123",
        payload={"status": "shipped"},
        idempotency_key="idem-001",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        correlation_id=UUID("50000000-0000-0000-0000-000000000001"),
    )
    assert result.allowed is True
    assert result.reason_code == "PROPOSAL_CREATED"


def test_unbound_subject_cannot_create_proposal():
    repo = MagicMock(spec=PaperclipRepository)
    service = _make_service(repo)
    subject = AuthenticatedSubject("unbound-subject")
    with pytest.raises((ForbiddenError, GovernanceDenied)):
        service.create_proposal(
            subject,
            action_key="UPDATE_ORDER_STATUS",
            target_system="ZIPPY",
            entity_type="order",
            entity_id="ord-123",
            payload={"status": "shipped"},
            idempotency_key="idem-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            correlation_id=UUID("50000000-0000-0000-0000-000000000001"),
        )


def test_decide_requires_owner_identity():
    repo = MagicMock(spec=PaperclipRepository)
    repo.decide.return_value = GovernanceResult(
        allowed=True, reason_code="DECISION_RECORDED", governance_id=UUID("60000000-0000-0000-0000-000000000001")
    )
    service = _make_service(repo)
    identity = RequestIdentity(
        PLATFORM_ID,
        UUID("c0000000-0000-0000-0000-000000000001"),
        None,
        frozenset({"admin"}),
    )
    result = service.decide(
        AuthenticatedSubject(OWNER_SUBJECT),
        identity,
        UUID("60000000-0000-0000-0000-000000000001"),
        True,
        datetime.now(UTC) + timedelta(minutes=5),
    )
    assert result.allowed is True


def test_non_owner_admin_cannot_decide():
    repo = MagicMock(spec=PaperclipRepository)
    service = _make_service(repo)
    identity = RequestIdentity(
        PLATFORM_ID,
        UUID("c0000000-0000-0000-0000-000000000001"),
        None,
        frozenset({"admin"}),
    )
    with pytest.raises((ForbiddenError, GovernanceDenied)):
        service.decide(
            AuthenticatedSubject(AGENT_SUBJECT),
            identity,
            UUID("60000000-0000-0000-0000-000000000001"),
            True,
            datetime.now(UTC) + timedelta(minutes=5),
        )


def test_grant_envelope_roundtrip():
    repo = MagicMock(spec=PaperclipRepository)
    service = _make_service(repo)
    subject = AuthenticatedSubject(AGENT_SUBJECT)
    proposal_id = UUID("70000000-0000-0000-0000-000000000001")
    grant_id = UUID("80000000-0000-0000-0000-000000000001")
    payload = {"status": "shipped"}
    envelope = service.issue_grant_envelope(
        subject,
        proposal_id,
        grant_id,
        action_key="UPDATE_ORDER_STATUS",
        target_system="ZIPPY",
        entity_type="order",
        entity_id="ord-123",
        payload=payload,
    )
    assert envelope.grant_id == grant_id
    verified = service._signer.verify_string(
        _to_b64(envelope),
        purpose=EnvelopeSigner.PURPOSE_GRANT,
        subject=EXECUTOR_SUBJECT,
        tenant_id=PLATFORM_ID,
    )
    assert verified.payload_hash == service._payload_hash(payload)


def test_executor_cannot_consume_without_envelope():
    repo = MagicMock(spec=PaperclipRepository)
    service = _make_service(repo)
    subject = AuthenticatedSubject(EXECUTOR_SUBJECT)
    with pytest.raises((ForbiddenError, GovernanceDenied, EnvelopeError)):
        service.consume_grant(subject, "not-an-envelope")


def _to_b64(envelope) -> str:
    import base64
    import json
    raw = json.dumps(envelope.to_dict(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def test_settings_secret_str_redacted():
    from api.config import SecretStr
    secret = SecretStr("super-secret")
    assert "super-secret" not in repr(secret)
    assert "super-secret" not in str(secret)
    assert secret.reveal() == "super-secret"


@pytest.mark.parametrize("row", [None, {}, {"allowed": "false", "reason_code": "GRANT_CONSUMED", "governance_id": None}, {"allowed": True, "reason_code": "UNKNOWN", "governance_id": None}, {"allowed": True, "reason_code": "GRANT_ISSUED", "governance_id": None}])
def test_unknown_or_malformed_results_fail_closed(row):
    with pytest.raises(GovernanceDenied):
        PaperclipRepository._to_result(row)


def test_owner_without_server_admin_cannot_decide():
    repo = MagicMock(spec=PaperclipRepository)
    service = _make_service(repo)
    with pytest.raises(ForbiddenError):
        service.decide(AuthenticatedSubject(OWNER_SUBJECT), RequestIdentity(PLATFORM_ID, UUID(int=1), None, frozenset()), UUID(int=2), True, datetime.now(UTC) + timedelta(minutes=5))
    repo.decide.assert_not_called()


def test_database_error_is_sanitized():
    from contextlib import contextmanager

    from psycopg import OperationalError

    class Broken:
        @contextmanager
        def transaction(self, tenant):
            raise OperationalError("synthetic-sensitive-value")
            yield

    repo = PaperclipRepository(Broken())
    with pytest.raises(GovernanceDenied) as error:
        repo.issue_grant(PLATFORM_ID, UUID(int=1))
    assert str(error.value) == "GOVERNANCE_DATABASE_UNAVAILABLE"


def test_synthetic_executor_stops_after_denial():
    repo = MagicMock(spec=PaperclipRepository)
    repo.consume_grant.return_value = GovernanceResult(False, "GRANT_CONSUMPTION_DENIED", None)
    with pytest.raises(GovernanceDenied):
        SyntheticExecutor(repo).execute(PLATFORM_ID, UUID(int=1), AGENT_ID, "REFUND", "ZIPPY", "order", "synthetic", "0" * 64)
    repo.record_execution_attempt.assert_not_called()


def test_missing_policy_configuration_fails_closed(settings):
    from dataclasses import replace

    from api.config import ConfigurationError, validate_settings

    with pytest.raises(ConfigurationError):
        validate_settings(replace(settings, paperclip_policy_id=None))


def test_owner_cannot_be_a_proposing_agent(settings):
    from dataclasses import replace

    from api.config import ConfigurationError, validate_settings

    with pytest.raises(ConfigurationError):
        validate_settings(replace(settings, paperclip_agent_bindings={OWNER_SUBJECT: AGENT_ID}))
