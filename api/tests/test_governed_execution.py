from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.services.governed_execution import GovernedExecutionGateway
from api.services.hermes import ExecutionResult, ExecutionStatus
from api.services.paperclip import Decision, PaperclipDecision, Proposal


@dataclass
class FakePaperclip:
    decision: Decision
    calls: int = 0
    last_proposal: Proposal | None = None

    def evaluate(self, proposal: Proposal) -> PaperclipDecision:
        self.calls += 1
        self.last_proposal = proposal
        return PaperclipDecision(
            decision=self.decision,
            decision_id="decision-123",
            policy_version="test-v1",
            reason="test",
        )


@dataclass
class FakeHermes:
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    calls: int = 0
    last_payload: dict[str, Any] | None = None

    def execute(
        self,
        tool: str,
        arguments: dict[str, Any],
        decision_id: str,
        correlation_id: str | None = None,
    ) -> ExecutionResult:
        self.calls += 1
        self.last_payload = {
            "tool": tool,
            "arguments": arguments,
            "decision_id": decision_id,
            "correlation_id": correlation_id,
        }
        return ExecutionResult(
            status=self.status,
            execution_id="execution-123",
            output={"ok": True} if self.status is ExecutionStatus.SUCCESS else None,
        )


def test_approved_proposal_executes_with_paperclip_decision_id() -> None:
    paperclip = FakePaperclip(Decision.APPROVE)
    hermes = FakeHermes()
    gateway = GovernedExecutionGateway(paperclip=paperclip, hermes=hermes)  # type: ignore[arg-type]

    result = gateway.execute(
        tool="create_customer_invoice",
        arguments={"order_id": "order-1", "amount": 25000},
        agent="payment_settlement",
        order_id="order-1",
        correlation_id="corr-1",
        tenant_id="tenant-1",
    )

    assert result.approved is True
    assert result.executed is True
    assert result.successful is True
    assert paperclip.calls == 1
    assert hermes.calls == 1
    assert hermes.last_payload == {
        "tool": "create_customer_invoice",
        "arguments": {"order_id": "order-1", "amount": 25000},
        "decision_id": "decision-123",
        "correlation_id": "corr-1",
    }
    assert paperclip.last_proposal is not None
    assert paperclip.last_proposal.tenant_id == "tenant-1"


def test_reject_never_calls_hermes() -> None:
    paperclip = FakePaperclip(Decision.REJECT)
    hermes = FakeHermes()
    gateway = GovernedExecutionGateway(paperclip=paperclip, hermes=hermes)  # type: ignore[arg-type]

    result = gateway.execute(
        tool="post_invoice",
        arguments={"invoice_id": "INV-1"},
        agent="payment_settlement",
    )

    assert result.approved is False
    assert result.executed is False
    assert hermes.calls == 0


def test_hold_never_calls_hermes() -> None:
    paperclip = FakePaperclip(Decision.HOLD)
    hermes = FakeHermes()
    gateway = GovernedExecutionGateway(paperclip=paperclip, hermes=hermes)  # type: ignore[arg-type]

    result = gateway.execute(
        tool="record_payment",
        arguments={"payment_id": "pay-1"},
        agent="payment_settlement",
    )

    assert result.approved is False
    assert result.executed is False
    assert hermes.calls == 0


def test_human_review_never_calls_hermes() -> None:
    paperclip = FakePaperclip(Decision.HUMAN_REVIEW)
    hermes = FakeHermes()
    gateway = GovernedExecutionGateway(paperclip=paperclip, hermes=hermes)  # type: ignore[arg-type]

    result = gateway.execute(
        tool="create_vendor_bill",
        arguments={"amount": 9000},
        agent="payment_settlement",
    )

    assert result.approved is False
    assert result.executed is False
    assert hermes.calls == 0


def test_approved_but_hermes_failure_is_not_successful() -> None:
    paperclip = FakePaperclip(Decision.APPROVE)
    hermes = FakeHermes(status=ExecutionStatus.FAILURE)
    gateway = GovernedExecutionGateway(paperclip=paperclip, hermes=hermes)  # type: ignore[arg-type]

    result = gateway.execute(
        tool="create_sale_order",
        arguments={"order_id": "order-2"},
        agent="order_management",
    )

    assert result.approved is True
    assert result.executed is True
    assert result.successful is False
    assert hermes.calls == 1
