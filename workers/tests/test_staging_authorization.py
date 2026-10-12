"""Synthetic grant, CLI and private-ledger evidence; never real provider approval."""

import asyncio
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from test_staging_recommendations import BASELINE, ENVIRONMENT, SETTINGS, envelope, runner

from zippy_workers.capabilities import UnauthorizedCapability
from zippy_workers.recommendation_provider import (
    DEEPSEEK_DIRECT_PROFILE,
    OpenAIRecommendationAgent,
    ProviderCleanupError,
    StagingConfigurationError,
)
from zippy_workers.staging_authorization import (
    APPROVED_STAGING_GRANTS,
    ApprovedStagingGrant,
    ExclusiveGrantClaims,
    StagingInvocation,
    assert_staging_authorized,
    ensure_execution_window,
    source_digest,
    validate_and_consume_grant,
)

NOW = datetime(2026, 10, 12, tzinfo=UTC)
SHA = "a" * 40
DIGEST = "b" * 64
PROFILE = DEEPSEEK_DIRECT_PROFILE
DIRECT = replace(SETTINGS, endpoint=PROFILE.endpoint, model=PROFILE.model)


@pytest.fixture(autouse=True)
def network_forbidden(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("authorization preparation attempted a real network call")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def bound(tmp_path):
    tmp_path.chmod(0o700)
    key = tmp_path / "synthetic.key"
    grant = ApprovedStagingGrant(
        "fake-human-grant",
        "order_management",
        "recommend_drivers",
        PROFILE.endpoint,
        PROFILE.model,
        PROFILE,
        SHA,
        DIGEST,
        10001,
        key,
        tmp_path,
        NOW - timedelta(seconds=1),
        NOW + timedelta(seconds=30),
        DIRECT.timeout_seconds,
        DIRECT.max_output_tokens,
        1,
        Decimal("0.10"),
        "fake-hard-quota-evidence",
        "fake-key-scope-evidence",
        "fake-isolation-evidence",
        "fake-human-owner",
    )
    return grant, StagingInvocation(SHA, DIGEST, 10001, key), ExclusiveGrantClaims(tmp_path)


def test_fake_grant_claim_survives_new_instance_and_cannot_repeat(bound):
    grant, invocation, claims = bound
    validate_and_consume_grant(DIRECT, PROFILE, invocation, grant, claims, now=NOW)
    marker = claims.directory / "fake-human-grant.consumed"
    assert marker.is_file() and marker.stat().st_mode & 0o777 == 0o600
    with pytest.raises(UnauthorizedCapability, match="GRANT_ALREADY_USED"):
        validate_and_consume_grant(
            DIRECT, PROFILE, invocation, grant, ExclusiveGrantClaims(claims.directory), now=NOW
        )
    assert marker.is_file()


def test_concurrent_claims_admit_exactly_one_fake_invocation(bound):
    grant, invocation, claims = bound

    def attempt():
        try:
            validate_and_consume_grant(DIRECT, PROFILE, invocation, grant, claims, now=NOW)
            return "consumed"
        except UnauthorizedCapability as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(4)))
    assert outcomes.count("consumed") == 1
    assert outcomes.count("OMS_STAGING_GRANT_ALREADY_USED") == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"agent": "payment_settlement"},
        {"operation": "assign_driver"},
        {"endpoint": "https://other.example/chat/completions"},
        {"model": "other-model"},
        {"source_sha": "c" * 40},
        {"source_digest": "c" * 64},
        {"uid": 0},
        {"max_requests": 2},
        {"max_requests": True},
        {"max_output_tokens": 256},
        {"timeout_seconds": 10},
        {"timeout_seconds": float("nan")},
        {"spend_ceiling_usd": Decimal("0")},
        {"spend_ceiling_usd": Decimal("NaN")},
        {"budget_evidence_ref": "unknown"},
        {"credential_evidence_ref": ""},
        {"isolation_evidence_ref": "pending"},
        {"approver_ref": ""},
        {"expires_at": NOW},
        {"not_before": NOW + timedelta(seconds=1)},
        {"expires_at": NOW.replace(tzinfo=None)},
    ],
)
def test_fake_grant_mismatch_denied_without_claim_or_http(bound, changes):
    grant, invocation, claims = bound
    with pytest.raises(UnauthorizedCapability):
        validate_and_consume_grant(
            DIRECT, PROFILE, invocation, replace(grant, **changes), claims, now=NOW
        )
    assert not list(claims.directory.glob("*.consumed"))


@pytest.mark.parametrize(
    "changes",
    [
        {"source_sha": "z" * 40},
        {"source_digest": "z" * 64},
        {"uid": 0},
        {"credential_file": None},
        {"credential_file": Path("/other/synthetic.key")},
    ],
)
def test_invocation_binding_cannot_be_substituted(bound, changes):
    grant, invocation, claims = bound
    with pytest.raises(UnauthorizedCapability):
        validate_and_consume_grant(
            DIRECT, PROFILE, replace(invocation, **changes), grant, claims, now=NOW
        )
    assert not list(claims.directory.glob("*.consumed"))


def test_changing_claim_store_does_not_reset_one_invocation(bound, tmp_path):
    grant, invocation, claims = bound
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    with pytest.raises(UnauthorizedCapability, match="BINDING_MISMATCH"):
        validate_and_consume_grant(
            DIRECT, PROFILE, invocation, grant, ExclusiveGrantClaims(other), now=NOW
        )


def test_unsafe_or_symlinked_claim_store_is_denied(bound, tmp_path):
    grant, invocation, claims = bound
    claims.directory.chmod(0o755)
    with pytest.raises(UnauthorizedCapability, match="CLAIM_STORE_UNSAFE"):
        validate_and_consume_grant(DIRECT, PROFILE, invocation, grant, claims, now=NOW)
    claims.directory.chmod(0o700)
    link = tmp_path / "link"
    link.symlink_to(claims.directory, target_is_directory=True)
    with pytest.raises(UnauthorizedCapability, match="CLAIM_STORE_UNAVAILABLE"):
        validate_and_consume_grant(
            DIRECT, PROFILE, invocation, grant, ExclusiveGrantClaims(link), now=NOW
        )


def test_real_registry_is_empty_and_cannot_be_filled_by_request_metadata(bound):
    grant, _, claims = bound
    assert not APPROVED_STAGING_GRANTS
    with pytest.raises(TypeError):
        APPROVED_STAGING_GRANTS[grant.grant_id] = grant
    with pytest.raises(UnauthorizedCapability, match="ENDPOINT_GRANT_NOT_AUTHORIZED"):
        assert_staging_authorized(
            DIRECT,
            PROFILE,
            source_sha=SHA,
            approval_id=grant.grant_id,
            claim_directory=claims.directory,
            credential_file=grant.credential_file,
        )
    assert not list(claims.directory.glob("*.consumed"))


def test_source_digest_is_bounded_and_deterministic():
    assert len(source_digest()) == 64
    assert source_digest() == source_digest()


def test_full_run_must_fit_inside_approval_window(bound):
    grant, invocation, claims = bound
    with pytest.raises(UnauthorizedCapability, match="GRANT_WINDOW_TOO_SHORT"):
        validate_and_consume_grant(
            DIRECT,
            PROFILE,
            invocation,
            replace(grant, expires_at=NOW + timedelta(seconds=DIRECT.timeout_seconds / 2)),
            claims,
            now=NOW,
        )
    assert not list(claims.directory.glob("*.consumed"))


def test_window_is_checked_again_after_preparation_delay():
    with pytest.raises(UnauthorizedCapability, match="GRANT_WINDOW_TOO_SHORT"):
        ensure_execution_window(NOW + timedelta(seconds=1), 10, now=NOW)


@pytest.mark.parametrize("initialization_elapsed", [0.7, 1.2])
def test_client_initialization_cannot_restart_bound_grant_window(
    monkeypatch, initialization_elapsed
):
    """Advance loop time deterministically instead of racing real sleeps."""
    from test_staging_recommendations import TrackedTransport

    settings = replace(DIRECT, timeout_seconds=1)
    transport = TrackedTransport(lambda request: pytest.fail("expired request reached HTTP"))
    concrete_client = httpx.AsyncClient
    monkeypatch.setattr(runner, "assert_can_call_external", lambda *args: None)
    monkeypatch.setattr(
        runner,
        "assert_staging_authorized",
        lambda *args, **kwargs: datetime.now(UTC) + timedelta(seconds=1.1),
    )

    async def scenario():
        loop = asyncio.get_running_loop()
        original_time = loop.time
        elapsed = 0.0
        monkeypatch.setattr(loop, "time", lambda: original_time() + elapsed)

        def delayed_client(**kwargs):
            nonlocal elapsed
            client = concrete_client(**kwargs)
            elapsed += initialization_elapsed
            return client

        monkeypatch.setattr(httpx, "AsyncClient", delayed_client)
        if initialization_elapsed < settings.timeout_seconds:
            report = await runner.run_synthetic(settings, transport=transport, profile=PROFILE)
            assert report.requests_started == 0 and report.provider_outcome == "TIMEOUT"
            assert report.advisory.candidate_ids == BASELINE
            assert transport.closed
        else:
            # There is no fresh cleanup budget once the fixed window is spent.
            with pytest.raises(ProviderCleanupError, match="PROVIDER_CLEANUP_FAILURE"):
                await runner.run_synthetic(settings, transport=transport, profile=PROFILE)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_request_building_cannot_start_http_after_fixed_request_deadline(monkeypatch):
    from test_staging_recommendations import TrackedTransport

    transport = TrackedTransport(lambda request: pytest.fail("late request reached HTTP"))

    async def scenario():
        loop = asyncio.get_running_loop()
        original_time = loop.time
        elapsed = 0.0
        monkeypatch.setattr(loop, "time", lambda: original_time() + elapsed)
        settings = replace(DIRECT, timeout_seconds=1)
        agent = OpenAIRecommendationAgent(
            settings, transport=transport, profile=PROFILE, execution_deadline=loop.time() + 1
        )
        build_request = agent._client.build_request

        def delayed_build(*args, **kwargs):
            nonlocal elapsed
            request = build_request(*args, **kwargs)
            elapsed += 0.7
            return request

        monkeypatch.setattr(agent._client, "build_request", delayed_build)
        result = await runner.recommend_drivers([{}, {}, {}], agent, timeout_seconds=1)
        await agent.aclose()
        assert result.candidate_ids == BASELINE
        assert agent.requests_started == 0 and agent.outcome == "TIMEOUT"
        assert transport.closed and asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


@pytest.mark.parametrize("deadline", [True, float("nan"), float("inf"), "unsafe"])
def test_invalid_fixed_deadline_denied_before_client_creation(monkeypatch, deadline):
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: pytest.fail("invalid deadline constructed client")
    )
    with pytest.raises(StagingConfigurationError, match="INVALID_OMS_STAGING_DEADLINE"):
        OpenAIRecommendationAgent(DIRECT, profile=PROFILE, execution_deadline=deadline)


def test_cli_profile_is_explicit_and_only_mocked_request_has_disabled_thinking(monkeypatch, capsys):
    captured = []
    concrete = runner.OpenAIRecommendationAgent
    transport = httpx.MockTransport(
        lambda request: (
            captured.append(json.loads(request.content))
            or httpx.Response(200, json=envelope({"candidate_ids": BASELINE}))
        )
    )
    monkeypatch.setattr(runner, "assert_can_call_external", lambda *args: None)
    monkeypatch.setattr(runner, "assert_staging_authorized", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "OpenAIRecommendationAgent",
        lambda settings, **kwargs: concrete(
            settings, transport=transport, profile=kwargs["profile"]
        ),
    )
    assert (
        runner.main(
            ["--run-synthetic-shadow", "--provider-profile", "deepseek-direct"],
            environment={
                **ENVIRONMENT,
                "OMS_STAGING_ENDPOINT": PROFILE.endpoint,
                "OMS_STAGING_MODEL": PROFILE.model,
            },
        )
        == 0
    )
    assert len(captured) == 1 and captured[0]["thinking"] == {"type": "disabled"}
    assert captured[0]["max_tokens"] == 128
    assert json.loads(capsys.readouterr().out)["requests_started"] == 1


def test_even_fake_global_capability_does_not_supply_real_endpoint_grant(monkeypatch):
    monkeypatch.setattr(runner, "assert_can_call_external", lambda *args: None)
    with pytest.raises(UnauthorizedCapability, match="ENDPOINT_GRANT_NOT_AUTHORIZED"):
        asyncio.run(runner.run_synthetic(DIRECT, profile=PROFILE))


def test_denied_cli_never_reads_key_file_or_constructs_client(monkeypatch, capsys, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("denied CLI touched credentials or constructed a client")

    monkeypatch.setattr(runner, "_read_credential", forbidden)
    monkeypatch.setattr(runner, "OpenAIRecommendationAgent", forbidden)
    env = {k: v for k, v in ENVIRONMENT.items() if k != "OMS_STAGING_API_KEY"}
    assert (
        runner.main(
            [
                "--run-synthetic-shadow",
                "--provider-profile",
                "deepseek-direct",
                "--credential-file",
                str(tmp_path / "not-read.key"),
                "--source-sha",
                SHA,
                "--approval-id",
                "unapproved",
            ],
            environment={
                **env,
                "OMS_STAGING_ENDPOINT": PROFILE.endpoint,
                "OMS_STAGING_MODEL": PROFILE.model,
            },
        )
        == 1
    )
    assert "OMS_STAGING_PROVIDER_NOT_AUTHORIZED" in capsys.readouterr().out


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o755])
def test_insecure_key_file_is_denied_without_disclosing_contents(tmp_path, mode):
    key = tmp_path / "synthetic.key"
    key.write_text("synthetic-secret-not-real")
    key.chmod(mode)
    with pytest.raises(StagingConfigurationError, match="CREDENTIAL_FILE_UNSAFE") as exc:
        runner._read_credential(key)
    assert "synthetic-secret-not-real" not in str(exc.value)


def test_private_key_file_and_symlink_handling(tmp_path):
    key = tmp_path / "synthetic.key"
    key.write_text("synthetic-secret-not-real\n")
    key.chmod(0o600)
    assert runner._read_credential(key) == SecretStr("synthetic-secret-not-real")
    link = tmp_path / "link.key"
    link.symlink_to(key)
    with pytest.raises(StagingConfigurationError, match="CREDENTIAL_FILE_UNSAFE"):
        runner._read_credential(link)


def test_credential_sources_cannot_be_combined(capsys, tmp_path):
    assert (
        runner.main(
            ["--run-synthetic-shadow", "--credential-file", str(tmp_path / "unused")],
            environment=ENVIRONMENT,
        )
        == 1
    )
    assert "OMS_STAGING_AMBIGUOUS_CREDENTIAL" in capsys.readouterr().out


def test_templates_stay_disabled_and_namespace_scoped():
    root = Path(__file__).resolve().parents[2]
    unit = (root / "infra/m7-staging/zippy-oms-staging.service.in").read_text()
    nft = (root / "infra/m7-staging/egress.nft.in").read_text()
    assert "[Install]" not in unit.split("[Unit]", 1)[1]
    assert "DynamicUser=yes" in unit and "NoNewPrivileges=yes" in unit
    assert "NetworkNamespacePath=/run/netns/zippy-oms-staging" in unit
    assert "Restart=no" in unit and "FUTURE_HUMAN_GRANT" in unit
    assert "env -i" in unit and "--credential-file" in unit
    assert "EnvironmentFile=" not in unit and "OMS_STAGING_API_KEY=" not in unit
    assert nft.count("policy drop;") == 3 and "flush ruleset" not in nft.split("table inet", 1)[1]
    assert "ip6 daddr @provider_v6 tcp dport 443" in nft
    assert "ip daddr @provider_v4 tcp dport 443" in nft
    assert "elements =" not in nft
