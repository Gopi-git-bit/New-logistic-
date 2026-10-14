"""Target-boundary observations; optional credential metadata, never contents."""

from __future__ import annotations

import argparse
import errno
import json
import os
import platform
import re
import stat
from pathlib import Path
from typing import Any

BUNDLE = "/opt/zippy-m7-staging"
FIXTURE = "/var/lib/zippy-m7-denial-fixtures/readable.fixture"
CREDENTIAL_DIRECTORY = Path("/run/credentials/zippy-oms-staging-credential-probe.service")


def credential_metadata() -> dict[str, object]:
    """Inspect only the service-bound injected file; never read/hash its bytes."""
    directory_fd = credential_fd = -1
    try:
        directory_fd = os.open(CREDENTIAL_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        directory = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid not in {0, os.geteuid()}
            or stat.S_IMODE(directory.st_mode) not in {0o500, 0o700}
        ):
            return {"observation": "NOT_VERIFIED", "reason_code": "CREDENTIAL_DIRECTORY_UNSAFE"}
        credential_fd = os.open(
            "provider-key", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
        )
        info = os.fstat(credential_fd)
        safe = (
            stat.S_ISREG(info.st_mode)
            and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) in {0o400, 0o600}
            and info.st_nlink == 1
            and 1 <= info.st_size <= 2048
        )
        return {
            "observation": "PRIVATE_STAGING_FILE_OBSERVED" if safe else "NOT_VERIFIED",
            "uid": info.st_uid,
            "mode": oct(stat.S_IMODE(info.st_mode)),
            "bytes": info.st_size,
            "regular_file": stat.S_ISREG(info.st_mode),
            "links": info.st_nlink,
        }
    except OSError:
        return {"observation": "NOT_VERIFIED", "reason_code": "CREDENTIAL_UNAVAILABLE"}
    finally:
        try:
            if credential_fd >= 0:
                os.close(credential_fd)
        finally:
            if directory_fd >= 0:
                os.close(directory_fd)


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


def collect(expected_host: str, *, verify_credential: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "NOT_VERIFIED",
        "readiness": "UNVERIFIED",
        "host": platform.node(),
        "target_uid": os.geteuid(),
        "provider_calls": 0,
        "socket_attempts": 0,
        "configuration_changes": 0,
        "credential_loaded": False,
        "credential_contents_read": False,
        "credential_injection": "UNVERIFIED",
        "dedicated_key_scope": "UNVERIFIED",
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
        if verify_credential:
            try:
                report["credential_metadata"] = credential_metadata()
            except OSError:
                # Descriptor close errors must also be redacted and fail closed.
                report["credential_metadata"] = {"observation": "NOT_VERIFIED"}
            if report["credential_metadata"]["observation"] == "PRIVATE_STAGING_FILE_OBSERVED":
                report["credential_injection"] = "PRIVATE_STAGING_FILE_OBSERVED"
                report["status"] = "LOCAL_CREDENTIAL_CHECKS_PASSED"
            else:
                report["status"] = "NOT_VERIFIED"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", default="srv1943844")
    parser.add_argument("--verify-staging-credential", action="store_true")
    args = parser.parse_args(argv)
    report = collect(args.expected_host, verify_credential=args.verify_staging_credential)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in {"LOCAL_CHECKS_PASSED", "LOCAL_CREDENTIAL_CHECKS_PASSED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
