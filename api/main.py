"""Zippy Logistics — FastAPI Application.

Canonical application API layer. Handles:
1. Authentication & authorization (Supabase JWT + RBAC)
2. Schema validation
3. Idempotency (atomic via INSERT ON CONFLICT)
4. Correlation IDs
5. Rate limiting
6. Database RPC calls
7. Background task enqueueing
8. Deterministic responses
9. Paperclip → Hermes governance enforcement
10. POD verification lifecycle (persisted to DB)

FastAPI must NOT perform unrestricted agent reasoning inside synchronous request handlers.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import UserIdentity, get_current_user, require_role, UserRole
from .config import load_settings, validate_required, validate_production_security
from .idempotency import IdempotencyStore
from .pod_lifecycle import (
    PODStatus,
    PODStore,
    can_transition,
    next_status,
    requires_paperclip,
)
from .redaction import redact_dict
from .services.paperclip import Decision, PaperclipClient, Proposal
from .services.hermes import ExecutionStatus, HermesClient


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------
class OrderCreate(BaseModel):
    """Order creation request."""
    pickup_location: dict[str, Any] = Field(..., description="GeoJSON Point")
    delivery_location: dict[str, Any] = Field(..., description="GeoJSON Point")
    cargo_type: str = Field(..., min_length=1, max_length=100)
    cargo_weight_kg: float = Field(..., gt=0)
    vehicle_type: str = Field(..., description="LCV/MCV/HCV")
    body_type: str = Field(..., description="Open Body/Closed Body")
    payment_mode: str = Field(..., description="full/partial/to_pay")
    advance_amount: Optional[float] = Field(None, ge=0)
    idempotency_key: str = Field(..., min_length=16, max_length=128)


class OrderResponse(BaseModel):
    """Order creation response."""
    order_id: str
    status: str
    total_amount: Optional[float] = None
    idempotency_key: str
    correlation_id: str
    pod_status: str = PODStatus.UPLOADED.value


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: dict[str, Any]


class PODVerifyResponse(BaseModel):
    """POD verification response."""
    order_id: str
    pod_status: str
    correlation_id: str
    paperclip_decision_id: Optional[str] = None
    hermes_execution_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration on startup and initialise service clients."""
    settings = load_settings()
    missing = validate_required(settings)
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    warnings = validate_production_security(settings)
    if warnings:
        import sys
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)

    app.state.settings = settings
    app.state.idempotency = IdempotencyStore(
        settings.supabase_url, settings.supabase_service_role_key
    )
    app.state.pod_store = PODStore(
        settings.supabase_url, settings.supabase_service_role_key
    )
    app.state.paperclip = PaperclipClient(
        settings.paperclip_url, settings.paperclip_api_key
    )
    app.state.hermes = HermesClient(
        settings.hermes_api_url, settings.hermes_api_key
    )
    yield
    app.state.idempotency.close()
    app.state.pod_store.close()
    app.state.paperclip.close()
    app.state.hermes.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Zippy Logistics API",
    version="1.0.0",
    description="Canonical application API layer",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware: Correlation ID + Timing
# ---------------------------------------------------------------------------
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
    return response


# ---------------------------------------------------------------------------
# Health & Readiness
# ---------------------------------------------------------------------------
@app.get("/api/v1/health")
async def health():
    """Liveness check — process is alive."""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/api/v1/ready")
async def ready():
    """Readiness check — required dependencies available."""
    settings = app.state.settings
    checks = {}
    all_ok = True

    # Database
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={"apikey": settings.next_public_supabase_anon_key or ""},
            )
            checks["database"] = "ok" if resp.status_code < 500 else "error"
    except Exception:
        checks["database"] = "error"
        all_ok = False

    # Paperclip
    if settings.paperclip_url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.paperclip_url}/health")
                checks["paperclip"] = "ok" if resp.status_code < 500 else "error"
        except Exception:
            checks["paperclip"] = "unavailable"
    else:
        checks["paperclip"] = "not_configured"

    # Hermes
    if settings.hermes_api_url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.hermes_api_url}/health")
                checks["hermes"] = "ok" if resp.status_code < 500 else "error"
        except Exception:
            checks["hermes"] = "unavailable"
    else:
        checks["hermes"] = "not_configured"

    # Langfuse (optional — fail open)
    checks["langfuse"] = "configured" if settings.langfuse_public_key else "not_configured"

    # Honcho (optional — fail open)
    checks["honcho"] = "configured" if settings.honcho_api_url else "not_configured"

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _new_id() -> str:
    return str(uuid.uuid4())


async def _insert_order(
    settings: Any,
    order: OrderCreate,
    order_id: str,
    user: UserIdentity,
) -> dict:
    """Insert order row into Supabase via REST API. Returns the row."""
    payload = {
        "id": order_id,
        "customer_id": user.user_id,
        "pickup_lat": order.pickup_location.get("coordinates", [0, 0])[1],
        "pickup_lng": order.pickup_location.get("coordinates", [0, 0])[0],
        "delivery_lat": order.delivery_location.get("coordinates", [0, 0])[1],
        "delivery_lng": order.delivery_location.get("coordinates", [0, 0])[0],
        "cargo_type": order.cargo_type,
        "cargo_weight_kg": order.cargo_weight_kg,
        "vehicle_type": order.vehicle_type,
        "body_type": order.body_type,
        "payment_mode": order.payment_mode,
        "advance_amount": order.advance_amount or 0,
        "status": "pending",
        "pod_status": PODStatus.UPLOADED.value,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/orders",
            json=payload,
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else payload


# ---------------------------------------------------------------------------
# Orders — POST (Create)
# ---------------------------------------------------------------------------
@app.post(
    "/api/v1/orders",
    response_model=OrderResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_order(
    order: OrderCreate,
    request: Request,
    x_correlation_id: Optional[str] = Header(None),
    user: UserIdentity = Depends(require_role(UserRole.CUSTOMER, UserRole.ADMIN)),
):
    """Create a new order. Requires idempotency key and JWT auth.

    Flow:
    1. Atomic idempotency claim (INSERT ON CONFLICT)
    2. Persist order to DB
    3. Mark idempotency complete
    4. On failure — mark idempotency failed, return deterministic error
    """
    correlation_id = x_correlation_id or _new_id()
    idempotency_store: IdempotencyStore = request.app.state.idempotency

    # 1. Atomic idempotency claim
    claimed, existing = idempotency_store.claim(
        order.idempotency_key,
        resource_type="order",
        payload=order.model_dump(),
    )
    if not claimed and existing.found:
        # Return the stored response for deterministic replay
        resp_data = existing.response_data or {}
        return OrderResponse(
            order_id=resp_data.get("order_id", ""),
            status=resp_data.get("status", "pending"),
            idempotency_key=order.idempotency_key,
            correlation_id=correlation_id,
            pod_status=resp_data.get("pod_status", PODStatus.UPLOADED.value),
        )

    # 2. Persist order to DB
    order_id = _new_id()
    try:
        settings = request.app.state.settings
        row = await _insert_order(settings, order, order_id, user)
        order_id = row.get("id", order_id)
    except Exception as exc:
        # Mark idempotency as failed so retry can re-attempt
        idempotency_store.fail(
            order.idempotency_key, "order", f"DB insert failed: {type(exc).__name__}"
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "ORDER_PERSIST_FAILED",
                    "message": "Order could not be persisted. Please retry.",
                    "retryable": True,
                    "correlation_id": correlation_id,
                }
            },
        )

    # 3. Mark idempotency complete
    response_data = {
        "order_id": order_id,
        "status": "pending",
        "pod_status": PODStatus.UPLOADED.value,
    }
    idempotency_store.complete(
        order.idempotency_key, "order", response_data
    )

    return OrderResponse(
        order_id=order_id,
        status="pending",
        idempotency_key=order.idempotency_key,
        correlation_id=correlation_id,
        pod_status=PODStatus.UPLOADED.value,
    )


# ---------------------------------------------------------------------------
# Orders — GET
# ---------------------------------------------------------------------------
@app.get("/api/v1/orders/{order_id}")
async def get_order(
    order_id: str,
    request: Request,
    x_correlation_id: Optional[str] = Header(None),
    user: UserIdentity = Depends(get_current_user),
):
    """Get order by ID."""
    settings = request.app.state.settings
    correlation_id = x_correlation_id or _new_id()
    params = {"id": f"eq.{order_id}", "select": "*"}
    # The API uses a service credential, so tenant filtering MUST be explicit.
    # Admins may inspect any order; every other role is restricted to its own row.
    if user.active_role != UserRole.ADMIN:
        params["customer_id"] = f"eq.{user.user_id}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/orders",
                params=params,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "ORDER_STORE_TIMEOUT",
                    "message": "Order store timed out. Please retry.",
                    "retryable": True,
                    "correlation_id": correlation_id,
                }
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "ORDER_STORE_UNAVAILABLE",
                    "message": "Order store is unavailable. Please retry.",
                    "retryable": True,
                    "correlation_id": correlation_id,
                }
            },
        ) from exc

    if resp.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "ORDER_STORE_UNAVAILABLE",
                    "message": "Order store is unavailable. Please retry.",
                    "retryable": True,
                    "correlation_id": correlation_id,
                }
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="Order store rejected the request")

    data = resp.json()
    if not data:
        # Do not reveal whether another tenant owns this identifier.
        raise HTTPException(status_code=404, detail="Order not found")
    return data[0]


# ---------------------------------------------------------------------------
# POD Verification — POST
# ---------------------------------------------------------------------------
@app.post(
    "/api/v1/orders/{order_id}/pod/verify",
    response_model=PODVerifyResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def verify_pod(
    order_id: str,
    request: Request,
    x_correlation_id: Optional[str] = Header(None),
    user: UserIdentity = Depends(require_role(UserRole.DRIVER, UserRole.ADMIN)),
):
    """Verify POD and advance lifecycle. Enforces:
    - State machine transitions (cannot skip steps)
    - Paperclip governance required before DELIVERY_CONFIRMED → SETTLEMENT_ELIGIBLE
    - Hermes execution only after Paperclip APPROVE
    - All state changes persisted to DB
    """
    correlation_id = x_correlation_id or _new_id()
    pod_store: PODStore = request.app.state.pod_store
    paperclip: PaperclipClient = request.app.state.paperclip
    hermes: HermesClient = request.app.state.hermes

    # 1. Read current status from DB
    current_status = pod_store.get_order_status(order_id)
    if current_status is None:
        raise HTTPException(status_code=404, detail="Order not found")

    target = next_status(current_status)
    if target is None:
        raise HTTPException(
            status_code=409,
            detail=f"Order already in terminal state: {current_status.value}",
        )

    # 2. Validate transition
    if not can_transition(current_status, target):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition: {current_status.value} → {target.value}",
        )

    # 3. If this transition requires Paperclip → Hermes chain
    paperclip_decision_id = None
    hermes_execution_id = None

    if requires_paperclip(current_status, target):
        # 3a. Submit proposal to Paperclip
        proposal = Proposal(
            tool="update_delivery_status",
            arguments={
                "order_id": order_id,
                "from_status": current_status.value,
                "to_status": target.value,
                "driver_id": user.user_id,
            },
            agent="api",
            order_id=order_id,
            correlation_id=correlation_id,
        )
        decision = paperclip.evaluate(proposal)
        paperclip_decision_id = decision.decision_id

        if decision.decision != Decision.APPROVE:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "GOVERNANCE_REJECTED",
                        "message": f"Paperclip rejected: {decision.reason}",
                        "paperclip_decision_id": decision.decision_id,
                        "correlation_id": correlation_id,
                    }
                },
            )

        # 3b. Execute via Hermes (only after Paperclip APPROVE)
        exec_result = hermes.execute(
            tool="update_delivery_status",
            arguments={
                "order_id": order_id,
                "new_status": target.value,
            },
            decision_id=decision.decision_id,
            correlation_id=correlation_id,
        )
        hermes_execution_id = exec_result.execution_id

        if exec_result.status != ExecutionStatus.SUCCESS:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "HERMES_EXECUTION_FAILED",
                        "message": f"Hermes execution failed: {exec_result.error}",
                        "hermes_execution_id": exec_result.execution_id,
                        "correlation_id": correlation_id,
                    }
                },
            )

    # 4. Persist status transition to DB
    ok, msg = pod_store.advance_status(order_id, current_status, target)
    if not ok:
        raise HTTPException(status_code=409, detail=msg)

    return PODVerifyResponse(
        order_id=order_id,
        pod_status=target.value,
        correlation_id=correlation_id,
        paperclip_decision_id=paperclip_decision_id,
        hermes_execution_id=hermes_execution_id,
    )


# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Standard error envelope for all errors."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "retryable": True,
                "correlation_id": correlation_id,
            }
        },
    )
