"""Sealed test-container entry point; no Docker socket or migration credentials."""

from __future__ import annotations

import argparse
import errno
import json
import os
import resource
import socket
import subprocess
import sys
import time
from pathlib import Path

# The reviewed source is mounted read-only at this fixed path in the proof.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from db.scripts.disposable_contract import (  # noqa: E402
    digest,
    read_private,
    report_cases,
    require,
    status_observation,
)


def socket_control(endpoint: str, denied: bool) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(5)
        try:
            probe.connect(endpoint)
        except OSError as exc:
            require(denied and exc.errno in {errno.EACCES, errno.EPERM}, "SOCKET_CONTROL_REJECTED")
            return
        require(not denied, "SOCKET_CONTROL_REJECTED")


def run_phase(output: Path) -> dict[str, object]:
    import psycopg

    phase = os.environ["DISPOSABLE_PHASE"]
    require(phase in {"operations", "governance"}, "PHASE_REJECTED")
    uid = os.geteuid()
    process = status_observation(Path("/proc/self/status").read_text(), uid)
    interfaces = [
        line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]
    ]
    require(
        interfaces == ["lo"] and len(Path("/proc/net/route").read_text().splitlines()) == 1,
        "TEST_NETWORK_REJECTED",
    )
    require(not Path("/var/run/docker.sock").exists(), "DOCKER_SOCKET_REJECTED")
    key = "ZIPPY_M4_TEST_DATABASE_URL" if phase == "operations" else "PAPERCLIP_DATABASE_URL"
    url = os.environ[key]
    login = "zippy_m2_app_login" if phase == "operations" else "paperclip_m5_app_login"
    schema = "zippy" if phase == "operations" else "paperclip"
    migrator = "zippy_migrator" if phase == "operations" else "paperclip_migrator"
    with psycopg.connect(url, connect_timeout=3) as connection:
        row = connection.execute(
            "SELECT current_user, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, "
            "pg_has_role(current_user, %s, 'MEMBER'), "
            "(SELECT pg_get_userbyid(nspowner)=current_user FROM pg_namespace WHERE nspname=%s) "
            "FROM pg_roles WHERE rolname=current_user",
            (migrator, schema),
        ).fetchone()
        require(
            row is not None and row[0] == login and row[1:] == (False,) * 6, "APP_ROLE_REJECTED"
        )
    started = time.time_ns()
    report = output / "results.xml"
    require(not report.exists(), "STALE_REPORT_REJECTED")
    suites = ["api/tests", "api/tests_m4"] if phase == "operations" else ["api/tests_m5"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_194_304, 4_194_304))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *suites,
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--junitxml=" + str(report),
        ],
        env=dict(os.environ),
        check=False,
        timeout=540,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # pytest writes nothing to the public job log. The source-bound JUnit stays private.
    require(result.returncode == 0, "PYTEST_FAILED")
    report.chmod(0o600)
    require(report.stat().st_mtime_ns >= started, "STALE_REPORT_REJECTED")
    cases, counts = report_cases(report, phase)
    return {
        "schema": 1,
        "phase": phase,
        "source_sha": os.environ["DISPOSABLE_SOURCE"],
        "run_id": os.environ["DISPOSABLE_RUN"],
        "nonce": os.environ["DISPOSABLE_NONCE"],
        "process": process,
        "namespaces": {n: os.stat("/proc/self/ns/" + n).st_ino for n in ("net", "mnt", "ipc")},
        "network_none_observed": True,
        "role": login,
        "restricted_role": True,
        "positive_authentication": True,
        "pytest_exit": result.returncode,
        "report_sha256": digest(read_private(report, 4_194_304)),
        "cases": cases,
        "integration_counts": counts,
        "skips": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["test", "denied", "accessible"])
    parser.add_argument("endpoint", nargs="?")
    args = parser.parse_args()
    try:
        os.umask(0o077)
        require(os.geteuid() > 0, "ROOT_OR_UID_REJECTED")
        if args.mode != "test":
            require(os.geteuid() == 65534 and args.endpoint, "CONTROL_IDENTITY_REJECTED")
            socket_control(args.endpoint, args.mode == "denied")
            print("SOCKET_CONTROL_PASSED")
            return 0
        output = Path("/out")
        require(not (output / "runtime.json").exists(), "STALE_REPORT_REJECTED")
        report = run_phase(output)
        (output / "runtime.json").write_text(json.dumps(report))
        return 0
    except Exception:
        print("DISPOSABLE_RUNTIME_NOT_VERIFIED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
