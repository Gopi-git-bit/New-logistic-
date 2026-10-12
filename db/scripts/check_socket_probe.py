"""Check the non-root probe against private and accessible synthetic sockets."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
from pathlib import Path


def verify_controls() -> None:
    if os.geteuid() != 0:
        raise ValueError("CI root orchestration required")
    root = Path(__file__).resolve().parents[2]
    source = (root / "db/zippy/scripts/run_m4_finance_proof.sh").read_text()
    marker = "/usr/bin/python3 - <<'PY' || negative_rc=$?\n"
    probe = source.split(marker, 1)[1].split("\nPY", 1)[0]
    with tempfile.TemporaryDirectory(prefix="zippy-ci-probe-control-") as directory:
        path = Path(directory)
        endpoint = path / "synthetic.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(endpoint))
            server.listen(1)
            endpoint.chmod(0o666)
            for mode, expected in ((0o700, 0), (0o755, 42)):
                path.chmod(mode)
                result = subprocess.run(
                    [
                        "setpriv",
                        "--reuid=65534",
                        "--regid=65534",
                        "--clear-groups",
                        "/usr/bin/python3",
                        "-",
                    ],
                    input=probe,
                    text=True,
                    capture_output=True,
                    env={
                        "PATH": "/usr/bin:/bin",
                        "ZIPPY_M4_SOCKET_PROBE": str(endpoint),
                    },
                    timeout=3,
                    check=False,
                )
                if result.returncode != expected:
                    raise ValueError("socket control outcome mismatch")


def main() -> int:
    try:
        verify_controls()
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        print("SOCKET_PROBE_CONTROLS_UNVERIFIED")
        return 1
    print("socket_probe_controls=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
