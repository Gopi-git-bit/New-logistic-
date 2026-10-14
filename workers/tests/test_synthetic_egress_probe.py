"""Mocked synthetic controls; never installed policy or real network evidence."""

import errno
import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/probe_oms_synthetic_egress.py"
SPEC = importlib.util.spec_from_file_location("synthetic_egress_probe", PATH)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("synthetic preparation attempted real sockets")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def target(monkeypatch):
    monkeypatch.setattr(probe.platform, "node", lambda: "srv1943844")
    monkeypatch.setattr(probe.platform, "system", lambda: "Linux")
    monkeypatch.setattr(probe.os, "geteuid", lambda: 10001)
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(Path, "stat", lambda _path: SimpleNamespace(st_ino=11))
    monkeypatch.setattr(
        probe,
        "boundary_observation",
        lambda: {"status": "LOCAL_CHECKS_PASSED", "namespace_inodes": {"net": 11}},
    )


def test_default_is_passive_and_never_approves_readiness(capsys):
    assert probe.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PREPARATION_ONLY"
    assert report["socket_attempts"] == report["provider_calls"] == 0
    assert report["readiness"] == "UNVERIFIED"
    assert report["effective_egress"].startswith("UNVERIFIED")


def test_fixed_matrix_has_both_families_and_address_and_port_negatives():
    cases = probe.control_cases()
    assert len(cases) == 14 and sum(c.permitted for c in cases) == 6
    assert {c.address for c in cases} == {
        "192.0.2.2",
        "192.0.2.3",
        "2001:db8:7::2",
        "2001:db8:7::3",
    }
    for family in (socket.AF_INET, socket.AF_INET6):
        controls = [c for c in cases if c.family == family]
        assert {(c.transport, c.port) for c in controls if c.permitted} == {
            ("tcp", 443),
            ("tcp", 53),
            ("udp", 53),
        }
        assert sum(not c.permitted for c in controls) == 4


@pytest.mark.parametrize("phase", ["calibration", "restricted"])
def test_suitable_local_controls_still_require_independent_proof(target, monkeypatch, phase):
    calls = []

    def attempt(case, deadline, *, receipt=None):
        calls.append((case, deadline))
        return (
            "RESPONSE_MATCHED"
            if phase == "calibration" or case.permitted
            else "NO_RESPONSE_UNVERIFIED"
        )

    monkeypatch.setattr(probe, "attempt", attempt)
    report = probe.collect(phase, perform_controls=True)
    assert len(calls) == report["socket_attempts"] == 14
    assert {deadline for _case, deadline in calls} == {16.0}
    assert report["status"] in {
        "CALIBRATION_RESPONSES_OBSERVED",
        "CANDIDATE_CONTROLS_REQUIRE_EXTERNAL_PROOF",
    }
    assert report["readiness"] == "UNVERIFIED" and report["effective_egress"].startswith(
        "UNVERIFIED"
    )
    assert report["provider_calls"] == report["configuration_changes"] == 0
    assert report["credential_loaded"] is False


@pytest.mark.parametrize("unsafe", ["root", "host", "platform"])
def test_unsafe_identity_stops_before_boundary_or_sockets(target, monkeypatch, unsafe):
    monkeypatch.setattr(
        probe, "boundary_observation", lambda: pytest.fail("unsafe metadata accessed")
    )
    if unsafe == "root":
        monkeypatch.setattr(probe.os, "geteuid", lambda: 0)
    elif unsafe == "host":
        monkeypatch.setattr(probe.platform, "node", lambda: "workstation")
    else:
        monkeypatch.setattr(probe.platform, "system", lambda: "Windows")
    report = probe.collect("restricted", perform_controls=True)
    assert report["status"] == "NOT_VERIFIED" and report["socket_attempts"] == 0


@pytest.mark.parametrize("kind", ["unsafe_boundary", "wrong_namespace", "missing_metadata"])
def test_boundary_or_namespace_failure_never_connects(target, monkeypatch, kind):
    if kind == "unsafe_boundary":
        monkeypatch.setattr(probe, "boundary_observation", lambda: {"status": "NOT_VERIFIED"})
    elif kind == "wrong_namespace":
        monkeypatch.setattr(Path, "stat", lambda _path: SimpleNamespace(st_ino=12))
    else:

        def fail():
            raise OSError("synthetic-sensitive-message")

        monkeypatch.setattr(probe, "boundary_observation", fail)
    report = probe.collect("restricted", perform_controls=True)
    assert report["status"] == "NOT_VERIFIED" and report["socket_attempts"] == 0
    assert "synthetic-sensitive-message" not in json.dumps(report)


@pytest.mark.parametrize("phase", ["calibration", "restricted"])
@pytest.mark.parametrize("outcome", ["CONNECTIVITY_ERROR_UNVERIFIED", "INVALID_RESPONSE"])
def test_unreachable_or_invalid_controls_do_not_qualify(target, monkeypatch, phase, outcome):
    monkeypatch.setattr(probe, "attempt", lambda *_args, **_kwargs: outcome)
    assert probe.collect(phase, perform_controls=True)["status"] == "NOT_VERIFIED"


def test_accessible_negative_destination_is_a_failure(target, monkeypatch):
    monkeypatch.setattr(probe, "attempt", lambda *_args, **_kwargs: "RESPONSE_MATCHED")
    assert probe.collect("restricted", perform_controls=True)["status"] == "NOT_VERIFIED"


@pytest.mark.parametrize("negative", ["CONNECTIVITY_ERROR_UNVERIFIED", "INVALID_RESPONSE"])
def test_passing_positives_do_not_hide_unverified_negative_controls(target, monkeypatch, negative):
    monkeypatch.setattr(
        probe,
        "attempt",
        lambda case, _deadline, **_kwargs: "RESPONSE_MATCHED" if case.permitted else negative,
    )
    assert probe.collect("restricted", perform_controls=True)["status"] == "NOT_VERIFIED"


def test_passing_ipv4_does_not_hide_missing_ipv6(target, monkeypatch):
    monkeypatch.setattr(
        probe,
        "attempt",
        lambda case, _deadline, **_kwargs: (
            "RESPONSE_MATCHED" if case.family == socket.AF_INET else "CONNECTIVITY_ERROR_UNVERIFIED"
        ),
    )
    assert probe.collect("calibration", perform_controls=True)["status"] == "NOT_VERIFIED"


def test_phase_cannot_select_live_destinations():
    with pytest.raises(ValueError, match="UNSUPPORTED_SYNTHETIC_PHASE"):
        probe.collect("https://api.deepseek.com")


def test_deadline_is_global_and_never_resets(target, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    calls = []

    def delayed(case, deadline, *, receipt=None):
        calls.append(deadline)
        clock[0] += 8.0
        return "RESPONSE_MATCHED"

    monkeypatch.setattr(probe, "attempt", delayed)
    report = probe.collect("calibration", perform_controls=True)
    assert calls == [16.0, 16.0]
    assert report["status"] == "NOT_VERIFIED"
    assert report["reason_code"] == "RUN_WINDOW_EXHAUSTED"


class FakeSocket:
    def __init__(self, *, error=None, chunks=None):
        self.error = error
        self.chunks = chunks
        self.address = None
        self.sent = b""
        self.timeouts = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, address):
        self.address = address
        if self.error is not None:
            raise self.error

    def sendall(self, data):
        self.sent = data

    def send(self, data):
        self.sent = data
        return len(data)

    def recv(self, size):
        assert 0 < size <= probe.MAX_RESPONSE_BYTES + 1
        if self.chunks is None:
            self.chunks = [self.sent, b""]
        return self.chunks.pop(0)


@pytest.mark.parametrize("family", [socket.AF_INET, socket.AF_INET6])
@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_nonce_echo_uses_numeric_endpoints_and_closes(monkeypatch, family, transport):
    connection = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0.0)
    case = next(c for c in probe.control_cases() if c.family == family and c.transport == transport)
    assert probe.attempt(case, 16.0) == "RESPONSE_MATCHED"
    assert connection.address[:2] == (case.address, case.port)
    assert connection.closed and all(t == 1.0 for t in connection.timeouts)
    assert connection.sent.startswith(b"M7-CONTROL ") and len(connection.sent) < 64


@pytest.mark.parametrize(
    "error,outcome",
    [
        (TimeoutError("synthetic-sensitive-message"), "NO_RESPONSE_UNVERIFIED"),
        (OSError(errno.EPERM, "synthetic-sensitive-message"), "PERMISSION_ERROR_UNVERIFIED"),
        (OSError(errno.EACCES, "synthetic-sensitive-message"), "PERMISSION_ERROR_UNVERIFIED"),
        (
            OSError(errno.ECONNREFUSED, "synthetic-sensitive-message"),
            "CONNECTIVITY_ERROR_UNVERIFIED",
        ),
        (
            OSError(errno.ENETUNREACH, "synthetic-sensitive-message"),
            "CONNECTIVITY_ERROR_UNVERIFIED",
        ),
        (
            OSError(errno.EHOSTUNREACH, "synthetic-sensitive-message"),
            "CONNECTIVITY_ERROR_UNVERIFIED",
        ),
    ],
)
def test_errors_are_redacted_closed_and_never_denial_proof(monkeypatch, error, outcome):
    connection = FakeSocket(error=error)
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0.0)
    assert probe.attempt(probe.control_cases()[0], 16.0) == outcome
    assert connection.closed


@pytest.mark.parametrize("chunks", [[b"wrong", b""], [b"x" * 65]])
def test_wrong_or_oversized_echo_fails_and_closes(monkeypatch, chunks):
    connection = FakeSocket(chunks=chunks)
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0.0)
    assert probe.attempt(probe.control_cases()[0], 16.0) == "INVALID_RESPONSE"
    assert connection.closed


def test_each_operation_consumes_the_same_attempt_deadline(monkeypatch):
    connection = FakeSocket()
    times = iter([0.0, 0.2, 0.7, 1.1])
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(probe.time, "monotonic", lambda: next(times))
    assert probe.attempt(probe.control_cases()[0], 16.0) == "NO_RESPONSE_UNVERIFIED"
    assert connection.timeouts == pytest.approx([0.8, 0.3]) and connection.closed


def test_template_is_disabled_credential_free_and_separate():
    root = Path(__file__).resolve().parents[2]
    text = (root / "infra/m7-staging/zippy-oms-staging-egress-probe@.service.in").read_text()
    assert "owner-egress-probe-enabled" in text
    assert "--phase %i --perform-controls" in text
    assert "TimeoutStartSec=18" in text and "Restart=no" in text
    assert "CapabilityBoundingSet=\nAmbientCapabilities=\n" in text
    assert "NoNewPrivileges=yes" in text and "DynamicUser=yes" in text
    assert "NetworkNamespacePath=/run/netns/zippy-oms-staging" in text
    assert "BindReadOnlyPaths=/opt/zippy-m7-staging:/opt/zippy-m7-staging" in text
    assert "BindReadOnlyPaths=/etc/netns/zippy-oms-staging/resolv.conf:/etc/resolv.conf" in text
    for forbidden in (
        "[Install]",
        "LoadCredential=",
        "EnvironmentFile=",
        "StateDirectory=",
        "owner-enabled",
    ):
        assert forbidden not in text
