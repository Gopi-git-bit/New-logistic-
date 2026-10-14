"""Typed M3 API contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SafeText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
OrderStatus = Literal[
    "pending", "quoted", "confirmed", "assigned", "in_transit", "delivered", "cancelled"
]


class StopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: SafeText
    latitude: Decimal = Field(ge=Decimal(-90), le=Decimal(90), allow_inf_nan=False)
    longitude: Decimal = Field(
        ge=Decimal(-180), le=Decimal(180), allow_inf_nan=False
    )
    accuracy_meters: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)


class ServiceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_class: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    body_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    hazardous: bool = False
    return_trip: bool = False


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pickup: StopInput
    delivery: StopInput
    cargo_description: SafeText
    cargo_weight_kg: Decimal = Field(
        gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False
    )
    distance_km: Decimal = Field(
        gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False
    )
    service: ServiceRequirement
    requested_pickup_at: datetime
    special_handling_code: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)] | None
    ) = None

    @model_validator(mode="after")
    def validate_request(self) -> OrderCreate:
        if self.service.hazardous:
            raise ValueError("hazardous cargo is not supported")
        if self.service.return_trip:
            raise ValueError("return-trip pricing is not approved")
        if (
            self.pickup.latitude == self.delivery.latitude
            and self.pickup.longitude == self.delivery.longitude
        ):
            raise ValueError("pickup and delivery must differ")
        if self.requested_pickup_at.tzinfo is None:
            raise ValueError("requested_pickup_at must include a timezone")
        return self


class OrderAccepted(BaseModel):
    order_id: UUID
    workflow_id: UUID
    status: Literal["pending"]
    correlation_id: UUID
    accepted_at: datetime
    idempotency_replay: bool


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_status: OrderStatus
    expected_version: int = Field(gt=0)
    next_status: OrderStatus
    reason: SafeText


class TransitionResponse(BaseModel):
    order_id: UUID
    status: OrderStatus
    version: int
    correlation_id: UUID


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: UUID
    retryable: bool
    details: list[dict[str, object]] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
