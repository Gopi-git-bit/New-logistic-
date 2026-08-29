"""Zippy Logistics — POD Verification Lifecycle.

Document upload alone must NOT authorize financial settlement.
Required lifecycle:
    POD_UPLOADED → POD_VERIFICATION_PENDING → POD_VERIFIED → DELIVERY_CONFIRMED → SETTLEMENT_ELIGIBLE

Each transition must be persisted to the database before proceeding.
The Paperclip → Hermes chain is enforced at the DELIVERY_CONFIRMED → SETTLEMENT_ELIGIBLE step.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import httpx


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

# Transitions that require Paperclip governance before advancing
PAPERCLIP_REQUIRED_TRANSITIONS = {
    (PODStatus.DELIVERY_CONFIRMED, PODStatus.SETTLEMENT_ELIGIBLE),
}


def can_transition(from_status: PODStatus, to_status: PODStatus) -> bool:
    """Check if a POD status transition is valid."""
    return to_status in POD_TRANSITIONS.get(from_status, [])


def next_status(current: PODStatus) -> Optional[PODStatus]:
    """Get the next status in the lifecycle."""
    transitions = POD_TRANSITIONS.get(current, [])
    return transitions[0] if transitions else None


def requires_paperclip(from_status: PODStatus, to_status: PODStatus) -> bool:
    """Check if this transition requires Paperclip governance."""
    return (from_status, to_status) in PAPERCLIP_REQUIRED_TRANSITIONS


class PODStore:
    """Persistent POD state management via Supabase."""

    def __init__(self, supabase_url: str, service_key: str):
        self.base_url = supabase_url.rstrip("/")
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.Client(timeout=10.0)

    def get_order_status(self, order_id: str) -> Optional[PODStatus]:
        """Fetch current POD status for an order from the orders table."""
        try:
            resp = self._http.get(
                f"{self.base_url}/rest/v1/orders",
                params={
                    "id": f"eq.{order_id}",
                    "select": "pod_status",
                },
                headers=self.headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    raw = data[0].get("pod_status", "POD_UPLOADED")
                    try:
                        return PODStatus(raw)
                    except ValueError:
                        return PODStatus.UPLOADED
        except Exception:
            pass
        return None

    def advance_status(
        self,
        order_id: str,
        current_status: PODStatus,
        target_status: PODStatus,
    ) -> tuple[bool, str]:
        """Atomically advance POD status in the database.

        Returns (success, message). Uses optimistic concurrency:
        UPDATE ... WHERE pod_status = current_status.
        If the row wasn't updated, the status has changed since read.
        """
        if not can_transition(current_status, target_status):
            return False, f"Invalid transition: {current_status.value} → {target_status.value}"

        try:
            resp = self._http.patch(
                f"{self.base_url}/rest/v1/orders",
                params={
                    "id": f"eq.{order_id}",
                    "pod_status": f"eq.{current_status.value}",
                },
                json={"pod_status": target_status.value},
                headers={**self.headers, "Prefer": "return=minimal"},
            )
            if resp.status_code in (200, 204):
                return True, f"Advanced to {target_status.value}"
            elif resp.status_code == 200:
                # Check if any rows were updated
                data = resp.json() if resp.text else []
                if not data:
                    return False, "Status changed by another process"
            return False, f"DB update failed: {resp.status_code}"
        except Exception as e:
            return False, f"DB error: {type(e).__name__}"

    def close(self) -> None:
        self._http.close()
