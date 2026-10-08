"""Read-only recommendations over an already eligible deterministic shortlist.

Results are suggestions, never assignment commands or authorization. Callers
must retain the existing transaction, eligibility and governance checks.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError


@dataclass(frozen=True)
class RecommendationCandidate:
    candidate_id: str
    distance_m: float | None
    score: float | None


@dataclass(frozen=True)
class RecommendationRequest:
    candidates: tuple[RecommendationCandidate, ...]


class RecommendationAgent(Protocol):
    async def rank(self, request: RecommendationRequest) -> object: ...


class AgentRanking(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")
    candidate_ids: list[str]


@dataclass(frozen=True)
class RecommendationResult:
    candidate_ids: tuple[str, ...]
    source: Literal["agent", "deterministic"]
    reason_code: str


def _finite_feature(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        numeric = float(value)
    except OverflowError:
        return None
    return numeric if math.isfinite(numeric) else None


async def recommend_drivers(
    candidates: Sequence[Mapping[str, Any]],
    agent: RecommendationAgent | None,
    *,
    timeout_seconds: float,
) -> RecommendationResult:
    """Rank matches without reading or mutating operational/financial state.

    Candidate IDs are opaque positions scoped to this request, not provider or
    driver identities. Original shortlist order is the deterministic fallback.
    Adapters must use cancellable async I/O and enforce their transport timeout.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    request = RecommendationRequest(
        tuple(
            RecommendationCandidate(
                f"candidate-{index}",
                _finite_feature(candidate.get("distance_m")),
                _finite_feature(candidate.get("score")),
            )
            for index, candidate in enumerate(candidates)
        )
    )
    fallback = tuple(candidate.candidate_id for candidate in request.candidates)
    if not fallback:
        return RecommendationResult(fallback, "deterministic", "NO_CANDIDATES")
    if agent is None:
        return RecommendationResult(fallback, "deterministic", "AGENT_UNAVAILABLE")
    try:
        output = await asyncio.wait_for(agent.rank(request), timeout=timeout_seconds)
    except TimeoutError:
        return RecommendationResult(fallback, "deterministic", "AGENT_TIMEOUT")
    except OSError:
        return RecommendationResult(fallback, "deterministic", "AGENT_UNAVAILABLE")
    except Exception:  # noqa: BLE001 - an advisory failure cannot affect business state
        return RecommendationResult(fallback, "deterministic", "AGENT_FAILURE")
    try:
        ranking = AgentRanking.model_validate(output)
    except ValidationError:
        return RecommendationResult(fallback, "deterministic", "MALFORMED_OUTPUT")
    if len(ranking.candidate_ids) != len(fallback) or set(ranking.candidate_ids) != set(fallback):
        return RecommendationResult(fallback, "deterministic", "MALFORMED_OUTPUT")
    return RecommendationResult(tuple(ranking.candidate_ids), "agent", "RECOMMENDED")
