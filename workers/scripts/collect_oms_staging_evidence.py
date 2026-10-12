"""Passive local metadata only; never starts a service or calls a provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

SERVICE = "zippy-oms-staging.service"
NAMESPACE = "zippy-oms-staging"
PROPERTIES = (
    "LoadState",
    "ActiveState",
    "MainPID",
    "User",
    "DynamicUser",
    "NetworkNamespacePath",
    "NoNewPrivileges",
    "ProtectSystem",
    "ProtectHome",
    "PrivateTmp",
    "PrivateDevices",
    "PrivateIPC",
    "CapabilityBoundingSet",
    "AmbientCapabilities",
)
MOUNTS = frozenset(
    {
        "/",
        "/opt/zippy-m7-staging",
        "/opt/new-logistic",
        "/opt/paperclip",
        "/var/lib/postgresql",
        "/var/lib/docker",
        "/run/docker.sock",
        "/etc/zippy",
    }
)


def observe(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode or len(result.stdout) > 262_144:
        return None
    return result.stdout


def file_metadata(path: Path) -> dict[str, object] | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    return {
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "bytes": info.st_size,
        "regular_file": stat.S_ISREG(info.st_mode),
        "directory": stat.S_ISDIR(info.st_mode),
        "symlink": stat.S_ISLNK(info.st_mode),
        "links": info.st_nlink,
    }


def parse_process(status: str, mounts: str) -> dict[str, object]:
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    uids = fields.get("Uid", "").split()
    uid = int(uids[1]) if len(uids) == 4 and all(x.isdigit() for x in uids) else None
    caps = fields.get("CapEff", "").strip()
    return {
        "effective_uid": uid,
        "identity_observation": "UNVERIFIED"
        if uid is None
        else ("PRIVILEGED" if uid == 0 else "NONROOT_OBSERVED"),
        "effective_capabilities": caps if re.fullmatch(r"[0-9a-fA-F]{16}", caps) else None,
        "matching_mounts": [
            {"path": words[4], "options": words[5].split(",")}
            for line in mounts.splitlines()
            if len(words := line.split()) >= 6 and words[4] in MOUNTS
        ],
        "mount_access_denial": "UNVERIFIED_NO_ACCESS_PROBE",
    }


def nft_metadata(text: str | None) -> dict[str, object] | None:
    if text is None:
        return None
    try:
        data = json.loads(text)
        entries = data["nftables"]
        policies = {
            c["name"]: c.get("policy")
            for item in entries
            if isinstance(c := item.get("chain"), dict)
            and c.get("family") == "inet"
            and c.get("table") == "zippy_oms_staging"
            and c.get("name") in {"input", "output", "forward"}
        }
        sets = {
            s["name"]: len(s.get("elem", []))
            for item in entries
            if isinstance(s := item.get("set"), dict)
            and s.get("family") == "inet"
            and s.get("table") == "zippy_oms_staging"
            and s.get("name") in {"provider_v4", "provider_v6", "dns_v4", "dns_v6"}
        }
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return {
        "chain_policies": policies,
        "destination_set_counts": sets,
        "rules_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "effective_destination_denial": "UNVERIFIED_NO_CONNECTIVITY_PROBES",
    }


def collect(expected_host: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "EVIDENCE_ONLY",
        "readiness": "UNVERIFIED",
        "host": platform.node(),
        "observer_uid": os.geteuid(),
        "provider_calls": 0,
        "configuration_changes": 0,
        "spending_cap": "UNVERIFIED",
        "trusted_authorization": "UNVERIFIED",
    }
    if report["host"] != expected_host or platform.system() != "Linux":
        report["status"] = "WRONG_HOST"
        return report
    output = observe(["systemctl", "show", SERVICE, *[f"--property={p}" for p in PROPERTIES]])
    properties = (
        {}
        if output is None
        else {
            k: v
            for line in output.splitlines()
            if "=" in line
            for k, v in [line.split("=", 1)]
            if k in PROPERTIES
        }
    )
    report["service_properties"] = properties
    report["credential_metadata"] = file_metadata(Path("/etc/zippy/m7-staging/provider.key"))
    report["state_metadata"] = file_metadata(Path("/var/lib/zippy-m7-oms"))
    pid = properties.get("MainPID", "0")
    if pid.isdigit() and int(pid) > 0:
        root = Path("/proc") / pid
        try:
            report["process"] = parse_process(
                (root / "status").read_text(), (root / "mountinfo").read_text()
            )
            report["process"]["named_namespace_matches"] = (root / "ns/net").stat().st_ino == Path(
                f"/run/netns/{NAMESPACE}"
            ).stat().st_ino
            report["process"]["separate_mount_namespace"] = (root / "ns/mnt").stat().st_ino != Path(
                "/proc/self/ns/mnt"
            ).stat().st_ino
        except OSError:
            report["process_observation"] = "UNVERIFIED_PROCESS_UNAVAILABLE"
    else:
        report["process_observation"] = "UNVERIFIED_NO_RUNNING_TARGET"
    report["namespace_firewall"] = nft_metadata(
        observe(
            [
                "ip",
                "netns",
                "exec",
                NAMESPACE,
                "nft",
                "-j",
                "list",
                "table",
                "inet",
                "zippy_oms_staging",
            ]
        )
    )
    # Facts only: no provider credential read, service start, nft apply or curl.
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", default="srv1943844")
    args = parser.parse_args(argv)
    report = collect(args.expected_host)
    print(json.dumps(report, sort_keys=True))
    return 2 if report["status"] == "WRONG_HOST" else 0


if __name__ == "__main__":
    raise SystemExit(main())
