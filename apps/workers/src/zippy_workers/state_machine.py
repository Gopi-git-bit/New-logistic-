"""Agent execution state machine (PRD §13).

Legal flows:
    PLANNING -> EXECUTING -> VALIDATING -> COMPLETED
    PLANNING|EXECUTING|VALIDATING -> FAILED        (error)
    EXECUTING      -> BLOCKED                      (guardian/capability stop)
    PLANNING       -> REJECTED                     (budget/pause pre-checks)
"""

from __future__ import annotations

import enum


class ExecutionState(str, enum.Enum):
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


_TRANSITIONS: dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.PLANNING: {ExecutionState.EXECUTING, ExecutionState.FAILED, ExecutionState.REJECTED},
    ExecutionState.EXECUTING: {ExecutionState.VALIDATING, ExecutionState.FAILED, ExecutionState.BLOCKED},
    ExecutionState.VALIDATING: {ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.BLOCKED},
    # Terminal states accept no further transitions.
    ExecutionState.COMPLETED: set(),
    ExecutionState.FAILED: set(),
    ExecutionState.BLOCKED: set(),
    ExecutionState.REJECTED: set(),
}


class IllegalTransition(Exception):
    pass


def validate_transition(current: ExecutionState, nxt: ExecutionState) -> None:
    allowed = _TRANSITIONS[current]
    if nxt not in allowed:
        raise IllegalTransition(f"{current.value} -> {nxt.value}")
