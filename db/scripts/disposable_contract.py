"""Pure admission, boundary and evidence checks for disposable PostgreSQL CI."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY = "Gopi-git-bit/New-logistic-"
WORKFLOW = REPOSITORY + "/.github/workflows/disposable-db-proofs.yml@refs/heads/main"
POSTGRES = "postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94"
PYTHON = "python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
CHECKS = {"api-tests", "python-checks", "security-scan", "secret-safety", "compose-config"}
GROUPS = {
    "operations": {
        "test_postgres_integration": 2,
        "test_dispatch_integration": 31,
        "test_finance_integration": 23,
        "test_payment_intent_privileges": 4,
    },
    "governance": {"test_integration": 12},
}
BASE_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}


class ProofError(ValueError):
    """A fixed public failure code, never command output or a credential."""


def require(ok: object, code: str) -> None:
    if not ok:
        raise ProofError(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "EXPIRY_REJECTED")
    return result.astimezone(UTC)


def admission(
    env: Mapping[str, str], sha: str, expiry: str, now: datetime | None = None
) -> dict[str, str]:
    require(re.fullmatch(r"[a-f0-9]{40}", sha), "SOURCE_REJECTED")
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REPOSITORY_ID": "1349197102",
        "GITHUB_REPOSITORY_OWNER_ID": "200721521",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ACTOR": "Gopi-git-bit",
        "GITHUB_ACTOR_ID": "200721521",
        "GITHUB_TRIGGERING_ACTOR": "Gopi-git-bit",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": sha,
        "GITHUB_WORKFLOW_SHA": sha,
        "GITHUB_WORKFLOW_REF": WORKFLOW,
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
    }
    require(all(env.get(k) == v for k, v in expected.items()), "ADMISSION_REJECTED")
    require(re.fullmatch(r"[1-9][0-9]{0,24}", env.get("GITHUB_RUN_ID", "")), "RUN_REJECTED")
    require(
        0 < (utc(expiry) - (now or datetime.now(UTC))).total_seconds() <= 3600, "EXPIRY_REJECTED"
    )
    return expected | {"GITHUB_RUN_ID": env["GITHUB_RUN_ID"]}


def ci_accept(run: dict[str, Any], jobs: list[dict[str, Any]], sha: str) -> None:
    require(
        run.get("head_sha") == sha
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
        and run.get("path") == ".github/workflows/ci.yml"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success",
        "CI_NOT_VERIFIED",
    )
    require(
        len(jobs) == 5
        and {j.get("name") for j in jobs} == CHECKS
        and all(
            j.get("head_sha") == sha
            and j.get("status") == "completed"
            and j.get("conclusion") == "success"
            for j in jobs
        ),
        "CI_NOT_VERIFIED",
    )


def read_private(path: Path, limit: int = 1_048_576) -> bytes:
    info = path.lstat()
    require(
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and not info.st_mode & 0o077
        and info.st_size <= limit,
        "PRIVATE_FILE_REJECTED",
    )
    return path.read_bytes()


def status_observation(text: str, uid: int) -> dict[str, Any]:
    fields = dict(line.split(":", 1) for line in text.splitlines() if ":" in line)
    require(uid > 0 and all(int(x) == uid for x in fields["Uid"].split()), "ROOT_OR_UID_REJECTED")
    require(
        int(fields["CapEff"].strip(), 16) == 0 and fields["NoNewPrivs"].strip() == "1",
        "PROCESS_PRIVILEGE_REJECTED",
    )
    return {
        "effective_uid": uid,
        "effective_capabilities": "0000000000000000",
        "no_new_privileges": True,
    }


def inspect_container(
    info: dict[str, Any],
    *,
    image: str,
    label: str,
    mounts: dict[str, tuple[str, bool]],
    test_uid: int | None,
) -> None:
    require(
        info["Config"]["Labels"].get("zippy.proof") == label and info["Image"] == image,
        "CONTAINER_IDENTITY_REJECTED",
    )
    host = info["HostConfig"]
    require(
        host["NetworkMode"] == "none"
        and not host.get("PortBindings")
        and not host.get("Privileged")
        and not host.get("PidMode")
        and host.get("IpcMode") == "private"
        and not host.get("Devices"),
        "CONTAINER_BOUNDARY_REJECTED",
    )
    persistent = [m for m in info["Mounts"] if m["Type"] in {"bind", "volume"}]
    observed = {m["Destination"]: (m["Source"], m["RW"]) for m in persistent}
    require(
        len(observed) == len(persistent)
        and observed == mounts
        and all(
            m["Type"] in {"bind", "volume"}
            or (m["Type"] == "tmpfs" and m["Destination"] in {"/tmp", "/out"})
            for m in info["Mounts"]
        ),
        "CONTAINER_MOUNTS_REJECTED",
    )
    maximum_memory = 2_147_483_648 if test_uid is not None else 1_073_741_824
    require(
        0 < host.get("Memory", 0) <= maximum_memory
        and 0 < host.get("NanoCpus", 0) <= 2_000_000_000
        and 0 < host.get("PidsLimit", 0) <= 256,
        "RESOURCE_CAP_REJECTED",
    )
    for target, flags in (host.get("Tmpfs") or {}).items():
        require(target in {"/tmp", "/out"}, "TMPFS_REJECTED")
        options = set(flags.split(","))
        limit = 8_388_608 if target == "/out" else 268_435_456
        require(
            {"noexec", "nosuid", "nodev"} <= options and f"size={limit}" in options,
            "TMPFS_REJECTED",
        )
    if test_uid is not None:
        require(
            info["Config"]["User"] == f"{test_uid}:{test_uid}"
            and host["ReadonlyRootfs"]
            and host.get("CapDrop") == ["ALL"]
            and not host.get("CapAdd")
            and any(
                flag in {"no-new-privileges", "no-new-privileges:true"}
                for flag in host.get("SecurityOpt", [])
            ),
            "TEST_BOUNDARY_REJECTED",
        )


def report_cases(path: Path, phase: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    # Keep the canonical existing checker as the minimum-count acceptance gate.
    from db.scripts.check_proof_report import verify_report

    data = read_private(path, 4_194_304)
    verify_report(path, phase)
    root = ET.fromstring(data)
    cases = [
        {"module": c.attrib["classname"].rsplit(".", 1)[-1], "name": c.attrib["name"]}
        for c in root.findall(".//testcase")
    ]
    for case in cases:
        require(
            re.fullmatch(r"[A-Za-z0-9_]{1,100}", case["module"])
            and re.fullmatch(r"[A-Za-z0-9_.:\[\], -]{1,300}", case["name"]),
            "TEST_IDENTITY_REJECTED",
        )
    counts = {module: sum(c["module"] == module for c in cases) for module in GROUPS[phase]}
    return cases, counts


def sanitized(value: dict[str, Any], secrets: list[str]) -> bytes:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    require(len(data) <= 1_048_576, "SUMMARY_TOO_LARGE")
    text = data.decode()
    require(
        not any(s and s in text for s in secrets)
        and not re.search(
            r"(?i)postgres(?:ql)?://|bearer\s+\S+|password\s*[=:]\s*[^\s,}]+|eyJ[\w-]+\.eyJ", text
        ),
        "SUMMARY_SECRET_REJECTED",
    )
    return data


def accept_runtime(
    result: dict[str, Any],
    path: Path,
    *,
    phase: str,
    source: str,
    run_id: str,
    nonce: str,
    uid: int,
) -> None:
    fields = {
        "schema",
        "phase",
        "source_sha",
        "run_id",
        "nonce",
        "process",
        "namespaces",
        "network_none_observed",
        "role",
        "restricted_role",
        "positive_authentication",
        "pytest_exit",
        "report_sha256",
        "cases",
        "integration_counts",
        "skips",
    }
    require(
        set(result) == fields
        and result["schema"] == 1
        and result["source_sha"] == source
        and result["run_id"] == run_id
        and result["nonce"] == nonce
        and result["phase"] == phase,
        "STALE_REPORT_REJECTED",
    )
    cases, counts = report_cases(path, phase)
    require(
        result["cases"] == cases
        and result["integration_counts"] == counts
        and result["report_sha256"] == digest(read_private(path, 4_194_304)),
        "REPORT_BINDING_REJECTED",
    )
    require(
        result["process"]
        == {
            "effective_uid": uid,
            "effective_capabilities": "0000000000000000",
            "no_new_privileges": True,
        }
        and uid > 0
        and result["pytest_exit"] == 0
        and result["skips"] == 0
        and result["restricted_role"] is True
        and result["positive_authentication"] is True
        and result["network_none_observed"] is True,
        "RUNTIME_RESULT_REJECTED",
    )
    expected_login = "zippy_m2_app_login" if phase == "operations" else "paperclip_m5_app_login"
    require(
        result["role"] == expected_login
        and set(result["namespaces"]) == {"net", "mnt", "ipc"}
        and all(type(v) is int and v > 0 for v in result["namespaces"].values()),
        "RUNTIME_RESULT_REJECTED",
    )
