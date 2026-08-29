"""Zippy Logistics — FastAPI Application.

Canonical application API layer. Handles:
1. Authentication & authorization
2. Schema validation
3. Idempotency
4. Correlation IDs
5. Rate limiting
6. Database RPC calls
7. Background task enqueueing
8. Deterministic responses

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

from .config import load_settings, validate_required, validate_production_security
from .redaction import redact_dict


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
    yield


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
            # Paperclip is critical but not for readiness
    else:
        checks["paperclip"] = "not_configured"

    # Hermes
    if settings.herMES_api_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.herMES_api_url}/health")
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
# Orders
# ---------------------------------------------------------------------------
@app.post("/api/v1/orders")
async def create_order(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None),
    x_correlation_id: Optional[str] = Header(None),
    x_agent_id: Optional[str] = Header(None),
    x_decision_id: Optional[str] = Header(None),
):
    """Create a new order. Requires idempotency key for state-changing ops."""
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")

    body = await request.json()
    settings = app.state.settings

    # TODO: Validate request schema
    # TODO: Check idempotency in webhook_events table
    # TODO: Call Supabase RPC via service role
    # TODO: Enqueue background task

    return {
        "order_id": str(uuid.uuid4()),
        "status": "pending",
        "idempotency_key": x_idempotency_key,
        "correlation_id": x_correlation_id or str(uuid.uuid4()),
    }


@app.get("/api/v1/orders/{order_id}")
async def get_order(
    order_id: str,
    x_correlation_id: Optional[str] = Header(None),
):
    """Get order by ID."""
    # TODO: Call Supabase RPC
    return {"order_id": order_id, "status": "pending"}


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
