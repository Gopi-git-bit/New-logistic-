"""Persistent failure, concurrency and no-authority escalation proofs."""

import asyncio
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_staging_recommendations import BASELINE, SETTINGS, TrackedTransport, envelope, runner

from zippy_workers.provider_circuit import (
    CircuitError,
    CircuitFailure,
    CircuitPermit,
    StrictProviderCircuit,
)
from zippy_workers.recommendation_provider import DEEPSEEK_DIRECT_PROFILE


@pytest.fixture
def circuit(tmp_path):
    tmp_path.chmod(0o700)
    return StrictProviderCircuit(tmp_path)


def test_success_releases_only_its_own_inflight_reservation(circuit):
    permit = circuit.reserve()
    with pytest.raises(CircuitError, match="PERMIT_MISMATCH"):
        circuit.finish(CircuitPermit("0" * 32), None)
    with pytest.raises(CircuitError):
        circuit.reserve()
    circuit.finish(permit, None)
    second = StrictProviderCircuit(circuit.directory).reserve()
    circuit.finish(second, None)


@pytest.mark.parametrize("failure", list(CircuitFailure))
def test_one_failure_latches_across_new_instances_without_reset(circuit, failure):
    circuit.finish(circuit.reserve(), failure)
    marker = circuit.directory / "deepseek-circuit.open"
    assert marker.is_file() and marker.stat().st_mode & 0o777 == 0o600
    for _ in range(2):
        with pytest.raises(CircuitError, match="CIRCUIT_OPEN"):
            StrictProviderCircuit(circuit.directory).reserve()


def test_crashed_inflight_request_stays_blocked(circuit):
    circuit.reserve()
    with pytest.raises(CircuitError, match="BUSY_OR_ABANDONED"):
        StrictProviderCircuit(circuit.directory).reserve()


def test_concurrent_invocations_reserve_exactly_one(circuit):
    def attempt(_index):
        try:
            return circuit.reserve()
        except CircuitError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        permits = [x for x in pool.map(attempt, range(6)) if x is not None]
    assert len(permits) == 1
    circuit.finish(permits[0], CircuitFailure.TIMEOUT)


@pytest.mark.parametrize("name", ["deepseek-circuit.lock", "deepseek-circuit.active"])
def test_symlinked_state_cannot_be_read_or_cleared(circuit, tmp_path, name):
    outside = tmp_path / "untouched"
    outside.write_text("synthetic-sensitive-data")
    (tmp_path / name).symlink_to(outside)
    with pytest.raises(CircuitError) as exc:
        circuit.reserve()
    assert "synthetic-sensitive-data" not in str(exc.value)
    assert outside.read_text() == "synthetic-sensitive-data"


def test_nonprivate_directory_denies(circuit):
    circuit.directory.chmod(0o755)
    with pytest.raises(CircuitError, match="STORE_UNSAFE"):
        circuit.reserve()


def test_circuit_open_or_key_presence_cannot_authorize_qwen(circuit):
    circuit.finish(circuit.reserve(), CircuitFailure.UNAVAILABLE)
    with pytest.raises(CircuitError, match="FALLBACK_NOT_AUTHORIZED"):
        circuit.assert_fallback_authorized()


def test_failed_marker_write_keeps_reservation_and_denies_future(circuit, monkeypatch):
    import os

    permit = circuit.reserve()
    write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: 0)
    with pytest.raises(CircuitError):
        circuit.finish(permit, CircuitFailure.TIMEOUT)
    monkeypatch.setattr(os, "write", write)
    with pytest.raises(CircuitError):
        circuit.reserve()
    assert (circuit.directory / "deepseek-circuit.active").exists()


@pytest.mark.parametrize("status", [200, 429, 503])
def test_runner_applies_circuit_only_after_trusted_authorization(circuit, monkeypatch, status):
    calls = []
    profile = DEEPSEEK_DIRECT_PROFILE
    settings = replace(
        SETTINGS, endpoint=profile.endpoint, model=profile.model, timeout_seconds=0.5
    )
    monkeypatch.setattr(runner, "assert_can_call_external", lambda *_args: None)
    monkeypatch.setattr(
        runner,
        "assert_staging_authorized",
        lambda *_args, **_kwargs: datetime.now(UTC) + timedelta(seconds=30),
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("mocked circuit test attempted network I/O")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    transport = TrackedTransport(
        lambda request: (
            calls.append(request)
            or httpx.Response(status, json=envelope({"candidate_ids": BASELINE}))
        )
    )
    report = asyncio.run(
        runner.run_synthetic(
            settings,
            transport=transport,
            profile=profile,
            claim_directory=circuit.directory,
        )
    )
    assert len(calls) == report.requests_started == 1
    assert transport.closed
    if status == 200:
        circuit.finish(circuit.reserve(), None)
    else:
        monkeypatch.setattr(runner, "_read_credential", forbidden)
        monkeypatch.setattr(runner, "OpenAIRecommendationAgent", forbidden)
        with pytest.raises(CircuitError, match="CIRCUIT_OPEN"):
            asyncio.run(
                runner.run_synthetic(
                    settings,
                    profile=profile,
                    claim_directory=circuit.directory,
                    credential_file=circuit.directory / "never-read.key",
                )
            )
    assert "synthetic-provider-key" not in json.dumps(report.provider_outcome)


def test_ungranted_runtime_never_touches_circuit_state(circuit, monkeypatch):
    from zippy_workers.capabilities import assert_can_call_external

    monkeypatch.setattr(runner, "assert_can_call_external", assert_can_call_external)
    with pytest.raises(CircuitError):
        # Separate test of fallback denial, without monkeypatching live authority.
        circuit.assert_fallback_authorized()
    with pytest.raises(Exception, match="PROVIDER_NOT_AUTHORIZED"):
        asyncio.run(runner.run_synthetic(SETTINGS, claim_directory=circuit.directory))
    assert not list(circuit.directory.iterdir())
