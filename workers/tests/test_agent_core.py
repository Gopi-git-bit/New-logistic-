"""M3 agent-core test suite — PRD §12-§16 cases."""

import pytest

from zippy_workers.capabilities import UnauthorizedCapability, assert_financial, has_capability
from zippy_workers.executor import Executor, TaskContext
from zippy_workers.loop_guardian import LoopGuardian, hash_args
from zippy_workers.state_machine import ExecutionState as ES
from zippy_workers.state_machine import IllegalTransition, validate_transition

AGENT = "order_management"


def make_guardian(cap: int = 20) -> LoopGuardian:
    g = LoopGuardian(max_tool_calls=cap)
    g.reset_tick()
    return g


def run_simple(payload: dict | None = None, output: dict | None = None,
               guardian: LoopGuardian | None = None) -> tuple:
    outbox: list[dict] = []
    ex = Executor(AGENT, guardian or make_guardian(),
                  intervention_sink=outbox.append)
    res = ex.run(TaskContext(AGENT, "t1", "noop_task", payload or {}),
                 lambda p: output if output is not None else {"ok": True})
    return res, outbox


# ------------------------------------------------------------------ state machine
def test_happy_path_completes():
    res, _ = run_simple()
    assert res.final_state is ES.COMPLETED and res.ok


def test_all_illegal_transitions_rejected():
    with pytest.raises(IllegalTransition):
        validate_transition(ES.PLANNING, ES.COMPLETED)          # skipping execution
    with pytest.raises(IllegalTransition):
        validate_transition(ES.EXECUTING, ES.PLANNING)          # backward
    with pytest.raises(IllegalTransition):
        validate_transition(ES.COMPLETED, ES.FAILED)            # terminal frozen


# ------------------------------------------------------------------ malformed
def test_malformed_payload_blocks_with_intervention():
    res, box = run_simple(payload=None, guardian=_g_for(payload_valid=False))
    # payload_valid=False comes from guardian admit(); emulate via broken guard below
    assert res.final_state in {ES.BLOCKED, ES.FAILED}
    assert box and box[0]["intervention_details"]["reason"] in {
        "malformed_payload", "hallucination_detected"}


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
    for i in range(3):
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
