"""Zippy Logistics — POD Verification Lifecycle.

Document upload alone must NOT authorize financial settlement.
Required lifecycle:
    POD_UPLOADED → POD_VERIFICATION_PENDING → POD_VERIFIED → DELIVERY_CONFIRMED → SETTLEMENT_ELIGIBLE
"""

from __future__ import annotations

from enum import Enum


class PODStatus(str, Enum):
    """Proof of Delivery verification status."""
    UPLOADED = "POD_UPLOADED"
    VERIFICATION_PENDING = "POD_VERIFICATION_PENDING"
    VERIFIED = "POD_VERIFIED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    SETTLEMENT_ELIGIBLE = "SETTLEMENT_ELIGIBLE"


# Valid state transitions
POD_TRANSITIONS = {
    PODStatus.UPLOADED: [PODStatus.VERIFICATION_PENDING],
    PODStatus.VERIFICATION_PENDING: [PODStatus.VERIFIED],
    PODStatus.VERIFIED: [PODStatus.DELIVERY_CONFIRMED],
    PODStatus.DELIVERY_CONFIRMED: [PODStatus.SETTLEMENT_ELIGIBLE],
    PODStatus.SETTLEMENT_ELIGIBLE: [],  # Terminal state
}


def can_transition(from_status: PODStatus, to_status: PODStatus) -> bool:
    """Check if a POD status transition is valid."""
    return to_status in POD_TRANSITIONS.get(from_status, [])


def next_status(current: PODStatus) -> PODStatus | None:
    """Get the next status in the lifecycle."""
    transitions = POD_TRANSITIONS.get(current, [])
    return transitions[0] if transitions else None
