"""Bounded synthetic controls only; external policy proof is still required."""

from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
import platform
import secrets
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_HOST = "srv1943844"
TARGET_NAMESPACE = Path("/run/netns/zippy-oms-staging")
BOUNDARY_PROBE = Path(__file__).with_name("probe_oms_staging_target.py")
RUN_SECONDS = 16.0
ATTEMPT_SECONDS = 1.0
MAX_RESPONSE_BYTES = 64


@dataclass(frozen=True)
class Control:
    family: int
    address: str
    transport: str
    port: int
    permitted: bool


def control_cases() -> tuple[Control, ...]:
    """Fixed documentation addresses; no hostname, destination or port override."""
    cases = []
    for family, permitted, blocked in (
        (socket.AF_INET, "192.0.2.2", "192.0.2.3"),
        (socket.AF_INET6, "2001:db8:7::2", "2001:db8:7::3"),
    ):
        for address, allowed in ((permitted, True), (blocked, False)):
            for transport, port in (("tcp", 443), ("tcp", 53), ("udp", 53)):
                cases.append(Control(family, address, transport, port, allowed))
        cases.append(Control(family, permitted, "tcp", 5432, False))
    return tuple(cases)


def boundary_observation() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("synthetic_boundary_probe", BOUNDARY_PROBE)
    if spec is None or spec.loader is None:
        return {"status": "NOT_VERIFIED"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The installed PR15 diagnostic also implements this credential-free call.
    report: dict[str, Any] = module.collect(EXPECTED_HOST)
    return report


def _set_remaining_timeout(connection: socket.socket, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    connection.settimeout(remaining)


def attempt(case: Control, run_deadline: float) -> str:
    """Send a nonce echo challenge, never HTTP/TLS/DNS/database protocol."""
    deadline = min(run_deadline, time.monotonic() + ATTEMPT_SECONDS)
    challenge = b"M7-CONTROL " + secrets.token_hex(12).encode("ascii")
    kind = socket.SOCK_STREAM if case.transport == "tcp" else socket.SOCK_DGRAM
    address: tuple[Any, ...] = (
        (case.address, case.port)
        if case.family == socket.AF_INET
        else (case.address, case.port, 0, 0)
    )
    try:
        with socket.socket(case.family, kind) as connection:
            _set_remaining_timeout(connection, deadline)
            connection.connect(address)
            _set_remaining_timeout(connection, deadline)
            # Connected UDP filters responses to the nominated synthetic peer.
            if case.transport == "tcp":
                connection.sendall(challenge)
            elif connection.send(challenge) != len(challenge):
                return "INVALID_RESPONSE"
            response = b""
            while len(response) <= MAX_RESPONSE_BYTES:
                _set_remaining_timeout(connection, deadline)
                chunk = connection.recv(MAX_RESPONSE_BYTES + 1 - len(response))
                if not chunk:
                    break
                response += chunk
                if case.transport == "udp":
                    break
            return "RESPONSE_MATCHED" if response == challenge else "INVALID_RESPONSE"
    except TimeoutError:
        # Absence of a response alone is never firewall-denial evidence.
        return "NO_RESPONSE_UNVERIFIED"
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EPERM}:
            return "PERMISSION_ERROR_UNVERIFIED"
        # Refused connections, absent routes, neighbor failures and close errors
        # must not be promoted to denial. Do not expose exception messages.
        return "CONNECTIVITY_ERROR_UNVERIFIED"


def collect(phase: str, *, perform_controls: bool = False) -> dict[str, Any]:
    if phase not in {"calibration", "restricted"}:
        raise ValueError("UNSUPPORTED_SYNTHETIC_PHASE")
    deadline = time.monotonic() + RUN_SECONDS
    report: dict[str, Any] = {
        "status": "PREPARATION_ONLY",
        "phase": phase,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "readiness": "UNVERIFIED",
        "effective_egress": "UNVERIFIED_REQUIRES_INDEPENDENT_POLICY_CORRELATION",
        "namespace_comparison": "REQUIRES_FRESH_INDEPENDENT_HOST_FACTS",
        "peer_health_and_calibration": "REQUIRES_INDEPENDENT_EVIDENCE",
        "provider_calls": 0,
        "credential_loaded": False,
        "configuration_changes": 0,
        "socket_attempts": 0,
        "run_seconds": RUN_SECONDS,
        "maximum_attempts": len(control_cases()),
        "results": [],
    }
    if not perform_controls:
        return report
    report["status"] = "NOT_VERIFIED"
    if platform.node() != EXPECTED_HOST or platform.system() != "Linux" or os.geteuid() == 0:
        report["reason_code"] = "UNSAFE_HOST_OR_IDENTITY"
        return report
    try:
        boundary = boundary_observation()
        report["boundary"] = boundary
        if boundary.get("status") != "LOCAL_CHECKS_PASSED":
            report["reason_code"] = "BOUNDARY_NOT_VERIFIED"
            return report
        if boundary["namespace_inodes"]["net"] != TARGET_NAMESPACE.stat().st_ino:
            report["reason_code"] = "WRONG_NETWORK_NAMESPACE"
            return report
    except (OSError, ImportError, KeyError):
        report["reason_code"] = "BOUNDARY_METADATA_UNAVAILABLE"
        return report

    suitable = True
    for case in control_cases():
        attempt_started = time.monotonic()
        if attempt_started >= deadline:
            report["reason_code"] = "RUN_WINDOW_EXHAUSTED"
            return report
        outcome = attempt(case, deadline)
        attempt_finished = time.monotonic()
        report["socket_attempts"] += 1
        expects_response = phase == "calibration" or case.permitted
        suitable &= (
            outcome == "RESPONSE_MATCHED"
            if expects_response
            else outcome in {"NO_RESPONSE_UNVERIFIED", "PERMISSION_ERROR_UNVERIFIED"}
        )
        report["results"].append(
            {
                "family": "ipv4" if case.family == socket.AF_INET else "ipv6",
                "address": case.address,
                "transport": case.transport,
                "port": case.port,
                "expected": "response" if expects_response else "policy_correlated_denial",
                "outcome": outcome,
                "started_elapsed_seconds": attempt_started - (deadline - RUN_SECONDS),
                "finished_elapsed_seconds": attempt_finished - (deadline - RUN_SECONDS),
            }
        )
    if time.monotonic() >= deadline:
        report["reason_code"] = "RUN_WINDOW_EXHAUSTED"
    elif suitable:
        report["status"] = (
            "CALIBRATION_RESPONSES_OBSERVED"
            if phase == "calibration"
            else "CANDIDATE_CONTROLS_REQUIRE_EXTERNAL_PROOF"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("calibration", "restricted"), default="restricted")
    parser.add_argument("--perform-controls", action="store_true")
    args = parser.parse_args(argv)
    report = collect(args.phase, perform_controls=args.perform_controls)
    print(json.dumps(report, sort_keys=True))
    return 1 if report["status"] == "NOT_VERIFIED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
