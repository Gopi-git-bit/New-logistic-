"""Synthetic target-boundary observations, not installed-host acceptance."""

import errno
import importlib.util
import json
import os
import socket
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/probe_oms_staging_target.py"
SPEC = importlib.util.spec_from_file_location("staging_target_probe", PATH)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

STATUS = "Uid:\t10001\t10001\t10001\t10001\nCapEff:\t0000000000000000\nNoNewPrivs:\t1\n"
MOUNTS = "1 0 0:1 / /opt/zippy-m7-staging ro,nosuid - tmpfs tmpfs ro\n"


@pytest.fixture
def target(monkeypatch):
    monkeypatch.setattr(probe.platform, "node", lambda: "srv1943844")
    monkeypatch.setattr(probe.platform, "system", lambda: "Linux")
    monkeypatch.setattr(probe.os, "geteuid", lambda: 10001)
    monkeypatch.setattr(Path, "read_text", lambda path: STATUS if path.name == "status" else MOUNTS)
    monkeypatch.setattr(probe, "namespace_inodes", lambda: {"net": 11, "mnt": 12, "ipc": 13})
    monkeypatch.setattr(probe, "fixture_access", lambda: "OBSERVED_DENIAL")

    def forbidden(*_args, **_kwargs):
        pytest.fail("target probe attempted socket activity")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def test_local_observations_never_approve_readiness_or_remaining_gates(target):
    report = probe.collect("srv1943844")
    assert report["status"] == "LOCAL_CHECKS_PASSED"
    assert report["readiness"] == "UNVERIFIED" and report["credential_loaded"] is False
    assert report["provider_calls"] == report["socket_attempts"] == 0
    for key in ("spending_cap", "trusted_authorization"):
        assert report[key] == "UNVERIFIED"
    assert report["fixture_positive_control"] == "REQUIRED_OUTSIDE_TARGET"
    assert report["namespace_boundary"].startswith("UNVERIFIED")
    assert report["effective_egress"].startswith("UNVERIFIED")
    assert report["business_mount_access"].startswith("UNVERIFIED")


@pytest.mark.parametrize("uid,host", [(0, "srv1943844"), (10001, "workstation")])
def test_root_or_wrong_host_stops_before_metadata_and_fixture_access(
    target, monkeypatch, uid, host
):
    monkeypatch.setattr(probe.os, "geteuid", lambda: uid)
    monkeypatch.setattr(probe.platform, "node", lambda: host)
    monkeypatch.setattr(Path, "read_text", lambda _path: pytest.fail("unsafe target inspected"))
    monkeypatch.setattr(probe, "fixture_access", lambda: pytest.fail("unsafe target probed"))
    assert probe.main([]) == 1


@pytest.mark.parametrize(
    "status",
    [
        STATUS.replace("10001", "10002"),
        STATUS.replace("0000000000000000", "0000000000000001"),
        STATUS.replace("NoNewPrivs:\t1", "NoNewPrivs:\t0"),
        "Uid:\tinvalid\nCapEff: invalid\n",
    ],
)
def test_unsafe_or_missing_effective_identity_fails(target, monkeypatch, status):
    monkeypatch.setattr(Path, "read_text", lambda path: status if path.name == "status" else MOUNTS)
    assert probe.main([]) == 1


@pytest.mark.parametrize("mounts", ["", MOUNTS.replace("ro,nosuid", "rw,nosuid"), MOUNTS + MOUNTS])
def test_missing_or_writable_bundle_mount_fails(target, monkeypatch, mounts):
    monkeypatch.setattr(Path, "read_text", lambda path: STATUS if path.name == "status" else mounts)
    assert probe.main([]) == 1


@pytest.mark.parametrize("result", ["ACCESSIBLE", "UNVERIFIED"])
def test_accessible_or_unknown_fixture_fails(target, monkeypatch, result):
    monkeypatch.setattr(probe, "fixture_access", lambda: result)
    assert probe.main([]) == 1


@pytest.mark.parametrize("code", [errno.EACCES, errno.EPERM, errno.ENOENT, errno.ELOOP])
def test_only_permission_denial_counts_as_an_observation(monkeypatch, code):
    def fail(*_args, **_kwargs):
        raise OSError(code, "synthetic-sensitive-data")

    monkeypatch.setattr(os, "open", fail)
    result = probe.fixture_access()
    assert result == ("OBSERVED_DENIAL" if code in {errno.EACCES, errno.EPERM} else "UNVERIFIED")
    assert "synthetic-sensitive-data" not in result


def test_accessible_fixture_is_closed_without_reading_any_content(monkeypatch):
    calls = []
    monkeypatch.setattr(os, "open", lambda path, flags: calls.append((path, flags)) or 42)
    monkeypatch.setattr(os, "close", lambda fd: calls.append(fd))
    monkeypatch.setattr(os, "read", lambda *_args: pytest.fail("fixture contents read"))
    assert probe.fixture_access() == "ACCESSIBLE"
    assert calls == [(probe.FIXTURE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 42]


def test_metadata_error_is_redacted_and_nonzero(target, monkeypatch, capsys):
    def fail():
        raise OSError("synthetic-sensitive-data")

    monkeypatch.setattr(probe, "namespace_inodes", fail)
    assert probe.main([]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["observation_error"] == "METADATA_UNAVAILABLE"
    assert "synthetic-sensitive-data" not in output
