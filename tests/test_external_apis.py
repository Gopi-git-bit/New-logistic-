"""Offline M7 denial regressions; never probe live provider endpoints."""

import importlib.util
import json
import socket
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "workers/scripts/run_oms_recommendation.py"


@pytest.fixture
def denied_runner(monkeypatch):
    spec = importlib.util.spec_from_file_location("offline_m7_runner", RUNNER)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    # Dataclass construction resolves its defining module through sys.modules.
    monkeypatch.setitem(sys.modules, spec.name, runner)
    spec.loader.exec_module(runner)
    tripwires = []
    for target, attribute in (
        (runner, "_read_credential"),
        (runner, "OpenAIRecommendationAgent"),
        (runner.httpx, "Client"),
        (runner.httpx, "AsyncClient"),
        (socket, "create_connection"),
        (socket.socket, "connect"),
    ):
        forbidden = Mock(side_effect=AssertionError("unauthorized credential or network access"))
        monkeypatch.setattr(target, attribute, forbidden)
        tripwires.append(forbidden)
    yield runner
    for forbidden in tripwires:
        forbidden.assert_not_called()


@pytest.mark.parametrize("provider", ["deepseek", "unapproved-qwen"])
def test_provider_configuration_cannot_grant_execution(
    provider, denied_runner, monkeypatch, tmp_path, capsys
):
    # Set only synthetic fixtures, even if the invoking shell contains real keys.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-deepseek-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter-key")
    claims = tmp_path / "claims"
    credential = tmp_path / "unread-credential"
    environment = {
        "OMS_STAGING_ENDPOINT": (
            "https://api.deepseek.com/chat/completions"
            if provider == "deepseek"
            else "https://provider.invalid/chat/completions"
        ),
        "OMS_STAGING_MODEL": "deepseek-flash" if provider == "deepseek" else provider,
        "OMS_STAGING_TIMEOUT_SECONDS": "1",
        "OMS_STAGING_MAX_OUTPUT_TOKENS": "16",
    }
    args = [
        "--run-synthetic-shadow",
        "--source-sha",
        "f" * 40,
        "--approval-id",
        "untrusted-synthetic-approval",
        "--claim-directory",
        str(claims),
        "--credential-file",
        str(credential),
    ]
    if provider == "deepseek":
        args.extend(["--provider-profile", "deepseek-direct"])
    assert denied_runner.main(args, environment=environment) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "ERROR",
        "reason_code": "OMS_STAGING_PROVIDER_NOT_AUTHORIZED",
    }
    assert not claims.exists() and not credential.exists()
    assert "synthetic-deepseek-key" not in captured.out + captured.err
    assert "synthetic-openrouter-key" not in captured.out + captured.err


@pytest.mark.parametrize("name", ["DEEPSEEK_API_KEY", "OPENROUTER_API_KEY"])
def test_generic_provider_secret_is_not_staging_configuration(name, denied_runner, capsys):
    key = "synthetic-generic-provider-key"
    assert denied_runner.main(["--run-synthetic-shadow"], environment={name: key}) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "ERROR",
        "reason_code": "ISOLATION_VIOLATION",
    }
    assert key not in captured.out + captured.err
