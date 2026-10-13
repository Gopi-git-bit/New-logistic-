"""Credential-free observations from inside the prepared M7 target boundary."""

from __future__ import annotations

import argparse
import errno
import json
import os
import platform
import re
from pathlib import Path
from typing import Any

BUNDLE = "/opt/zippy-m7-staging"
FIXTURE = "/var/lib/zippy-m7-denial-fixtures/readable.fixture"


def process_fields(status: str) -> dict[str, object]:
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    uids = fields.get("Uid", "").split()
    uid = int(uids[1]) if len(uids) == 4 and all(x.isdigit() for x in uids) else None
    caps = fields.get("CapEff", "").strip()
    return {
        "effective_uid": uid,
        "effective_capabilities": caps if re.fullmatch(r"[0-9a-fA-F]{16}", caps) else None,
        "no_new_privileges": fields.get("NoNewPrivs", "").strip() == "1",
    }


def bundle_readonly(mounts: str) -> bool | None:
    # Require the actual explicit ReadOnlyPaths mount, not a template setting.
    matches = []
    for line in mounts.splitlines():
        words = line.split()
        if len(words) >= 6 and words[4] == BUNDLE:
            matches.append("ro" in words[5].split(","))
    # Do not infer which mount is effective from ambiguous stacked entries.
    return matches[0] if len(matches) == 1 else None


def namespace_inodes() -> dict[str, int]:
    return {name: (Path("/proc/self/ns") / name).stat().st_ino for name in ("net", "mnt", "ipc")}


def fixture_access() -> str:
    """Attempt only a read-only open of a fixed synthetic file; read no bytes."""
    try:
        fd = os.open(FIXTURE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return "OBSERVED_DENIAL" if exc.errno in {errno.EACCES, errno.EPERM} else "UNVERIFIED"
    os.close(fd)
    return "ACCESSIBLE"


def collect(expected_host: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "NOT_VERIFIED",
        "readiness": "UNVERIFIED",
        "host": platform.node(),
        "target_uid": os.geteuid(),
        "provider_calls": 0,
        "socket_attempts": 0,
        "configuration_changes": 0,
        "credential_loaded": False,
        "fixture_positive_control": "REQUIRED_OUTSIDE_TARGET",
        "effective_egress": "UNVERIFIED_NO_CONNECTIVITY_PROBES",
        "namespace_boundary": "UNVERIFIED_REQUIRES_HOST_COMPARISON",
        "business_mount_access": "UNVERIFIED_NO_BUSINESS_PATH_PROBES",
        "provider_state_store": "UNVERIFIED_NOT_MOUNTED_BY_PROBE",
        "spending_cap": "UNVERIFIED",
        "trusted_authorization": "UNVERIFIED",
    }
    if report["host"] != expected_host or platform.system() != "Linux":
        report["status"] = "WRONG_HOST"
        return report
    if report["target_uid"] == 0:
        report["status"] = "PRIVILEGED_TARGET"
        return report
    try:
        report["process"] = process_fields(Path("/proc/self/status").read_text())
        report["bundle_readonly"] = bundle_readonly(Path("/proc/self/mountinfo").read_text())
        report["namespace_inodes"] = namespace_inodes()
        report["synthetic_fixture_access"] = fixture_access()
    except OSError:
        report["observation_error"] = "METADATA_UNAVAILABLE"
        return report
    process = report["process"]
    if (
        process["effective_uid"] == report["target_uid"]
        and process["effective_capabilities"] == "0000000000000000"
        and process["no_new_privileges"]
        and report["bundle_readonly"] is True
        and report["synthetic_fixture_access"] == "OBSERVED_DENIAL"
    ):
        # This is not a positive-control, namespace, egress or readiness approval.
        report["status"] = "LOCAL_CHECKS_PASSED"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", default="srv1943844")
    report = collect(parser.parse_args(argv).expected_host)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "LOCAL_CHECKS_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
