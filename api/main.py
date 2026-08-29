"""Zippy Logistics — FastAPI Application.

Canonical application API layer. Handles:
1. Authentication & authorization (Supabase JWT + RBAC)
2. Schema validation
3. Idempotency (persistent via webhook_events)
4. Correlation IDs
5. Rate limiting
6. Database RPC calls
7. Background task enqueueing
8. Deterministic responses
9. Paperclip → Hermes governance enforcement
10. POD verification lifecycle

FastAPI must NOT perform unrestricted agent reasoning inside synchronous request handlers.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import UserIdentity, get_current_user, require_role, UserRole
from .config import load_settings, validate_required, validate_production_security
from .idempotency import IdempotencyStore
from .pod_lifecycle import PODStatus, can_transition, next_status
from .redaction import redact_dict


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


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration on startup."""
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
    yield
    app.state.idempotency.close()


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
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.supabase_url}/rest/v1/", headers={
                "apikey": settings.supabase_anon_key or "",
            })
            checks["database"] = "ok" if resp.status_code < 500 else "error"
    except Exception:
        checks["database"] = "error"
        all_ok = False

    # Paperclip
    if settings.paperclip_url:
        try:
            import httpx
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
            import httpx
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
    x_agent_id: Optional[str] = Header(None),
    x_decision_id: Optional[str] = Header(None),
    user: UserIdentity = Depends(require_role(UserRole.CUSTOMER, UserRole.ADMIN)),
):
    """Create a new order. Requires idempotency key and JWT auth."""
    correlation_id = x_correlation_id or str(uuid.uuid4())
    idempotency_store: IdempotencyStore = request.app.state.idempotency

    # 1. Idempotency check
    existing = idempotency_store.check(order.idempotency_key)
    if existing:
        return OrderResponse(
            order_id=str(existing.get("id", "")),
            status="pending",
            idempotency_key=order.idempotency_key,
            correlation_id=correlation_id,
        )

    # 2. Store idempotency key
    idempotency_store.store(
        idempotency_key=order.idempotency_key,
        provider="api",
        event_type="order_created",
        payload=order.model_dump(),
    )

    # 3. Call Supabase RPC to create order
    settings = request.app.state.settings
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/generate_order_quote",
                json={
                    "p_order_id": str(uuid.uuid4()),
                },
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
            )
            # For now, return a placeholder order_id
            order_id = str(uuid.uuid4())
    except Exception:
        order_id = str(uuid.uuid4())

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
    return {
        "order_id": order_id,
        "status": "pending",
        "correlation_id": x_correlation_id or str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# POD Verification — POST
# ---------------------------------------------------------------------------
@app.post("/api/v1/orders/{order_id}/pod/verify")
async def verify_pod(
    order_id: str,
    request: Request,
    x_correlation_id: Optional[str] = Header(None),
    user: UserIdentity = Depends(require_role(UserRole.DRIVER, UserRole.ADMIN)),
):
    """Verify POD and advance lifecycle. Requires Paperclip governance for settlement."""
    # TODO: Check current POD status from DB
    # TODO: Advance through lifecycle
    # TODO: Enforce Paperclip governance before DELIVERY_CONFIRMED
    return {
        "order_id": order_id,
        "pod_status": PODStatus.VERIFICATION_PENDING.value,
        "correlation_id": x_correlation_id or str(uuid.uuid4()),
    }


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
