"""Fixed, bounded synthetic echo listeners; disabled unless --serve is selected."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import selectors
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SPEC = importlib.util.spec_from_file_location(
    "oms_synthetic_contract", Path(__file__).with_name("oms_synthetic_contract.py")
)
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)
PEER_NAMESPACE = Path("/run/netns/zippy-m7-synthetic-peer")
TARGET_NAMESPACE = Path("/run/netns/zippy-oms-staging")


def now() -> str:
    return datetime.now(UTC).isoformat()


def peer_boundary() -> dict[str, Any]:
    fields = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    own = Path("/proc/self/ns/net").stat().st_ino
    peer, target = PEER_NAMESPACE.stat().st_ino, TARGET_NAMESPACE.stat().st_ino
    uid = os.geteuid()
    caps = int(fields["CapEff"].strip(), 16)
    mount_entries = [
        line.split()
        for line in Path("/proc/self/mountinfo").read_text().splitlines()
        if len(line.split()) >= 6 and line.split()[4] == "/opt/zippy-m7-staging"
    ]
    safe = (
        uid > 0
        and len(fields["Uid"].split()) == 4
        and int(fields["Uid"].split()[1]) == uid
        and caps in {0, 1 << 10}
        and fields["NoNewPrivs"].strip() == "1"
        and own == peer
        and own != target
        and len(mount_entries) == 1
        and "ro" in mount_entries[0][5].split(",")
    )
    return {
        "safe": safe,
        "effective_uid": uid,
        "capabilities": caps,
        "no_new_privileges": fields["NoNewPrivs"].strip() == "1",
        "network_inode": own,
    }


def exchange(connection: socket.socket, deadline: float) -> bytes | None:
    data = b""
    while len(data) < 35:
        remaining = min(deadline, time.monotonic() + 1.0) - time.monotonic()
        if remaining <= 0:
            return None
        connection.settimeout(remaining)
        chunk = connection.recv(65 - len(data))
        if not chunk:
            return None
        data += chunk
    if contract.CHALLENGE.fullmatch(data) is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    connection.settimeout(remaining)
    connection.sendall(data)
    return data


def serve() -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "NOT_VERIFIED",
        "provider_calls": 0,
        "credential_loaded": False,
        "pid": os.getpid(),
        "events": [],
        "errors": 0,
    }
    if platform.node() != "srv1943844" or platform.system() != "Linux" or os.geteuid() == 0:
        report["reason_code"] = "UNSAFE_HOST_OR_IDENTITY"
        return report
    try:
        report["boundary"] = peer_boundary()
        if not report["boundary"]["safe"]:
            report["reason_code"] = "UNSAFE_PEER_BOUNDARY"
            return report
    except (OSError, ValueError, KeyError):
        report["reason_code"] = "PEER_BOUNDARY_UNAVAILABLE"
        return report
    sockets: list[socket.socket] = []
    deadline = time.monotonic() + contract.PEER_SECONDS
    exchanges = 0
    try:
        with selectors.DefaultSelector() as selector:
            definitions: list[dict[str, Any]] = contract.cases()
            for index, case in enumerate(definitions):
                family = socket.AF_INET if case["family"] == "ipv4" else socket.AF_INET6
                kind = socket.SOCK_STREAM if case["transport"] == "tcp" else socket.SOCK_DGRAM
                listener = socket.socket(family, kind)
                sockets.append(listener)
                if family == socket.AF_INET6:
                    listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                listener.setblocking(False)
                listener.bind((case["address"], case["port"]))
                if kind == socket.SOCK_STREAM:
                    listener.listen(2)
                selector.register(listener, selectors.EVENT_READ, index)
            report["ready_at_utc"] = now()
            report["bound_cases"] = list(range(len(definitions)))
            # A single bounded ready record lets an operator start calibration.
            print(
                json.dumps(
                    {k: v for k, v in report.items() if k != "events"}
                    | {"status": "LISTENERS_READY"}
                ),
                flush=True,
            )
            while time.monotonic() < deadline and exchanges < contract.MAX_EXCHANGES:
                for selected, _mask in selector.select(max(0, deadline - time.monotonic())):
                    if time.monotonic() >= deadline or exchanges >= contract.MAX_EXCHANGES:
                        break
                    index = selected.data
                    case = definitions[index]
                    ready_socket = selected.fileobj
                    assert isinstance(ready_socket, socket.socket)
                    listener = ready_socket
                    exchanges += 1
                    try:
                        if case["transport"] == "tcp":
                            connection, remote = listener.accept()
                            with connection:
                                if remote[0] != case["source"]:
                                    report["errors"] += 1
                                    continue
                                response = exchange(connection, min(deadline, time.monotonic() + 1))
                        else:
                            data, remote = listener.recvfrom(65)
                            response = None
                            if remote[0] == case["source"] and contract.CHALLENGE.fullmatch(data):
                                if listener.sendto(data, remote) == len(data):
                                    response = data
                        if response is None:
                            report["errors"] += 1
                        else:
                            report["events"].append(
                                {
                                    "case": index,
                                    "at_utc": now(),
                                    "challenge_sha256": contract.digest(response),
                                }
                            )
                    except OSError:
                        report["errors"] += 1
            report["status"] = (
                "LISTENER_COMPLETED" if exchanges < contract.MAX_EXCHANGES else "NOT_VERIFIED"
            )
            report["attempted_exchanges"] = exchanges
    except OSError:
        report["reason_code"] = "LISTENER_IO_UNAVAILABLE"
        report["status"] = "NOT_VERIFIED"
    finally:
        # No listener survives the shared deadline or a partial bind failure.
        for listener in sockets:
            try:
                listener.close()
            except OSError:
                report["status"] = "NOT_VERIFIED"
        report["finished_at_utc"] = now()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args(argv)
    report = (
        serve()
        if args.serve
        else {
            "status": "PREPARATION_ONLY",
            "provider_calls": 0,
            "credential_loaded": False,
            "bound_cases": [],
            "events": [],
        }
    )
    print(json.dumps(report, sort_keys=True))
    return 1 if report["status"] == "NOT_VERIFIED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
