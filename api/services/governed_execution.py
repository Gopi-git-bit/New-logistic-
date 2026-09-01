"""Governed execution gateway for consequential external mutations.

This module enforces the canonical execution chain:
Agent -> Paperclip -> Hermes -> target system.

Only an explicit Paperclip APPROVE decision may reach Hermes.
All other governance outcomes fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from api.services.hermes import ExecutionResult, ExecutionStatus, HermesClient
from api.services.paperclip import Decision, PaperclipClient, PaperclipDecision, Proposal


@dataclass(frozen=True)
class GovernedExecutionResult:
    """Outcome of a governed action request."""

    approved: bool
    decision: PaperclipDecision
    execution: Optional[ExecutionResult] = None

    @property
    def executed(self) -> bool:
        return self.execution is not None

    @property
    def successful(self) -> bool:
        return (
            self.approved
            and self.execution is not None
            and self.execution.status is ExecutionStatus.SUCCESS
        )


class GovernedExecutionGateway:
    """Coordinates Paperclip approval before Hermes execution."""

    def __init__(self, paperclip: PaperclipClient, hermes: HermesClient):
        self.paperclip = paperclip
        self.hermes = hermes

    def execute(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        agent: str,
        order_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> GovernedExecutionResult:
        """Request governance approval and execute only when approved.

        Paperclip already fails closed on transport/service errors by returning
        Decision.REJECT. This gateway additionally treats every non-APPROVE
        decision as non-executable, including HOLD and HUMAN_REVIEW.
        """

        proposal = Proposal(
            tool=tool,
            arguments=arguments,
            agent=agent,
            order_id=order_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
        decision = self.paperclip.evaluate(proposal)

        if decision.decision is not Decision.APPROVE:
            return GovernedExecutionResult(
                approved=False,
                decision=decision,
                execution=None,
            )

        execution = self.hermes.execute(
            tool=tool,
            arguments=arguments,
            decision_id=decision.decision_id,
            correlation_id=correlation_id,
        )
        return GovernedExecutionResult(
            approved=True,
            decision=decision,
            execution=execution,
        )
