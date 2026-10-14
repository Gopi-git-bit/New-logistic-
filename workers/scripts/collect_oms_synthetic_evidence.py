"""Offline correlation of private synthetic artifacts; never grants activation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SPEC = importlib.util.spec_from_file_location(
    "oms_synthetic_contract", Path(__file__).with_name("oms_synthetic_contract.py")
)
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)
FILES = (
    "manifest.json",
    "listener-ready.json",
    "listener-final.json",
    "calibration.json",
    "restricted.json",
    "calibration-before.json",
    "calibration-after.json",
    "restricted-before.json",
    "restricted-after.json",
    "original-policy.json",
    "restored-policy.json",
    "peer-calibration-before.json",
    "peer-calibration-after.json",
    "peer-restricted-before.json",
    "peer-restricted-after.json",
)
LIMIT = 2 * 1024 * 1024


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("SYNTHETIC_EVIDENCE_INCOMPLETE")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def load_private(directory: Path) -> dict[str, Any]:
    result = {}
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700)
        for name in FILES:
            file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                info = os.fstat(file_fd)
                require(
                    stat.S_ISREG(info.st_mode)
                    and info.st_uid == os.geteuid()
                    and stat.S_IMODE(info.st_mode) == 0o600
                    and info.st_nlink == 1
                    and 0 < info.st_size <= LIMIT
                )
                data = b""
                while len(data) <= LIMIT:
                    chunk = os.read(file_fd, min(65536, LIMIT + 1 - len(data)))
                    if not chunk:
                        break
                    data += chunk
                require(0 < len(data) <= LIMIT)
                result[name] = json.loads(data, object_pairs_hook=unique_object)
            finally:
                os.close(file_fd)
    finally:
        os.close(fd)
    return result


def timestamp(value: Any) -> datetime:
    require(isinstance(value, str))
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0))
    return parsed.astimezone(UTC)


def number(value: Any) -> float:
    require(type(value) in {int, float} and math.isfinite(value) and value >= 0)
    return float(value)


def envelope(value: dict[str, Any], unit: str) -> dict[str, Any]:
    require(
        value["unit"] == unit and re.fullmatch(r"[0-9a-f]{32}", value["invocation_id"]) is not None
    )
    require(type(value["pid"]) is int and value["pid"] > 0)
    report: dict[str, Any] = value["report"]
    require(
        report["pid"] == value["pid"]
        and report["provider_calls"] == 0
        and report["credential_loaded"] is False
    )
    return report


def evaluate(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Only a correlated record; operator provenance/acceptance remains required."""
    manifest = artifacts["manifest.json"]
    require(manifest["host"] == "srv1943844" and manifest["version"] == 1)
    require(re.fullmatch(r"[0-9a-f]{40}", manifest["source_sha"]) is not None)
    host, target, peer = (
        manifest[key] for key in ("host_net_inode", "target_net_inode", "peer_net_inode")
    )
    require(
        all(type(n) is int and n > 0 for n in (host, target, peer))
        and len({host, target, peer}) == 3
    )
    # These are signed-off operator observations, not evidence manufactured here.
    for key in (
        "exclusive_target",
        "no_uplink",
        "fixture_positive_control",
        "restoration_verified",
    ):
        require(manifest[key] is True)
    for phase in ("calibration", "restricted", "peer"):
        require(manifest["policy_sha256"][phase] == contract.digest(contract.policy_bytes(phase)))
    code_root = Path(__file__).parent
    expected_sources = {
        name: contract.digest((code_root / name).read_bytes())
        for name in (
            "oms_synthetic_contract.py",
            "probe_oms_synthetic_egress.py",
            "serve_oms_synthetic_peer.py",
            "collect_oms_synthetic_evidence.py",
        )
    }
    require(manifest["source_sha256"] == expected_sources)
    original_record, restored_record = (
        artifacts[name] for name in ("original-policy.json", "restored-policy.json")
    )
    require(original_record["network_inode"] == restored_record["network_inode"] == target)
    original, restored = original_record["ruleset"], restored_record["ruleset"]
    require(
        [item["table"]["name"] for item in original["nftables"] if "table" in item]
        == [contract.TARGET_TABLE]
    )

    # Original policy may contain sets. Do not discard any expression or object.
    def restoration_shape(value: dict[str, Any]) -> Any:
        def strip(item: Any) -> Any:
            if isinstance(item, dict):
                return {k: strip(v) for k, v in item.items() if k != "handle"}
            if isinstance(item, list):
                return [strip(v) for v in item]
            return item

        return [strip(x) for x in value["nftables"] if "metainfo" not in x]

    require(restoration_shape(original) == restoration_shape(restored))
    ready = envelope(artifacts["listener-ready.json"], "zippy-oms-staging-synthetic-peer.service")
    listener = envelope(
        artifacts["listener-final.json"], "zippy-oms-staging-synthetic-peer.service"
    )
    require(
        artifacts["listener-ready.json"]["invocation_id"]
        == artifacts["listener-final.json"]["invocation_id"]
    )
    require(ready["status"] == "LISTENERS_READY" and listener["status"] == "LISTENER_COMPLETED")
    require(ready["pid"] == listener["pid"] and ready["boundary"] == listener["boundary"])
    boundary = listener["boundary"]
    require(
        boundary["safe"] is True
        and type(boundary["effective_uid"]) is int
        and boundary["effective_uid"] > 0
        and boundary["capabilities"] in {0, 1 << 10}
        and boundary["no_new_privileges"] is True
        and boundary["network_inode"] == peer
    )
    require(ready["bound_cases"] == listener["bound_cases"] == list(range(14)))
    require(listener["errors"] == 0 and listener["attempted_exchanges"] == 20)
    ready_at, final_at = timestamp(listener["ready_at_utc"]), timestamp(listener["finished_at_utc"])
    require(
        ready["ready_at_utc"] == listener["ready_at_utc"]
        and 0 < (final_at - ready_at).total_seconds() <= 42
    )
    require(
        timestamp(original_record["captured_at_utc"]) < ready_at
        and final_at <= timestamp(restored_record["captured_at_utc"])
        and (timestamp(restored_record["captured_at_utc"]) - final_at).total_seconds() <= 120
    )
    require(len(listener["events"]) == 20)
    events = {event["challenge_sha256"]: event for event in listener["events"]}
    require(len(events) == 20)
    consumed: set[str] = set()
    challenges: set[str] = set()
    phase_times = []
    phase_invocations = set()
    definitions: list[dict[str, Any]] = contract.cases()
    for phase in ("calibration", "restricted"):
        wrapper = artifacts[f"{phase}.json"]
        report = envelope(wrapper, f"zippy-oms-staging-egress-probe@{phase}.service")
        phase_invocations.add(wrapper["invocation_id"])
        require(
            report["phase"] == phase
            and report["socket_attempts"] == 14
            and report["configuration_changes"] == 0
            and report["maximum_attempts"] == 14
            and report["run_seconds"] == 16.0
        )
        expected_status = (
            "CALIBRATION_RESPONSES_OBSERVED"
            if phase == "calibration"
            else "CANDIDATE_CONTROLS_REQUIRE_EXTERNAL_PROOF"
        )
        require(report["status"] == expected_status and report["readiness"] == "UNVERIFIED")
        b = report["boundary"]
        require(
            b["status"] == "LOCAL_CHECKS_PASSED"
            and b["bundle_readonly"] is True
            and b["synthetic_fixture_access"] == "OBSERVED_DENIAL"
            and type(b["target_uid"]) is int
            and b["target_uid"] > 0
            and b["process"]["effective_uid"] == b["target_uid"]
            and b["process"]["effective_capabilities"] == "0000000000000000"
            and b["process"]["no_new_privileges"] is True
            and b["namespace_inodes"]["net"] == target
            and b["namespace_inodes"]["mnt"] != manifest["host_mount_inode"]
            and b["namespace_inodes"]["ipc"] != manifest["host_ipc_inode"]
        )
        start, end = timestamp(report["started_at_utc"]), timestamp(report["finished_at_utc"])
        require(ready_at <= start < end <= final_at and (end - start).total_seconds() <= 16.5)
        phase_times.append((start, end))
        before, after = (artifacts[f"{phase}-{side}.json"] for side in ("before", "after"))
        require(before["network_inode"] == after["network_inode"] == target)
        require(
            timestamp(before["captured_at_utc"]) <= start
            and timestamp(after["captured_at_utc"]) >= end
        )
        require(
            ready_at
            <= timestamp(before["captured_at_utc"])
            <= timestamp(after["captured_at_utc"])
            <= final_at
        )
        expected = contract.policy_shape(contract.policy(phase))
        require(
            contract.policy_shape(before["ruleset"])
            == contract.policy_shape(after["ruleset"])
            == expected
        )
        require(
            contract.snapshot_identity(before["ruleset"])
            == contract.snapshot_identity(after["ruleset"])
        )
        peer_before, peer_after = (
            artifacts[f"peer-{phase}-{side}.json"] for side in ("before", "after")
        )
        require(peer_before["network_inode"] == peer_after["network_inode"] == peer)
        require(
            ready_at <= timestamp(peer_before["captured_at_utc"]) <= start
            and end <= timestamp(peer_after["captured_at_utc"]) <= final_at
        )
        require(
            contract.policy_shape(peer_before["ruleset"])
            == contract.policy_shape(peer_after["ruleset"])
            == contract.policy_shape(contract.policy("peer"))
        )
        require(
            contract.snapshot_identity(peer_before["ruleset"])
            == contract.snapshot_identity(peer_after["ruleset"])
        )
        peer_initial: dict[str, tuple[int, int]] = contract.counter_values(peer_before["ruleset"])
        peer_final: dict[str, tuple[int, int]] = contract.counter_values(peer_after["ruleset"])
        if phase == "calibration":
            require(all(value == (0, 0) for value in peer_initial.values()))
        else:
            prior_peer = artifacts["peer-calibration-after.json"]["ruleset"]
            require(
                contract.snapshot_identity(prior_peer)
                == contract.snapshot_identity(peer_before["ruleset"])
            )
            require(contract.counter_values(prior_peer) == peer_initial)
        initial: dict[str, tuple[int, int]] = contract.counter_values(before["ruleset"])
        final: dict[str, tuple[int, int]] = contract.counter_values(after["ruleset"])
        require(len(report["results"]) == 14 and all(value == (0, 0) for value in initial.values()))
        prior_finish = 0.0
        for i, (case, result) in enumerate(zip(definitions, report["results"], strict=True)):
            for key in ("family", "address", "transport", "port"):
                require(result[key] == case[key])
            permitted = phase == "calibration" or case["permitted"]
            require(result["expected"] == ("response" if permitted else "policy_correlated_denial"))
            require(
                result["outcome"] == ("RESPONSE_MATCHED" if permitted else "NO_RESPONSE_UNVERIFIED")
            )
            begin, finish = (
                number(result["started_elapsed_seconds"]),
                number(result["finished_elapsed_seconds"]),
            )
            require(prior_finish <= begin <= finish <= 16 and finish - begin <= 1.1)
            require(finish <= (end - start).total_seconds() + 0.25)
            if not permitted:
                require(finish - begin >= 0.9)
            prior_finish = finish
            challenge = result["challenge_sha256"]
            require(
                re.fullmatch(r"[0-9a-f]{64}", challenge) is not None and challenge not in challenges
            )
            challenges.add(challenge)
            packets, size = final[f"m7_{i:02}"]
            require(packets > 0 and size >= packets * (20 if case["family"] == "ipv4" else 40))
            peer_old, peer_new = peer_initial[f"m7_{i:02}"], peer_final[f"m7_{i:02}"]
            peer_delta = tuple(new - old for old, new in zip(peer_old, peer_new, strict=True))
            require(
                (peer_delta[0] > 0 and peer_delta[1] > 0) if permitted else peer_delta == (0, 0)
            )
            if permitted:
                event = events[challenge]
                require(
                    event["case"] == i
                    and start + timedelta(seconds=begin - 0.25)
                    <= timestamp(event["at_utc"])
                    <= start + timedelta(seconds=finish + 0.25)
                )
                consumed.add(challenge)
            else:
                require(challenge not in events)
    require(
        len(phase_invocations) == 2
        and artifacts["listener-final.json"]["invocation_id"] not in phase_invocations
    )
    require(
        phase_times[0][1] <= phase_times[1][0]
        and (phase_times[1][1] - phase_times[0][0]).total_seconds() <= 40
    )
    require(consumed == set(events))
    return {
        "status": "SYNTHETIC_CONTROLS_CORRELATED_REVIEW_REQUIRED",
        "provider_calls": 0,
        "readiness": "UNVERIFIED",
        "effective_egress": "UNVERIFIED_PENDING_OPERATOR_ACCEPTANCE",
        "permitted_controls": 6,
        "denied_controls": 8,
        "calibration_responses": 14,
        "source_sha": manifest["source_sha"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args(argv)
    report: dict[str, Any] = {
        "status": "PREPARATION_ONLY",
        "provider_calls": 0,
        "readiness": "UNVERIFIED",
    }
    if args.evidence_dir is not None:
        try:
            report = evaluate(load_private(args.evidence_dir))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            IndexError,
            OverflowError,
            RecursionError,
        ):
            report = {
                "status": "NOT_VERIFIED",
                "reason_code": "EVIDENCE_INVALID_OR_INCOMPLETE",
                "provider_calls": 0,
                "readiness": "UNVERIFIED",
            }
    print(json.dumps(report, sort_keys=True))
    return 1 if report["status"] == "NOT_VERIFIED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
