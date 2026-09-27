"""Request/response models for the M5-B authenticated Paperclip governance service."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_key: str = Field(..., pattern=r"^[A-Z][A-Z0-9_]{1,63}$")
    target_system: Literal["ZIPPY", "ODOO", "EXTERNAL", "PAPERCLIP"]
    entity_type: str = Field(..., pattern=r"^[a-z][a-z0-9_.]{0,63}$")
    entity_id: str = Field(..., min_length=1, max_length=160)
    payload: dict[str, Any]
    idempotency_key: str = Field(..., min_length=1, max_length=200)
    expires_at: datetime


class InvariantRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invariant_code: str = Field(..., min_length=1, max_length=80)
    passed: bool


class DecisionLockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)


class HumanDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    reason: str = Field(..., min_length=1, max_length=1000)
    expires_at: datetime


class RevocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)


class ExecutionAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    status: Literal["CONSUMED", "ATTEMPTED", "SUCCEEDED", "FAILED"]


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_key: str | None = Field(default=None, min_length=1, max_length=160)
    run_key: str = Field(..., min_length=1, max_length=160)


class TokenCostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cost_usd: Decimal = Field(..., ge=Decimal(0), max_digits=14, decimal_places=6)
    run_key: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator("cost_usd")
    @classmethod
    def _finite_cost(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("cost_usd must be finite")
        return value


class GovernanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reason_code: str
    governance_id: UUID | None
    correlation_id: UUID
    envelope: str | None = Field(default=None, repr=False)


class GrantConsumeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumed: bool
    reason_code: str
    synthetic_result: str | None
    correlation_id: UUID
