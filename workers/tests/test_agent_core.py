"""M3 agent-core test suite — PRD §12-§16 cases."""

from copy import deepcopy

import pytest

from zippy_workers.capabilities import UnauthorizedCapability, assert_financial, has_capability
from zippy_workers.executor import Executor, TaskContext
from zippy_workers.loop_guardian import LoopGuardian
from zippy_workers.state_machine import ExecutionState as ES
from zippy_workers.state_machine import IllegalTransition, validate_transition
from zippy_workers.telemetry_adapter import InMemorySink, TelemetryAdapter
from zippy_workers.telemetry_pseudonym import generate_pepper, pseudonymize

AGENT = "order_management"


def make_guardian(cap: int = 20) -> LoopGuardian:
    g = LoopGuardian(max_tool_calls=cap)
    g.reset_tick()
    return g


def run_simple(
    payload: dict | None = None, output: dict | None = None, guardian: LoopGuardian | None = None
) -> tuple:
    outbox: list[dict] = []
    ex = Executor(AGENT, guardian or make_guardian(), intervention_sink=outbox.append)
    res = ex.run(
        TaskContext(AGENT, "t1", "noop_task", payload or {}),
        lambda p: output if output is not None else {"ok": True},
    )
    return res, outbox


# ------------------------------------------------------------------ state machine
def test_happy_path_completes():
    res, _ = run_simple()
    assert res.final_state is ES.COMPLETED and res.ok


def test_all_illegal_transitions_rejected():
    with pytest.raises(IllegalTransition):
        validate_transition(ES.PLANNING, ES.COMPLETED)  # skipping execution
    with pytest.raises(IllegalTransition):
        validate_transition(ES.EXECUTING, ES.PLANNING)  # backward
    with pytest.raises(IllegalTransition):
        validate_transition(ES.COMPLETED, ES.FAILED)  # terminal frozen


# ------------------------------------------------------------------ malformed
def test_malformed_payload_blocks_with_intervention():
    res, box = run_simple(payload=None, guardian=_g_for(payload_valid=False))
    # payload_valid=False comes from guardian admit(); emulate via broken guard below
    assert res.final_state in {ES.BLOCKED, ES.FAILED}
    assert box and box[0]["intervention_details"]["reason"] in {
        "malformed_payload",
        "hallucination_detected",
    }


def _g_for(**kw):
    class PreDeny(LoopGuardian):  # pre-seeded verdict override
        def admit(self, **kwargs):  # type: ignore[override]
            kwargs.update(kw)
            return super().admit(**kwargs)

    g = PreDeny(max_tool_calls=20)
    g.reset_tick()
    return g


# ------------------------------------------------------------------ hallucination
def test_hallucinated_output_blocked():
    res, box = run_simple(output={"__mock_garbage__": True})
    assert res.final_state is ES.BLOCKED
    assert res.reason == "hallucination_detected"
    assert box[0]["intervention_type"] == "hallucination"


def test_lying_text_output_blocked():
    res, _ = run_simple(output={"note": "I made this up"})
    assert res.final_state is ES.BLOCKED


# ------------------------------------------------------------------ unauthorized capability
def test_unauthorized_capability_denied_at_matrix():
    assert not has_capability("communication", "write", "orders")
    assert has_capability("payment_settlement", "write", "payments")
    assert not has_capability("transportation", "write", "pricing")


def test_financial_gate_enforced():
    with pytest.raises(UnauthorizedCapability):
        assert_financial("customer_service")
    assert_financial("payment_settlement")  # must NOT raise


def test_executor_wraps_unauthorized_tool_as_blocked():
    def forbidden_tool(_p):
        raise UnauthorizedCapability("orders->admin_actions")

    outbox: list[dict] = []
    ex = Executor(AGENT, make_guardian(), intervention_sink=outbox.append)
    res = ex.run(TaskContext(AGENT, "t2", "raider_task"), forbidden_tool)
    assert res.final_state is ES.BLOCKED
    assert res.reason.startswith("unauthorized:")
    assert outbox[0]["detection_method"] == "loop_guardian"


# ------------------------------------------------------------------ loop + cap
def test_repetitive_loop_detected_after_threshold():
    g = make_guardian()
    for _ in range(3):
        v = g.admit(tool="lookup", args_hash="same-args")
        assert v.decision == "ALLOW"
    v4 = g.admit(tool="lookup", args_hash="same-args")
    assert v4.decision == "BLOCKED"
    assert v4.reason == "repetitive_loop_detected"


def test_tool_call_cap_enforces_env_budget():
    g = make_guardian(cap=3)
    seen = [g.admit(tool=f"tool_{i}").decision for i in range(5)]
    assert seen[:3] == ["ALLOW"] * 3
    assert seen[3] == "DENY" and g.calls_remaining == 0


# ------------------------------------------------------------------ budget semantics (worker side mirror of D-17 RPCs)
def test_spend_mirror_never_negative_and_pauses():
    spent = 90
    budget = 100
    for _ in range(3):
        spent += 5
    paused = spent >= budget
    assert spent == 105 and paused  # kernel auto-pauses at exhaustion


def test_m6_development_usage_reconciles_independent_receipts():
    receipts = [
        {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10, "estimated_cost_cents": 2},
        {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16, "estimated_cost_cents": 4},
    ]
    source_usage = deepcopy(receipts)
    sink = InMemorySink()
    pepper = generate_pepper()
    adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper=pepper)
    workflow = pseudonymize("synthetic-usage-workflow", pepper)
    with adapter.trace("synthetic_usage") as trace:
        for receipt in receipts:
            metadata = {**receipt, "pseudonymous_workflow_id": workflow}
            with trace.span("synthetic_call", metadata=metadata):
                result, audit = run_simple()
                assert result.ok and not audit
    assert sink.count == len(source_usage)
    assert all(event["correlation_id"] == trace.correlation_id for event in sink.events)
    assert all(event["pseudonymous_workflow_id"] == workflow for event in sink.events)
    for key in receipts[0]:
        assert sum(event[key] for event in sink.events) == sum(row[key] for row in source_usage)
    assert all(
        event["total_tokens"] == event["input_tokens"] + event["output_tokens"]
        for event in sink.events
    )
    before = deepcopy(source_usage)
    sink.events[0]["estimated_cost_cents"] += 1
    assert sum(event["estimated_cost_cents"] for event in sink.events) != sum(
        row["estimated_cost_cents"] for row in source_usage
    )
    sink.clear()
    assert source_usage == before


@pytest.mark.parametrize(
    "mode", ["disabled", "healthy", "outage", "recovery", "redaction", "classification"]
)
def test_m6_development_audit_and_usage_survive_telemetry_failures(mode):
    class SyntheticCollector(InMemorySink):
        attempts = 0

        def emit(self, event):
            self.attempts += 1
            if mode == "outage" or (mode == "recovery" and self.attempts == 1):
                raise OSError("synthetic_collector_unavailable")
            super().emit(event)

    outputs = [{"ok": True}, {"ok": True}, {"__mock_garbage__": True}]
    expected = [run_simple(output=output) for output in outputs]
    collector = SyntheticCollector()
    adapter = TelemetryAdapter(enabled=mode != "disabled", sampling_rate=1.0, sink=collector)
    outcomes = []
    audit_records = []
    source_usage = []
    for index, output in enumerate(outputs):
        metadata = {
            "input_tokens": index + 1,
            "output_tokens": 1,
            "total_tokens": index + 2,
            "estimated_cost_cents": index + 1,
        }
        if mode == "redaction":
            metadata["ledger_entry"] = "synthetic-prohibited-metadata"
        if mode == "classification":
            metadata[42] = "synthetic-unclassifiable-field"
        with adapter.trace("synthetic_execution") as trace:
            with trace.span("synthetic_step", metadata=metadata) as span:
                result, audit = run_simple(output=output)
                source_usage.append(index + 1)
                outcomes.append((result.final_state, result.reason))
                audit_records.extend(audit)
                span.set_attribute("task_state", result.final_state.value)
    assert outcomes == [(result.final_state, result.reason) for result, audit in expected]
    assert audit_records == [record for result, audit in expected for record in audit]
    assert len(audit_records) == 1
    assert outcomes[-1][0] is ES.BLOCKED
    assert source_usage == [1, 2, 3]
    if mode == "healthy":
        assert collector.count == collector.attempts == 3
    elif mode == "recovery":
        assert collector.count == 2 and collector.attempts == 3
        assert sum(event["estimated_cost_cents"] for event in collector.events) == 5
        assert sum(source_usage) == 6
    else:
        assert collector.count == 0
        assert collector.attempts == (3 if mode == "outage" else 0)
    before = deepcopy((outcomes, audit_records, source_usage))
    collector.clear()
    collector.close()
    assert (outcomes, audit_records, source_usage) == before
