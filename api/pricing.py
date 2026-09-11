"""Deterministic test-only pricing policy for M3."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .config import Settings
from .models.core import OrderCreate


@dataclass(frozen=True)
class PriceQuote:
    amount: Decimal
    currency: str
    policy_version: str
    input_hash: str
    evidence: dict[str, str]


def calculate_price(order: OrderCreate, settings: Settings) -> PriceQuote:
    evidence = {
        "distance_km": str(order.distance_km),
        "cargo_weight_kg": str(order.cargo_weight_kg),
        "vehicle_class": order.service.vehicle_class,
        "body_type": order.service.body_type,
        "return_trip": "false",
    }
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    amount = (
        settings.pricing_base_amount
        + order.distance_km * settings.pricing_per_km
        + order.cargo_weight_kg * settings.pricing_per_kg
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not amount.is_finite() or amount < 0:
        raise ValueError("calculated price is invalid")
    return PriceQuote(
        amount=amount,
        currency=settings.pricing_currency,
        policy_version=settings.pricing_policy_version,
        input_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        evidence=evidence,
    )
