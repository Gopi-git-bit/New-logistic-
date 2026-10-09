"""Synthetic-only M7 shadow evaluation; never registered as an operational tool."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from typing import Literal

from .capabilities import UnauthorizedCapability, has_capability
from .recommendations import RecommendationRequest, RecommendationResult, recommend_drivers


@dataclass(frozen=True)
class SyntheticMatch:
    """Features from a synthetic eligible shortlist, in deterministic match order."""

    distance_m: float | None = None
    score: float | None = None

    def __post_init__(self) -> None:
        for value in (self.distance_m, self.score):
            if value is None:
                continue
            if type(value) not in (int, float):
                raise ValueError("synthetic features must be finite numbers or None")
            try:
                finite = math.isfinite(value)
            except OverflowError as exc:
                raise ValueError("synthetic features must be finite numbers or None") from exc
            if not finite:
                raise ValueError("synthetic features must be finite numbers or None")


@dataclass(frozen=True)
class FakeShadowAgent:
    """Fixed local outcomes only; no injected adapter, callbacks or provider client."""

    response_json: str = '{"candidate_ids": []}'
    outcome: Literal["response", "timeout", "unavailable", "failure"] = "response"

    def __post_init__(self) -> None:
        if type(self.response_json) is not str:
            raise ValueError("response_json must be a string")
        if self.outcome not in ("response", "timeout", "unavailable", "failure"):
            raise ValueError("unknown fake outcome")

    async def rank(self, request: RecommendationRequest) -> object:
        if self.outcome == "timeout":
            await asyncio.Future[None]()
        if self.outcome == "unavailable":
            raise ConnectionError("synthetic provider unavailable")
        if self.outcome == "failure":
            raise RuntimeError("synthetic provider failure")
        try:
            return json.loads(self.response_json)
        except json.JSONDecodeError:
            return self.response_json


@dataclass(frozen=True)
class RankDifference:
    candidate_id: str
    baseline_rank: int
    advisory_rank: int


@dataclass(frozen=True)
class ShadowComparison:
    baseline_ids: tuple[str, ...]
    advisory: RecommendationResult
    differences: tuple[RankDifference, ...]
    top_choice_agrees: bool | None
    total_rank_displacement: int


async def evaluate_shadow(
    matches: tuple[SyntheticMatch, ...],
    agent: FakeShadowAgent | None,
    *,
    agent_name: str,
    action: str,
    tool: str,
    timeout_seconds: float,
) -> ShadowComparison:
    """Compare advisory ranks without rematching, assigning or persisting anything.

    The sole development grant is OMS / recommend_drivers / recommend_drivers.
    Broader production capabilities never grant shadow mutation or external tools.
    Caller-supplied names are test labels, not authenticated runtime identities.
    """
    if (agent_name, action, tool) != (
        "order_management",
        "recommend_drivers",
        "recommend_drivers",
    ) or not has_capability(agent_name, "read", "drivers"):
        raise UnauthorizedCapability("shadow agent/action/tool denied")
    if type(matches) is not tuple or any(type(match) is not SyntheticMatch for match in matches):
        raise ValueError("only a tuple of SyntheticMatch fixtures is accepted")
    if agent is not None and type(agent) is not FakeShadowAgent:
        raise ValueError("only the built-in fake shadow agent is accepted")

    candidates = [{"distance_m": match.distance_m, "score": match.score} for match in matches]
    baseline = await recommend_drivers(candidates, None, timeout_seconds=timeout_seconds)
    advisory = await recommend_drivers(candidates, agent, timeout_seconds=timeout_seconds)
    positions = {
        candidate_id: rank for rank, candidate_id in enumerate(advisory.candidate_ids, start=1)
    }
    differences = tuple(
        RankDifference(candidate_id, rank, positions[candidate_id])
        for rank, candidate_id in enumerate(baseline.candidate_ids, start=1)
        if positions[candidate_id] != rank
    )
    return ShadowComparison(
        baseline.candidate_ids,
        advisory,
        differences,
        baseline.candidate_ids[0] == advisory.candidate_ids[0] if baseline.candidate_ids else None,
        sum(abs(item.baseline_rank - item.advisory_rank) for item in differences),
    )
