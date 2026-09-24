"""Request/response models for the M4 deterministic dispatch boundary.

Offer creation names an exact vendor/vehicle/driver candidate; there is no
automatic search, ranking, scoring, or timeout invention here (D-27 scope).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DispatchOfferCreate(BaseModel):
    vendor_profile_id: UUID
    vehicle_id: UUID
    driver_profile_id: UUID
    expires_at: datetime


class DispatchOfferResponse(BaseModel):
    dispatch_offer_id: UUID | None
    outcome: Literal["created", "duplicate", "manual_review"]
    status: str | None
    reason_code: str | None
    duplicate: bool = False
    correlation_id: UUID


class DispatchOfferDecisionRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class DispatchOfferDecisionResponse(BaseModel):
    dispatch_offer_id: UUID
    status: str
    correlation_id: UUID


class DispatchAssignmentResponse(BaseModel):
    dispatch_offer_id: UUID
    trip_id: UUID
    trip_assignment_id: UUID
    order_status: str
    duplicate: bool = False
    correlation_id: UUID
