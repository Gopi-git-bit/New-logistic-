"""Executor — runs one claimed task through the §13 state machine.

Every business "tool" invocation passes the LoopGuardian. Capability and
financial assertions are hard gates; BLOCKED outcomes are mirrored to
`ai_agent_interventions` via the injected sink (never silent).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .capabilities import UnauthorizedCapability, assert_financial
from .loop_guardian import GuardianVerdict, LoopGuardian, hash_args
from .state_machine import ExecutionState as ES
from .state_machine import IllegalTransition, validate_transition


@dataclass
class TaskContext:
    agent: str
    task_id: str
    task_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    final_state: ES
    reason: str | None = None
    output: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.final_state is ES.COMPLETED


class Executor:
    def __init__(self, agent: str, guardian: LoopGuardian,
                 intervention_sink: Callable[[dict[str, Any]], None] | None = None):
        self.agent = agent
        self.guardian = guardian
        self._sink = intervention_sink or (lambda _details: None)

    # ------------------------------------------------------------------ run
    def run(self, ctx: TaskContext,
            tool_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> ExecutionResult:
        state = ES.PLANNING

        if not ctx.task_type:
            return self._finish(state, ES.REJECTED, "empty_task_type")

        state = ES.EXECUTING

        try:
            verdict = self.guardian.admit(
                tool=ctx.task_type,
                args_hash=hash_args(ctx.payload),
            )
        except Exception:  # guardian is trusted but never crash the flow  # noqa: BLE001
            verdict = GuardianVerdict("DENY", "guardian_internal_error")

        if verdict.decision != "ALLOW":
            reason = verdict.reason or "guard_denied"
            terminal = ES.BLOCKED if reason in {
                "malformed_payload", "hallucination_detected",
                "repetitive_loop_detected",
            } else ES.FAILED
            return self._finish(state, terminal, reason)

        start_ms = time.monotonic_ns() // 1_000_000
        try:
            output = dict(tool_fn(ctx.payload) or {})
        except UnauthorizedCapability as exc:
            return self._finish(ES.EXECUTING, ES.BLOCKED, f"unauthorized:{exc}")
        except Exception as exc:  # noqa: BLE001 - business code boundary
            return self._finish(ES.EXECUTING, ES.FAILED, type(exc).__name__)
        elapsed = int(time.monotonic_ns() // 1_000_000 - start_ms)

        state = ES.VALIDATING
        clean = self._output_clean(output)
        if not clean:
            return self._finish(state, ES.BLOCKED, "hallucination_detected")

        validate_transition(state, ES.COMPLETED)
        state = ES.COMPLETED
        return ExecutionResult(state, reason=None, output={"elapsed_ms": elapsed, **output})

    # ------------------------------------------------------------- internals
    def _finish(self, current: ES, terminal: ES, reason: str) -> ExecutionResult:
        try:
            validate_transition(current, terminal)
        except IllegalTransition:
            raise
        if terminal in (ES.FAILED, ES.BLOCKED):
            self._record_intervention(terminal, reason)
        return ExecutionResult(terminal, reason)

    def _record_intervention(self, terminal: ES, reason: str) -> None:
        details: dict[str, Any] = {
            "agent_name": self.agent,
            "intervention_type": (
                "hallucination" if reason == "hallucination_detected"
                else "anomaly_detection" if reason.startswith("unauthorized")
                else "error_correction"
            ),
            "detection_method": "loop_guardian",
            "intervention_details": {"state": terminal.value, "reason": reason},
            "status": "detected",
        }
        with contextlib_suppress():
            self._sink(details)

    @staticmethod
    def _output_clean(output: dict[str, Any]) -> bool:
        """Heuristic §4 check: reject obviously fabricated output shapes."""
        if any(k in output for k in ("<HALLUCINATED>", "__mock_garbage__")):
            return False
        for v in output.values():
            if isinstance(v, str) and v.strip().lower() in {"hallucinated", "i made this up"}:
                return False
        return True


def require_financial(agent: str) -> None:
    """Convenience gate for payment-flavored tools."""
    assert_financial(agent)


import contextlib  # noqa: E402  (placed late to keep dataclasses readable)


def contextlib_suppress():  # noqa: ANN201 - tiny helper
    return contextlib.suppress(Exception)
