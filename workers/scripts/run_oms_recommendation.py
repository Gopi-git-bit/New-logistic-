"""Explicit finite synthetic runner, separate from API and heartbeat registration."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import stat
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from pydantic import SecretStr

from zippy_workers.capabilities import (
    UnauthorizedCapability,
    assert_can_call_external,
    has_capability,
)
from zippy_workers.recommendation_provider import (
    OpenAIRecommendationAgent,
    ProviderCleanupError,
    ProviderOutcome,
    ProviderRequestProfile,
    ProviderSettings,
    StagingConfigurationError,
)
from zippy_workers.recommendations import RecommendationResult, recommend_drivers
from zippy_workers.shadow_recommendations import SyntheticMatch
from zippy_workers.staging_authorization import assert_staging_authorized, ensure_execution_window

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
    profile: ProviderRequestProfile | None = None,
    source_sha: str | None = None,
    approval_id: str | None = None,
    claim_directory: Path | None = None,
    credential_file: Path | None = None,
) -> StagingReport:
    if not has_capability("order_management", "read", "drivers"):
        raise UnauthorizedCapability("OMS_STAGING_CAPABILITY_DENIED")
    try:
        assert_can_call_external("order_management", "oms_recommendation_provider")
    except UnauthorizedCapability:
        raise UnauthorizedCapability("OMS_STAGING_PROVIDER_NOT_AUTHORIZED") from None
    expires_at = assert_staging_authorized(
        settings,
        profile,
        source_sha=source_sha,
        approval_id=approval_id,
        claim_directory=claim_directory,
        credential_file=credential_file,
    )
    if profile is not None:
        profile.validate_settings(settings)
    if credential_file is not None:
        settings = ProviderSettings(
            settings.endpoint,
            _read_credential(credential_file),
            settings.model,
            settings.timeout_seconds,
            settings.max_output_tokens,
        )
    candidates = [
        {"distance_m": match.distance_m, "score": match.score} for match in SYNTHETIC_MATCHES
    ]
    baseline = await recommend_drivers(candidates, None, timeout_seconds=settings.timeout_seconds)
    if expires_at is not None:
        ensure_execution_window(expires_at, settings.timeout_seconds)
    agent = OpenAIRecommendationAgent(settings, transport=transport, profile=profile)
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


def _read_credential(path: Path) -> SecretStr:
    """Read only a private regular staging credential after all authorization."""
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) not in {0o400, 0o600}
            or info.st_nlink != 1
            or not 1 <= info.st_size <= 2048
        ):
            raise StagingConfigurationError("OMS_STAGING_CREDENTIAL_FILE_UNSAFE")
        raw = os.read(descriptor, 2049)
        if not 1 <= len(raw) <= 2048:
            raise StagingConfigurationError("OMS_STAGING_CREDENTIAL_FILE_UNSAFE")
        return SecretStr(raw.decode("ascii").rstrip("\n"))
    except (OSError, UnicodeDecodeError):
        raise StagingConfigurationError("OMS_STAGING_CREDENTIAL_FILE_UNSAFE") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def main(
    argv: list[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-synthetic-shadow", action="store_true", required=True)
    parser.add_argument("--provider-profile", choices=["deepseek-direct"])
    parser.add_argument("--source-sha")
    parser.add_argument("--approval-id")
    parser.add_argument("--claim-directory", type=Path)
    parser.add_argument("--credential-file", type=Path)
    args = parser.parse_args(argv)
    try:
        selected_environment = dict(os.environ if environment is None else environment)
        if args.credential_file is not None:
            if selected_environment.get("OMS_STAGING_API_KEY"):
                raise StagingConfigurationError("OMS_STAGING_AMBIGUOUS_CREDENTIAL")
            # Settings/binding validation needs no real key. The file is read only
            # after both capability and trusted endpoint authorization pass.
            selected_environment["OMS_STAGING_API_KEY"] = "binding-only-not-a-provider-key"
        settings = ProviderSettings.from_environment(selected_environment)
        profile = (
            ProviderRequestProfile.DEEPSEEK_DIRECT if args.provider_profile is not None else None
        )
        if any(
            (profile, args.source_sha, args.approval_id, args.claim_directory, args.credential_file)
        ):
            report = asyncio.run(
                run_synthetic(
                    settings,
                    profile=profile,
                    source_sha=args.source_sha,
                    approval_id=args.approval_id,
                    claim_directory=args.claim_directory,
                    credential_file=args.credential_file,
                )
            )
        else:
            report = asyncio.run(run_synthetic(settings))
    except (StagingConfigurationError, ProviderCleanupError, UnauthorizedCapability) as exc:
        print(json.dumps({"status": "ERROR", "reason_code": str(exc)}))
        return 1
    print(json.dumps({"status": "SHADOW_ONLY", **asdict(report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
