"""Request/response models for the M4 operations-finance boundary."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PodSubmission(BaseModel):
    object_key: str = Field(..., min_length=8, max_length=512)
    content_type: str = Field(..., min_length=3, max_length=100)
    byte_size: int = Field(..., gt=0)
    checksum_sha256: str = Field(..., pattern="^[0-9a-f]{64}$")


class PodDecisionRequest(BaseModel):
    decision: Literal["accepted", "rejected", "manual_review"]
    reason: str = Field(..., min_length=3, max_length=1000)


class RefundRequestBody(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency_code: str = Field(..., pattern="^[A-Z]{3}$")
    target_reference: str = Field(..., min_length=3, max_length=200)
    reason: str = Field(..., min_length=3, max_length=1000)


class RefundDecisionBody(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(..., min_length=3, max_length=1000)


class RefundExecutionBody(BaseModel):
    gateway_refund_id: str = Field(..., min_length=3, max_length=200)
    evidence_hash_sha256: str = Field(..., pattern="^[0-9a-f]{64}$")
    executed_at: datetime


class WebhookReceiptResponse(BaseModel):
    receipt_id: UUID
    duplicate: bool
    outcome: str
    correlation_id: UUID


class PodSubmissionResponse(BaseModel):
    pod_document_id: UUID
    verification_status: str
    duplicate: bool
    correlation_id: UUID


class PodDecisionResponse(BaseModel):
    pod_document_id: UUID
    verification_status: str
    settlement_projection_id: UUID | None
    correlation_id: UUID


class SettlementEvaluationResponse(BaseModel):
    order_id: UUID
    eligible: bool
    settlement_projection_id: UUID | None
    reason: str
    correlation_id: UUID


class RefundResponse(BaseModel):
    refund_request_id: UUID
    status: str
    duplicate: bool = False
    correlation_id: UUID


class RefundDecisionResponse(BaseModel):
    refund_request_id: UUID
    refund_decision_id: UUID
    status: str
    correlation_id: UUID


class RefundExecutionResponse(BaseModel):
    refund_request_id: UUID
    refund_execution_id: UUID
    status: str
    correlation_id: UUID
