"""M5-B authenticated Paperclip governance routes."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from .auth import AuthenticatedSubject
from .config import Settings
from .database import Database, PaperclipDatabase
from .models.paperclip import (
    DecisionLockRequest,
    ExecutionAttemptRequest,
    GovernanceResponse,
    GrantConsumeResponse,
    HeartbeatRequest,
    HumanDecisionRequest,
    InvariantRecord,
    ProposalCreate,
    RevocationRequest,
    TokenCostRequest,
)
from .repositories import CoreRepository, ForbiddenError, RequestIdentity
from .repositories_paperclip import GovernanceDenied, PaperclipRepository
from .services.paperclip_envelope import EnvelopeError, EnvelopeSigner
from .services.synthetic_executor import SyntheticExecutor


def _parts(
    request: Request,
) -> tuple[Settings, Database, PaperclipDatabase, CoreRepository]:
    return (
        cast(Settings, request.app.state.settings),
        cast(Database, request.app.state.database),
        cast(PaperclipDatabase, request.app.state.paperclip_database),
        cast(CoreRepository, request.app.state.repository),
    )


def _identity(
    connection: Any, settings: Settings, subject: AuthenticatedSubject, repository: CoreRepository
) -> RequestIdentity:
    return repository.resolve_identity(
        connection, settings.platform_id, subject.external_subject
    )


def _service(
    settings: Settings, paperclip_database: PaperclipDatabase
) -> Any:
    from .services.paperclip import PaperclipService

    repository = PaperclipRepository(paperclip_database)
    signer = EnvelopeSigner(
        settings.paperclip_envelope_signing_key.reveal().encode("utf-8"),
        max_ttl_seconds=settings.paperclip_envelope_ttl_seconds,
    )
    executor = SyntheticExecutor(repository)
    return PaperclipService(repository, signer, executor, settings)


def _reject(exc: Exception) -> HTTPException:
    if isinstance(exc, ForbiddenError):
        return HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Governance request rejected", "retryable": False},
        )
    if isinstance(exc, GovernanceDenied):
        return HTTPException(
            status_code=403,
            detail={"code": "GOVERNANCE_DENIED", "message": "Governance request rejected", "retryable": False},
        )
    return HTTPException(
        status_code=409,
        detail={"code": "GOVERNANCE_CONFLICT", "message": "Governance request rejected", "retryable": False},
    )


def register_paperclip_routes(
    application: FastAPI,
    subject_dependency: Any,
    correlation: Any,
) -> None:
    @application.post(
        "/api/v1/governance/proposals",
        response_model=GovernanceResponse,
        responses={
            401: {"model": dict},
            403: {"model": dict},
            409: {"model": dict},
            422: {"model": dict},
            503: {"model": dict},
        },
    )
    def create_proposal(
        body: ProposalCreate,
        request: Request,
        idempotency_key: str = Header(
            ..., alias="Idempotency-Key", min_length=16, max_length=128
        ),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                result = service.create_proposal(
                    subject,
                    body.action_key,
                    body.target_system,
                    body.entity_type,
                    body.entity_id,
                    body.payload,
                    idempotency_key,
                    body.expires_at,
                    correlation_id,
                )
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        signed = None
        if result.allowed and result.governance_id is not None:
            signed = service.issue_proposal_envelope(
                subject, result.governance_id, body.action_key, body.target_system,
                body.entity_type, body.entity_id, body.payload,
            ).to_string()
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
            envelope=signed,
        )

    @application.post(
        "/api/v1/governance/proposals/{proposal_id}/invariants",
        response_model=GovernanceResponse,
    )
    def record_invariant(
        proposal_id: UUID,
        body: InvariantRecord,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                service.record_invariant(
                    subject, identity, proposal_id, body.invariant_code, body.passed
                )
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=True,
            reason_code="INVARIANT_RECORDED",
            governance_id=proposal_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/proposals/{proposal_id}/decision-lock",
        response_model=GovernanceResponse,
    )
    def acquire_decision_lock(
        proposal_id: UUID,
        body: DecisionLockRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                result = service.acquire_decision_lock(
                    subject, identity, proposal_id, body.reason
                )
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.delete(
        "/api/v1/governance/proposals/{proposal_id}/decision-lock",
        response_model=GovernanceResponse,
    )
    def release_decision_lock(
        proposal_id: UUID,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                result = service.release_decision_lock(subject, identity, proposal_id)
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/proposals/{proposal_id}/decisions",
        response_model=GovernanceResponse,
    )
    def decide(
        proposal_id: UUID,
        body: HumanDecisionRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                result = service.decide(
                    subject,
                    identity,
                    proposal_id,
                    body.decision == "approved",
                    body.expires_at,
                )
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/proposals/{proposal_id}/grants",
        response_model=GovernanceResponse,
    )
    def issue_grant(
        proposal_id: UUID,
        request: Request,
        envelope: str = Header(..., alias="X-Governance-Envelope"),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                signed_proposal = service._signer.verify_string(
                    envelope, purpose=EnvelopeSigner.PURPOSE_PROPOSAL,
                    tenant_id=settings.platform_id, proposal_id=proposal_id,
                )
                if (settings.paperclip_agent_bindings.get(signed_proposal.subject) != signed_proposal.agent_id
                        or signed_proposal.policy_id != settings.paperclip_policy_id):
                    raise GovernanceDenied("ENVELOPE_MAPPING_MISMATCH")
                result = service.issue_grant(subject, identity, proposal_id)
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        signed = None
        if result.allowed and result.governance_id is not None:
            signed = service._signer.issue(
                tenant_id=settings.platform_id, subject=settings.paperclip_executor_subject,
                agent_id=signed_proposal.agent_id, policy_id=settings.paperclip_policy_id,
                proposal_id=proposal_id, grant_id=result.governance_id,
                action=signed_proposal.action, target_system=signed_proposal.target_system,
                entity_type=signed_proposal.entity_type, entity_id=signed_proposal.entity_id,
                payload_hash=signed_proposal.payload_hash, purpose=EnvelopeSigner.PURPOSE_GRANT,
                ttl_seconds=settings.paperclip_envelope_ttl_seconds,
            ).to_string()
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
            envelope=signed,
        )

    @application.post(
        "/api/v1/governance/grants/{grant_id}/revocations",
        response_model=GovernanceResponse,
    )
    def revoke_grant(
        grant_id: UUID,
        body: RevocationRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                result = service.revoke_grant(subject, identity, grant_id, body.reason)
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/grants/{grant_id}/consumption",
        response_model=GrantConsumeResponse,
    )
    def consume_grant(
        grant_id: UUID,
        request: Request,
        envelope: str = Header(..., alias="X-Governance-Envelope"),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GrantConsumeResponse:
        settings, _database, paperclip_database, _core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            service = _service(settings, paperclip_database)
            result = service.consume_grant(subject, envelope, grant_id)
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GrantConsumeResponse(
            consumed=result.allowed,
            reason_code=result.reason_code,
            synthetic_result="synthetic-success" if result.allowed else None,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/grants/{grant_id}/attempts",
        response_model=GovernanceResponse,
    )
    def record_execution_attempt(
        grant_id: UUID,
        body: ExecutionAttemptRequest,
        request: Request,
        envelope: str = Header(..., alias="X-Governance-Envelope"),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, _database, paperclip_database, _core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            service = _service(settings, paperclip_database)
            result = service.record_execution_attempt(
                subject,
                envelope,
                body.request_fingerprint,
                body.status,
                grant_id,
            )
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/heartbeats",
        response_model=GovernanceResponse,
    )
    def record_heartbeat(
        body: HeartbeatRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, _database, paperclip_database, _core_repository = _parts(request)
        correlation_id = correlation(request)
        task_id = UUID(body.task_key) if body.task_key else None
        try:
            service = _service(settings, paperclip_database)
            result = service.record_heartbeat(
                subject, task_id, body.run_key
            )
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/token-costs",
        response_model=GovernanceResponse,
    )
    def record_token_cost(
        body: TokenCostRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, _database, paperclip_database, _core_repository = _parts(request)
        correlation_id = correlation(request)
        heartbeat_id = None
        try:
            service = _service(settings, paperclip_database)
            result = service.record_token_cost(subject, heartbeat_id, body.cost_usd)
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/governance/proposals/{proposal_id}/loop-guard",
        response_model=GovernanceResponse,
    )
    def evaluate_loop_guard(
        proposal_id: UUID,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> GovernanceResponse:
        settings, database, paperclip_database, core_repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, settings, subject, core_repository)
                service = _service(settings, paperclip_database)
                result = service.evaluate_loop_guard(subject, identity, proposal_id)
        except (ForbiddenError, GovernanceDenied, EnvelopeError) as exc:
            raise _reject(exc) from exc
        return GovernanceResponse(
            allowed=result.allowed,
            reason_code=result.reason_code,
            governance_id=result.governance_id,
            correlation_id=correlation_id,
        )
