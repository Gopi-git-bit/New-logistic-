"""M4 operations-finance routes: Razorpay sandbox webhook, POD gate, refunds.

The webhook endpoint is public and HMAC-gated; it operates on the exact raw
request body and fails closed when the secret, signature, or provider event
ID is missing. All other routes use the standard subject dependency and the
PostgreSQL authorization path.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from .auth import AuthenticatedSubject
from .config import Settings
from .database import Database
from .gateway import (
    MalformedEventError,
    parse_event,
    payload_hash,
    verify_signature,
)
from .models.finance import (
    PodDecisionRequest,
    PodDecisionResponse,
    PodSubmission,
    PodSubmissionResponse,
    RefundDecisionBody,
    RefundDecisionResponse,
    RefundExecutionBody,
    RefundExecutionResponse,
    RefundRequestBody,
    RefundResponse,
    SettlementEvaluationResponse,
    WebhookReceiptResponse,
)
from .repositories import ConflictError, CoreRepository, ForbiddenError, RequestIdentity
from .repositories_finance import FinanceRepository


def register_finance_routes(
    application: FastAPI,
    subject_dependency: Any,
    correlation: Any,
) -> None:
    def _parts(request: Request) -> tuple[Settings, Database, FinanceRepository]:
        return (
            cast(Settings, request.app.state.settings),
            cast(Database, request.app.state.database),
            cast(FinanceRepository, request.app.state.finance_repository),
        )

    def _reject(exc: Exception) -> HTTPException:
        if isinstance(exc, ForbiddenError):
            return HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": str(exc), "retryable": False},
            )
        return HTTPException(
            status_code=409,
            detail={"code": "FINANCE_CONFLICT", "message": str(exc), "retryable": False},
        )

    @application.post("/api/v1/webhooks/razorpay", response_model=WebhookReceiptResponse)
    async def razorpay_webhook(request: Request) -> WebhookReceiptResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        if not settings.razorpay_webhook_secret:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "WEBHOOK_NOT_CONFIGURED",
                    "message": "Webhook verification is not configured",
                    "retryable": True,
                },
            )
        raw = await request.body()
        signature = request.headers.get("X-Razorpay-Signature")
        if not verify_signature(raw, signature, settings.razorpay_webhook_secret):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "INVALID_SIGNATURE",
                    "message": "Webhook signature verification failed",
                    "retryable": False,
                },
            )
        try:
            event = parse_event(raw)
        except MalformedEventError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "MALFORMED_EVENT",
                    "message": str(exc),
                    "retryable": False,
                },
            ) from exc
        # Defensive re-check: the persisted evidence hash must be the hash of
        # the exact raw body that passed signature verification.
        if event.evidence_hash != payload_hash(raw):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "MALFORMED_EVENT",
                    "message": "event evidence does not match the raw body",
                    "retryable": False,
                },
            )
        with database.transaction(settings.platform_id) as connection:
            outcome = repository.ingest_gateway_event(
                connection,
                settings.platform_id,
                event,
                correlation_id,
                settings.task_max_attempts,
            )
        return WebhookReceiptResponse(
            receipt_id=outcome.receipt_id,
            duplicate=outcome.duplicate,
            outcome=outcome.outcome,
            correlation_id=outcome.correlation_id,
        )

    @application.post("/api/v1/orders/{order_id}/pod", response_model=PodSubmissionResponse)
    def submit_pod(
        order_id: UUID,
        submission: PodSubmission,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> PodSubmissionResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = repository_identity(connection, request, subject)
                pod_id, status, duplicate = repository.submit_pod(
                    connection,
                    identity,
                    order_id,
                    submission.object_key,
                    submission.content_type,
                    submission.byte_size,
                    submission.checksum_sha256,
                    correlation_id,
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return PodSubmissionResponse(
            pod_document_id=pod_id,
            verification_status=status,
            duplicate=duplicate,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/pod/{pod_document_id}/verification", response_model=PodDecisionResponse
    )
    def decide_pod(
        pod_document_id: UUID,
        decision: PodDecisionRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> PodDecisionResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = repository_identity(connection, request, subject)
                status, projection_id = repository.decide_pod(
                    connection,
                    identity,
                    pod_document_id,
                    decision.decision,
                    decision.reason,
                    correlation_id,
                    settings.task_max_attempts,
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return PodDecisionResponse(
            pod_document_id=pod_document_id,
            verification_status=status,
            settlement_projection_id=projection_id,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/orders/{order_id}/settlement-evaluation",
        response_model=SettlementEvaluationResponse,
    )
    def evaluate_settlement(
        order_id: UUID,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> SettlementEvaluationResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = repository_identity(connection, request, subject)
                result = repository.evaluate_settlement(
                    connection, identity, order_id, correlation_id
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return SettlementEvaluationResponse(
            order_id=result.order_id,
            eligible=result.eligible,
            settlement_projection_id=result.settlement_projection_id,
            reason=result.reason,
            correlation_id=correlation_id,
        )

    @application.post("/api/v1/orders/{order_id}/refunds", response_model=RefundResponse)
    def request_refund(
        order_id: UUID,
        body: RefundRequestBody,
        request: Request,
        idempotency_key: str = Header(
            ..., alias="Idempotency-Key", min_length=16, max_length=128
        ),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> RefundResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = repository_identity(connection, request, subject)
                refund_id, status, duplicate = repository.request_refund(
                    connection,
                    identity,
                    order_id,
                    body.amount,
                    body.currency_code,
                    body.target_reference,
                    body.reason,
                    idempotency_key,
                    correlation_id,
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return RefundResponse(
            refund_request_id=refund_id,
            status=status,
            duplicate=duplicate,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/refunds/{refund_request_id}/decision", response_model=RefundDecisionResponse
    )
    def decide_refund(
        refund_request_id: UUID,
        body: RefundDecisionBody,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> RefundDecisionResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = repository_identity(connection, request, subject)
                decision_id, status = repository.decide_refund(
                    connection,
                    identity,
                    refund_request_id,
                    body.decision,
                    body.reason,
                    correlation_id,
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return RefundDecisionResponse(
            refund_request_id=refund_request_id,
            refund_decision_id=decision_id,
            status=status,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/refunds/{refund_request_id}/execution", response_model=RefundExecutionResponse
    )
    def record_refund_execution(
        refund_request_id: UUID,
        body: RefundExecutionBody,
        request: Request,
        idempotency_key: str = Header(
            ..., alias="Idempotency-Key", min_length=16, max_length=128
        ),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> RefundExecutionResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = repository_identity(connection, request, subject)
                execution_id, status = repository.record_refund_execution(
                    connection,
                    identity,
                    refund_request_id,
                    body.gateway_refund_id,
                    body.evidence_hash_sha256,
                    body.executed_at,
                    idempotency_key,
                    correlation_id,
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return RefundExecutionResponse(
            refund_request_id=refund_request_id,
            refund_execution_id=execution_id,
            status=status,
            correlation_id=correlation_id,
        )


def repository_identity(
    connection: Any, request: Request, subject: AuthenticatedSubject
) -> RequestIdentity:
    """Resolve the PostgreSQL-backed identity inside the active transaction."""
    settings = cast(Settings, request.app.state.settings)
    return CoreRepository().resolve_identity(
        connection, settings.platform_id, subject.external_subject
    )
