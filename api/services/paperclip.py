"""Zippy Logistics — Paperclip Governance Client.

Typed interface for Paperclip governance decisions.
All external mutations must pass through Paperclip before execution.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx


class Decision(Enum):
    """Paperclip decision outcomes."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    HOLD = "HOLD"
    HUMAN_REVIEW = "HUMAN_REVIEW"


@dataclass
class Proposal:
    """A proposal to be evaluated by Paperclip."""
    tool: str
    arguments: dict[str, Any]
    agent: str
    order_id: Optional[str] = None
    correlation_id: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass
class PaperclipDecision:
    """Result of Paperclip evaluation."""
    decision: Decision
    decision_id: str
    policy_version: str
    reason: Optional[str] = None
    reviewer: Optional[str] = None


class PaperclipClient:
    """Paperclip governance client."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = httpx.Client(timeout=timeout_s)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def evaluate(self, proposal: Proposal) -> PaperclipDecision:
        """Evaluate a proposal through Paperclip governance."""
        payload = {
            "tool": proposal.tool,
            "arguments": proposal.arguments,
            "agent": proposal.agent,
            "order_id": proposal.order_id,
            "correlation_id": proposal.correlation_id or str(uuid.uuid4()),
            "tenant_id": proposal.tenant_id,
            "arguments_hash": hashlib.sha256(
                json.dumps(proposal.arguments, sort_keys=True).encode()
            ).hexdigest()[:16],
        }

        try:
            resp = self._http.post(
                f"{self.base_url}/api/v1/evaluate",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return PaperclipDecision(
                decision=Decision(data["decision"]),
                decision_id=data["decision_id"],
                policy_version=data.get("policy_version", "unknown"),
                reason=data.get("reason"),
                reviewer=data.get("reviewer"),
            )
        except Exception as e:
            # Paperclip governance must FAIL CLOSED
            return PaperclipDecision(
                decision=Decision.REJECT,
                decision_id=str(uuid.uuid4()),
                policy_version="error",
                reason=f"Paperclip unavailable: {type(e).__name__}",
            )

    def get_decision(self, decision_id: str) -> Optional[PaperclipDecision]:
        """Retrieve an existing decision by ID."""
        try:
            resp = self._http.get(
                f"{self.base_url}/api/v1/decisions/{decision_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return PaperclipDecision(
                decision=Decision(data["decision"]),
                decision_id=data["decision_id"],
                policy_version=data.get("policy_version", "unknown"),
                reason=data.get("reason"),
                reviewer=data.get("reviewer"),
            )
        except Exception:
            return None

    def close(self) -> None:
        self._http.close()
