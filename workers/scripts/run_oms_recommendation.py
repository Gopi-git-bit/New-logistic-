"""Explicit finite synthetic runner, separate from API and heartbeat registration."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass

import httpx

from zippy_workers.capabilities import UnauthorizedCapability, has_capability
from zippy_workers.recommendation_provider import (
    OpenAIRecommendationAgent,
    ProviderCleanupError,
    ProviderOutcome,
    ProviderSettings,
    StagingConfigurationError,
)
from zippy_workers.recommendations import RecommendationResult, recommend_drivers
from zippy_workers.shadow_recommendations import SyntheticMatch

# Already-eligible fixtures preserve backend shortlist order, not a new feature sort.
SYNTHETIC_MATCHES = (SyntheticMatch(30, 7), SyntheticMatch(10, 9), SyntheticMatch(20, 8))


@dataclass(frozen=True)
class StagingReport:
    baseline_ids: tuple[str, ...]
    advisory: RecommendationResult
    provider_outcome: ProviderOutcome
    requests_started: int
    telemetry_enabled: bool = False


async def run_synthetic(
    settings: ProviderSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> StagingReport:
    if not has_capability("order_management", "read", "drivers"):
        raise UnauthorizedCapability("OMS_STAGING_CAPABILITY_DENIED")
    candidates = [
        {"distance_m": match.distance_m, "score": match.score} for match in SYNTHETIC_MATCHES
    ]
    baseline = await recommend_drivers(candidates, None, timeout_seconds=settings.timeout_seconds)
    agent = OpenAIRecommendationAgent(settings, transport=transport)
    try:
        advisory = await recommend_drivers(
            candidates, agent, timeout_seconds=settings.timeout_seconds / 2
        )
    finally:
        cleanup = asyncio.create_task(agent.aclose())
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError
    return StagingReport(baseline.candidate_ids, advisory, agent.outcome, agent.requests_started)


def main(
    argv: list[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-synthetic-shadow", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        settings = ProviderSettings.from_environment(
            os.environ if environment is None else environment
        )
        report = asyncio.run(run_synthetic(settings))
    except (StagingConfigurationError, ProviderCleanupError, UnauthorizedCapability) as exc:
        print(json.dumps({"status": "ERROR", "reason_code": str(exc)}))
        return 1
    print(json.dumps({"status": "SHADOW_ONLY", **asdict(report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
