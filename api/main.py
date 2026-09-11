"""FastAPI command boundary for the deterministic M3 operational core."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from psycopg import OperationalError

from .auth import AuthenticatedSubject, authenticate_subject, security
from .config import Settings, load_settings
from .database import Database
from .models.core import (
    ErrorEnvelope,
    OrderAccepted,
    OrderCreate,
    TransitionRequest,
    TransitionResponse,
)
from .pricing import calculate_price
from .repositories import (
    ConflictError,
    CoreRepository,
    ForbiddenError,
    canonical_fingerprint,
)


def _correlation_id(request: Request) -> UUID:
    return cast(UUID, request.state.correlation_id)


def _error(
    status: int,
    code: str,
    message: str,
    correlation_id: UUID,
    retryable: bool,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "correlation_id": str(correlation_id),
        "retryable": retryable,
    }
    if details:
        error["details"] = details
    return JSONResponse(status_code=status, content={"error": error})


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
    repository: CoreRepository | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        selected_settings = settings or load_settings()
        selected_database = database or Database(selected_settings.database_url)
        application.state.settings = selected_settings
        application.state.database = selected_database
        application.state.repository = repository or CoreRepository()
        selected_database.open()
        yield
        selected_database.close()

    application = FastAPI(
        title="Zippy Logistics API", version="3.0.0", lifespan=lifespan
    )

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            correlation_id = UUID(request.headers.get("X-Correlation-ID", ""))
        except ValueError:
            correlation_id = uuid4()
        request.state.correlation_id = correlation_id
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(correlation_id)
        response.headers["X-Response-Time"] = (
            f"{int((time.monotonic() - started) * 1000)}ms"
        )
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        malformed = any(error["type"] == "json_invalid" for error in exc.errors())
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "code": error["type"],
            }
            for error in exc.errors()
        ]
        return _error(
            400 if malformed else 422,
            "MALFORMED_REQUEST" if malformed else "VALIDATION_FAILED",
            "Request body is malformed" if malformed else "Request validation failed",
            _correlation_id(request),
            False,
            details,
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {
                "code": "REQUEST_REJECTED",
                "message": str(exc.detail),
                "retryable": False,
            }
        )
        code = detail.get("code", "REQUEST_REJECTED")
        message = detail.get("message", "Request rejected")
        return _error(
            exc.status_code,
            code if isinstance(code, str) else "REQUEST_REJECTED",
            message if isinstance(message, str) else "Request rejected",
            _correlation_id(request),
            bool(detail.get("retryable", False)),
        )

    @application.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, OperationalError):
            return _error(
                503,
                "DATABASE_UNAVAILABLE",
                "The service is temporarily unavailable",
                _correlation_id(request),
                True,
            )
        return _error(
            500,
            "INTERNAL_ERROR",
            "An internal error occurred",
            _correlation_id(request),
            True,
        )

    @application.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/v1/ready", response_model=None)
    def ready(request: Request) -> dict[str, str] | JSONResponse:
        selected_database = cast(Database, request.app.state.database)
        if not selected_database.ready():
            return _error(
                503,
                "NOT_READY",
                "The service is not ready",
                _correlation_id(request),
                True,
            )
        return {"status": "ready"}

    def subject_dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    ) -> AuthenticatedSubject:
        return authenticate_subject(request, credentials)

    @application.post(
        "/api/v1/orders",
        response_model=OrderAccepted,
        status_code=202,
        responses={
            400: {"model": ErrorEnvelope},
            401: {"model": ErrorEnvelope},
            403: {"model": ErrorEnvelope},
            409: {"model": ErrorEnvelope},
            422: {"model": ErrorEnvelope},
            503: {"model": ErrorEnvelope},
        },
    )
    def create_order(
        order: OrderCreate,
        request: Request,
        idempotency_key: str = Header(
            ..., alias="Idempotency-Key", min_length=16, max_length=128
        ),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> OrderAccepted:
        selected_settings = cast(Settings, request.app.state.settings)
        selected_database = cast(Database, request.app.state.database)
        selected_repository = cast(CoreRepository, request.app.state.repository)
        correlation_id = _correlation_id(request)
        quote = calculate_price(order, selected_settings)
        try:
            with selected_database.transaction(
                selected_settings.platform_id
            ) as connection:
                identity = selected_repository.resolve_identity(
                    connection, selected_settings.platform_id, subject.external_subject
                )
                return selected_repository.create_order(
                    connection,
                    identity,
                    order,
                    quote,
                    idempotency_key,
                    correlation_id,
                    canonical_fingerprint(order),
                    selected_settings.task_max_attempts,
                )
        except ConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "IDEMPOTENCY_CONFLICT",
                    "message": str(exc),
                    "retryable": False,
                },
            ) from exc
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": str(exc), "retryable": False},
            ) from exc

    @application.post(
        "/api/v1/orders/{order_id}/transitions",
        response_model=TransitionResponse,
        responses={
            401: {"model": ErrorEnvelope},
            403: {"model": ErrorEnvelope},
            409: {"model": ErrorEnvelope},
            422: {"model": ErrorEnvelope},
            503: {"model": ErrorEnvelope},
        },
    )
    def transition_order(
        order_id: UUID,
        command: TransitionRequest,
        request: Request,
        idempotency_key: str = Header(
            ..., alias="Idempotency-Key", min_length=16, max_length=128
        ),
        subject: AuthenticatedSubject = Depends(subject_dependency),  # noqa: B008
    ) -> TransitionResponse:
        selected_settings = cast(Settings, request.app.state.settings)
        selected_database = cast(Database, request.app.state.database)
        selected_repository = cast(CoreRepository, request.app.state.repository)
        try:
            with selected_database.transaction(
                selected_settings.platform_id
            ) as connection:
                identity = selected_repository.resolve_identity(
                    connection, selected_settings.platform_id, subject.external_subject
                )
                return selected_repository.transition_order(
                    connection,
                    identity,
                    order_id,
                    command,
                    idempotency_key,
                    _correlation_id(request),
                )
        except ConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "TRANSITION_CONFLICT",
                    "message": str(exc),
                    "retryable": False,
                },
            ) from exc
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": str(exc), "retryable": False},
            ) from exc

    return application


app = create_app()
