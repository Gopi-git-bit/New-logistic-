"""Zippy Logistics — Hermes Execution Client.

Typed interface for Hermes approved tool execution.
Only allowlisted tools may be executed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx


class ExecutionStatus(Enum):
    """Hermes execution status."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    UNAUTHORIZED = "UNAUTHORIZED"


@dataclass
class ExecutionResult:
    """Result of Hermes execution."""
    status: ExecutionStatus
    execution_id: str
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int = 0


# Allowlisted tools that Hermes may execute
ALLOWLISTED_TOOLS = {
    "find_partner",
    "create_partner",
    "create_sale_order",
    "create_customer_invoice",
    "post_invoice",
    "create_vendor_bill",
    "record_payment",
    "reconcile_payment",
    "confirm_picking",
    "send_notification",
    "process_document",
    "match_drivers",
    "assign_driver",
    "update_delivery_status",
}


class HermesClient:
    """Hermes execution client."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = httpx.Client(timeout=timeout_s)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def execute(
        self,
        tool: str,
        arguments: dict[str, Any],
        decision_id: str,
        correlation_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute an approved tool through Hermes."""
        # Enforce allowlist
        if tool not in ALLOWLISTED_TOOLS:
            return ExecutionResult(
                status=ExecutionStatus.UNAUTHORIZED,
                execution_id=str(uuid.uuid4()),
                error=f"Tool '{tool}' not in allowlist",
            )

        payload = {
            "tool": tool,
            "arguments": arguments,
            "decision_id": decision_id,
            "correlation_id": correlation_id or str(uuid.uuid4()),
        }

        try:
            resp = self._http.post(
                f"{self.base_url}/api/v1/execute",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return ExecutionResult(
                status=ExecutionStatus(data["status"]),
                execution_id=data["execution_id"],
                output=data.get("output"),
                error=data.get("error"),
                latency_ms=data.get("latency_ms", 0),
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                execution_id=str(uuid.uuid4()),
                error=f"Hermes unavailable: {type(e).__name__}",
            )

    def close(self) -> None:
        self._http.close()
