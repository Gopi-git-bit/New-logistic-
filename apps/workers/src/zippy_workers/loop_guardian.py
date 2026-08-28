"""LoopGuardian (PRD S3) — per-tick tool governance.

Guards, in order:
  1. Tool-call cap        -> Verdict(cap_exceeded)
  2. Capability / forbidden action check
  3. Malformed payload    -> malformed(reason)
  4. Hallucination heuristic on output text
  5. Repeated identical call loop detection -> BLOCKED
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field


@dataclass(slots=True)
class GuardianVerdict:
    decision: str            # ALLOW | DENY | BLOCKED
    reason: str | None = None


@dataclass
class LoopGuardian:
    max_tool_calls: int = 20
    max_repeat_threshold: int = 3
    _calls_used: int = field(default=0, init=False)
    _seen: Counter[str] = field(default_factory=Counter, init=False)

    # ---- lifecycle ---------------------------------------------------------
    def reset_tick(self) -> None:
        self._calls_used = 0
        self._seen.clear()

    @property
    def calls_remaining(self) -> int:
        return self.max_tool_calls - self._calls_used

    # ---- pre-execution gate ------------------------------------------------
    def admit(self, *, tool: str, args_hash: str | None = None,
              capabilities_check: bool = True,
              required_capability_satisfied: bool = True,
              payload_valid: bool = True,
              hallucination_score: float = 0.0) -> GuardianVerdict:
        """Return the verdict for one proposed tool invocation."""
        if not required_capability_satisfied:
            return GuardianVerdict("DENY", "unauthorized")

        if self._calls_used >= self.max_tool_calls:
            return GuardianVerdict("DENY", "tool_call_cap_reached")

        if not payload_valid:
            return GuardianVerdict("BLOCKED", "malformed_payload")

        if hallucination_score >= 0.95:
            return GuardianVerdict("BLOCKED", "hallucination_detected")

        if args_hash is not None:
            key = hashlib.sha256(f"{tool}:{args_hash}".encode()).hexdigest()[:24]
            self._seen[key] += 1
            if self._seen[key] > self.max_repeat_threshold:
                return GuardianVerdict("BLOCKED", "repetitive_loop_detected")
        else:
            self._seen[tool] += 1
            if self._seen[tool] > self.max_repeat_threshold:
                return GuardianVerdict("BLOCKED", "repetitive_loop_detected")

        if not capabilities_check:
            return GuardianVerdict("DENY", "capability_disabled")

        self._calls_used += 1
        return GuardianVerdict("ALLOW")


def hash_args(args: dict | list | tuple | set) -> str:
    """Stable content hash used by repeat-detection."""
    import json
    blob = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()
