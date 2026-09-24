"""M4 deterministic dispatch routes: offer creation, accept, decline, cancel."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from .auth import AuthenticatedSubject
from .config import Settings
from .database import Database
from .models.dispatch import (
    DispatchAssignmentResponse,
    DispatchOfferCreate,
    DispatchOfferDecisionRequest,
    DispatchOfferDecisionResponse,
    DispatchOfferResponse,
)
from .repositories import ConflictError, CoreRepository, ForbiddenError, RequestIdentity
from .repositories_dispatch import DispatchRepository


def register_dispatch_routes(
    application: FastAPI,
    subject_dependency: Any,
    correlation: Any,
) -> None:
    def _parts(request: Request) -> tuple[Settings, Database, DispatchRepository]:
        return (
            cast(Settings, request.app.state.settings),
            cast(Database, request.app.state.database),
            cast(DispatchRepository, request.app.state.dispatch_repository),
        )

    def _identity(connection: Any, request: Request, subject: AuthenticatedSubject) -> RequestIdentity:
        settings = cast(Settings, request.app.state.settings)
        return CoreRepository().resolve_identity(connection, settings.platform_id, subject.external_subject)

    def _reject(exc: Exception) -> HTTPException:
        if isinstance(exc, ForbiddenError):
            return HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": str(exc), "retryable": False},
            )
        return HTTPException(
            status_code=409,
            detail={"code": "DISPATCH_CONFLICT", "message": str(exc), "retryable": False},
        )

    @application.post(
        "/api/v1/orders/{order_id}/dispatch-offers", response_model=DispatchOfferResponse
    )
    def create_offer(
        order_id: UUID,
        body: DispatchOfferCreate,
        request: Request,
        idempotency_key: str = Header(
            ..., alias="Idempotency-Key", min_length=16, max_length=128
        ),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> DispatchOfferResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, request, subject)
                outcome = repository.create_dispatch_offer(
                    connection,
                    identity,
                    order_id,
                    body.vendor_profile_id,
                    body.vehicle_id,
                    body.driver_profile_id,
                    body.expires_at,
                    idempotency_key,
                    correlation_id,
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return DispatchOfferResponse(
            dispatch_offer_id=outcome.dispatch_offer_id,
            outcome=outcome.outcome,
            status=outcome.status,
            reason_code=outcome.reason_code,
            duplicate=outcome.duplicate,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/dispatch-offers/{dispatch_offer_id}/accept",
        response_model=DispatchAssignmentResponse,
    )
    def accept_offer(
        dispatch_offer_id: UUID,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> DispatchAssignmentResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            # Committed on its own: persisting an overdue expiry must survive
            # even when the accept attempt below is rejected and rolled back.
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, request, subject)
                repository.expire_if_due(connection, identity.platform_id, dispatch_offer_id)
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, request, subject)
                outcome = repository.accept_dispatch_offer(
                    connection, identity, dispatch_offer_id, identity.account_id, correlation_id
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return DispatchAssignmentResponse(
            dispatch_offer_id=outcome.dispatch_offer_id,
            trip_id=outcome.trip_id,
            trip_assignment_id=outcome.trip_assignment_id,
            order_status=outcome.order_status,
            duplicate=outcome.duplicate,
            correlation_id=correlation_id,
        )

    @application.post(
        "/api/v1/dispatch-offers/{dispatch_offer_id}/decline",
        response_model=DispatchOfferDecisionResponse,
    )
    def decline_offer(
        dispatch_offer_id: UUID,
        body: DispatchOfferDecisionRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> DispatchOfferDecisionResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, request, subject)
                status = repository.decline_dispatch_offer(
                    connection, identity, dispatch_offer_id, body.reason, correlation_id
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return DispatchOfferDecisionResponse(
            dispatch_offer_id=dispatch_offer_id, status=status, correlation_id=correlation_id
        )

    @application.post(
        "/api/v1/dispatch-offers/{dispatch_offer_id}/cancel",
        response_model=DispatchOfferDecisionResponse,
    )
    def cancel_offer(
        dispatch_offer_id: UUID,
        body: DispatchOfferDecisionRequest,
        request: Request,
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> DispatchOfferDecisionResponse:
        settings, database, repository = _parts(request)
        correlation_id = correlation(request)
        try:
            with database.transaction(settings.platform_id) as connection:
                identity = _identity(connection, request, subject)
                status = repository.cancel_dispatch_offer(
                    connection, identity, dispatch_offer_id, body.reason, correlation_id
                )
        except (ForbiddenError, ConflictError) as exc:
            raise _reject(exc) from exc
        return DispatchOfferDecisionResponse(
            dispatch_offer_id=dispatch_offer_id, status=status, correlation_id=correlation_id
        )
