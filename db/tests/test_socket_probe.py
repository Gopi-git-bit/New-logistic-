"""Require real socket denial; reject errors before the database test phase."""

import errno
import os
import socket
import subprocess
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2] / "db/zippy/scripts/run_m4_finance_proof.sh"
).read_text()
PROBE = SOURCE.split("/usr/bin/python3 - <<'PY' || negative_rc=$?\n", 1)[1].split(
    "\nPY", 1
)[0]
GATE = SOURCE.split("negative_local_user='NOT VERIFIED'\n", 1)[1].split(
    "\nproof_phase=tests\n", 1
)[0]


@pytest.mark.parametrize("probe_exit", [0, 1, 3, 42, 124, 137])
def test_actual_probe_errors_and_access_stop_before_tests(probe_exit):
    # Execute the production shell gate, stubbing only the probe process.
    script = f"""set -euo pipefail
id() {{ printf '0\\n'; }}
setpriv() {{ cat >/dev/null; return {probe_exit}; }}
socket_dir=/synthetic
negative_local_user='NOT VERIFIED'
{GATE}
printf 'TEST_PHASE_REACHED\\n'
"""
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=3, check=False
    )
    assert result.returncode == (0 if probe_exit == 0 else 1)
    assert ("TEST_PHASE_REACHED" in result.stdout) == (probe_exit == 0)


def test_missing_probe_prerequisite_stops_before_tests():
    script = f"""set -euo pipefail
id() {{ printf '1\\n'; }}
socket_dir=/synthetic
negative_local_user='NOT VERIFIED'
{GATE}
printf 'TEST_PHASE_REACHED\\n'
"""
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=3, check=False
    )
    assert result.returncode == 1
    assert "TEST_PHASE_REACHED" not in result.stdout
    assert "negative_local_user=NOT VERIFIED" in result.stderr


@pytest.mark.parametrize(
    "error,expected",
    [
        (OSError(errno.EACCES, "synthetic denial"), 0),
        (OSError(errno.EPERM, "synthetic denial"), 0),
        (OSError(errno.ECONNREFUSED, "synthetic refusal"), 3),
        (OSError(errno.ENOENT, "synthetic missing socket"), 3),
        (OSError(errno.ETIMEDOUT, "synthetic timeout"), 3),
        (TimeoutError("synthetic timeout"), 3),
        (None, 42),
    ],
)
def test_probe_accepts_only_permission_denial(monkeypatch, error, expected):
    class SyntheticSocket:
        timeout = None
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

        def settimeout(self, value):
            self.timeout = value

        def connect(self, path):
            assert path == "/synthetic/socket"
            if error is not None:
                raise error

    probe = SyntheticSocket()
    monkeypatch.setattr(socket, "socket", lambda *_args: probe)
    monkeypatch.setattr(os, "geteuid", lambda: 65534)
    monkeypatch.setenv("ZIPPY_M4_SOCKET_PROBE", "/synthetic/socket")
    with pytest.raises(SystemExit) as exited:
        # Execute only the checked-in heredoc so the regression covers CI code.
        exec(compile(PROBE, "<production socket probe>", "exec"), {})  # noqa: S102
    assert exited.value.code == expected
    assert probe.timeout == 5
    assert probe.closed


def test_probe_rejects_wrong_identity_before_connect(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)

    def unexpected_socket(*_args):
        pytest.fail("wrong identity must not reach the socket")

    monkeypatch.setattr(socket, "socket", unexpected_socket)
    with pytest.raises(SystemExit) as exited:
        exec(compile(PROBE, "<production socket probe>", "exec"), {})  # noqa: S102
    assert exited.value.code == 3
