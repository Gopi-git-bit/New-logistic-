"""Admit one owner/main build; optionally retain it, never publish or start it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPOSITORY = "Gopi-git-bit/New-logistic-"
WORKFLOW = REPOSITORY + "/.github/workflows/api-build-only.yml@refs/heads/main"
CANDIDATE_WORKFLOW = REPOSITORY + "/.github/workflows/api-candidate.yml@refs/heads/main"
BASE_IMAGE = (
    "python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
)
MARKER = "ZIPPY_API_BUILD_EVIDENCE "
DIGEST = r"sha256:[a-f0-9]{64}"
Command = Callable[[list[str], dict[str, str], float], str]


class BuildError(ValueError):
    """A closed build or evidence gate."""


def require(ok: object) -> None:
    if not ok:
        raise BuildError("BUILD_NOT_VERIFIED")


def admit(env: Mapping[str, str], source_sha: str, workflow: str = WORKFLOW) -> dict[str, str]:
    require(workflow in (WORKFLOW, CANDIDATE_WORKFLOW))
    require(re.fullmatch(r"[a-f0-9]{40}", source_sha))
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ACTOR": "Gopi-git-bit",
        "GITHUB_ACTOR_ID": "200721521",
        "GITHUB_TRIGGERING_ACTOR": "Gopi-git-bit",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": source_sha,
        "GITHUB_WORKFLOW_SHA": source_sha,
        "GITHUB_WORKFLOW_REF": workflow,
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
    }
    require(all(env.get(key) == value for key, value in expected.items()))
    require(re.fullmatch(r"[1-9][0-9]{0,24}", env.get("GITHUB_RUN_ID", "")))
    return expected | {"GITHUB_RUN_ID": env["GITHUB_RUN_ID"]}


def execute(argv: list[str], env: dict[str, str], timeout: float) -> str:
    result = subprocess.run(
        argv, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        # Do not attach captured output or environment to the exception/report.
        raise subprocess.CalledProcessError(result.returncode, argv[:3])
    return result.stdout + (result.stderr if argv[:3] == ["docker", "buildx", "build"] else "")


def safe_token(value: object, pattern: str = r"[A-Za-z0-9_.+!~:/() -]{1,200}") -> str:
    require(isinstance(value, str))
    require(re.fullmatch(pattern, str(value)))
    return str(value)


def downloads_match(receipt: dict[str, Any], lock: str) -> None:
    pins: dict[str, tuple[str, set[str]]] = {}
    for line in lock.replace("\\\n", " ").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, version = line.split()[0].split("==")
        name = re.sub(r"[-_.]+", "-", name).lower()
        pins[name] = (version, set(re.findall(r"--hash=sha256:([a-f0-9]{64})", line)))
    observed = receipt["pip_downloads"]
    require(len(observed) == len(pins))
    names = set()
    for item in observed:
        require(set(item) == {"name", "version", "url", "sha256"})
        name = safe_token(item["name"], r"[a-z0-9][a-z0-9-]{0,159}")
        require(name not in names and name in pins)
        names.add(name)
        require(item["version"] == pins[name][0] and item["sha256"] in pins[name][1])
        location = urlsplit(safe_token(item["url"], r"https://[A-Za-z0-9./%+_~-]{1,1256}"))
        require(
            location.hostname == "files.pythonhosted.org"
            and not location.username
            and not location.query
        )
    require(names == set(pins))


def build_receipt(log: str, lock: str) -> dict[str, Any]:
    # Only an actual BuildKit output line, not a Dockerfile instruction echo.
    lines = re.findall(r"^#[0-9]+ [0-9.]+ " + MARKER + r"(\{[^\n]+\})$", log, re.MULTILINE)
    require(len(lines) == 1 and len(lines[0]) < 200000)
    receipt: dict[str, Any] = json.loads(lines[0])
    require(
        set(receipt)
        == {
            "schema",
            "python",
            "pip",
            "os",
            "installed_os_packages",
            "pip_downloads",
            "pip_hash_evidence",
            "apt_archive_receipts",
        }
        and receipt["schema"] == 1
    )
    for key in ("python", "pip"):
        safe_token(receipt[key], r"[A-Za-z0-9_.+-]{1,80}")
    require(set(receipt["os"]) == {"ID", "VERSION_ID"})
    for value in receipt["os"].values():
        safe_token(value, r"[A-Za-z0-9_.+-]{1,80}")
    require(0 < len(receipt["installed_os_packages"]) < 2000)
    for item in receipt["installed_os_packages"]:
        require(set(item) == {"name", "version"})
        for value in item.values():
            safe_token(value, r"[A-Za-z0-9_.+!~:-]{1,160}")
    require(
        receipt["pip_hash_evidence"]
        == "pip --require-hashes plus installation-report v1; not independent capture"
    )
    require(
        receipt["apt_archive_receipts"]
        == "UNVERIFIED; installed versions only, mutable apt repositories"
    )
    downloads_match(receipt, lock)
    return receipt


def build(
    repo: Path,
    source_sha: str,
    env: Mapping[str, str],
    report: dict[str, Any],
    command: Command = execute,
    *,
    workflow: str = WORKFLOW,
    retain: Callable[[str, Path, Callable[[list[str], float], str]], None] | None = None,
) -> None:
    report["stage"] = "ADMISSION"
    report["run_identity"] = admit(env, source_sha, workflow)
    deadline = time.monotonic() + 720  # Leave hosted-job time for evidence and cleanup.
    with tempfile.TemporaryDirectory(prefix="zippy-api-build-", dir=env["RUNNER_TEMP"]) as raw:
        private = Path(raw)
        (private / "docker").mkdir(mode=0o700)
        child_env = {
            "PATH": os.defpath,
            "LC_ALL": "C",
            "HOME": str(private),
            "DOCKER_CONFIG": str(private / "docker"),
            "DOCKER_HOST": "unix:///var/run/docker.sock",
            "BUILDX_METADATA_PROVENANCE": "min",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_NO_REPLACE_OBJECTS": "1",
        }

        def run(args: list[str], limit: float = 30) -> str:
            remaining = deadline - time.monotonic()
            require(remaining > 0)
            entry: dict[str, Any] = {"stage": report["stage"], "exit_status": "NOT_VERIFIED"}
            report.setdefault("command_results", []).append(entry)
            try:
                output = command(args, child_env, min(limit, remaining))
                entry["exit_status"] = 0
                return output
            except subprocess.TimeoutExpired:
                entry["exit_status"] = "TIMEOUT"
                raise
            except subprocess.CalledProcessError as error:
                entry["exit_status"] = error.returncode
                raise

        report["stage"] = "SOURCE_AND_CONTEXT"
        require(run(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip() == source_sha)
        require(not run(["git", "-C", str(repo), "status", "--porcelain"]).strip())
        context = private / "context"
        manifest = json.loads(
            run(
                [
                    sys.executable,
                    "-I",
                    str(repo / "scripts/prepare_api_build_context.py"),
                    "--repo-root",
                    str(repo),
                    "--source-sha",
                    source_sha,
                    "--output",
                    str(context),
                ]
            )
        )
        require(manifest["status"] == "CONTEXT_PREPARED" and manifest["source_sha"] == source_sha)
        report["context"] = manifest
        dockerfile = (context / "Dockerfile.api").read_text()
        require(dockerfile.splitlines()[0] == "FROM " + BASE_IMAGE)
        report["stage"] = "PLACEHOLDER_CONFIGURATION"
        settings = json.loads(
            run(
                [
                    sys.executable,
                    "-I",
                    str(repo / "scripts/validate_api_staging_config.py"),
                    "--repo-root",
                    str(context),
                    "--manifest",
                    str(repo / "infra/staging/api-validation.compose.json"),
                ]
            )
        )
        require(settings["status"] == "OFFLINE_CONTRACT_VALIDATED")
        run(
            [
                "docker",
                "compose",
                "--env-file",
                os.devnull,
                "-f",
                str(repo / "infra/staging/api-validation.compose.json"),
                "--profile",
                "validation-only",
                "config",
                "--quiet",
            ]
        )
        report["placeholder_configuration"] = settings
        report["stage"] = "BUILD_TOOLCHAIN"
        report["tools"] = {
            "host_python": platform.python_version(),
            "docker_client": safe_token(
                run(["docker", "version", "--format", "{{.Client.Version}}"]).strip()
            ),
            "docker_server": safe_token(
                run(["docker", "version", "--format", "{{.Server.Version}}"]).strip()
            ),
            "buildx": safe_token(run(["docker", "buildx", "version"]).strip()),
            "compose": safe_token(run(["docker", "compose", "version", "--short"]).strip()),
        }
        # The default builder uses this runner's local daemon; refuse a remote driver.
        builder = run(["docker", "buildx", "inspect", "default"])
        require(re.search(r"^Driver:\s+docker\s*$", builder, re.MULTILINE))
        require(
            "unix:///var/run/docker.sock" in builder
            or re.search(r"^Endpoint:\s+default\s*$", builder, re.MULTILINE)
        )
        report["stage"] = "BASE_PLATFORM"
        index = json.loads(
            run(["docker", "buildx", "imagetools", "inspect", "--raw", BASE_IMAGE], 60)
        )
        candidates = [
            item["digest"]
            for item in index["manifests"]
            if item.get("platform", {}).get("os") == "linux"
            and item.get("platform", {}).get("architecture") == "amd64"
            and not item.get("platform", {}).get("variant")
        ]
        require(len(candidates) == 1)
        report["base"] = {
            "declared": BASE_IMAGE,
            "platform": "linux/amd64",
            "resolved_platform_manifest": safe_token(candidates[0], DIGEST),
        }
        original_images = set(run(["docker", "image", "ls", "--quiet", "--no-trunc"]).split())
        image_id = ""
        try:
            report["stage"] = "LOCAL_IMAGE_BUILD"
            log = run(
                [
                    "docker",
                    "buildx",
                    "build",
                    "--builder",
                    "default",
                    "--load",
                    "--pull",
                    "--no-cache",
                    "--platform",
                    "linux/amd64",
                    "--progress",
                    "plain",
                    "--iidfile",
                    str(private / "image-id"),
                    "--metadata-file",
                    str(private / "build-metadata.json"),
                    "-f",
                    str(context / "Dockerfile.api"),
                    str(context),
                ],
                600,
            )
            report["stage"] = "BUILD_EVIDENCE"
            image_id = safe_token((private / "image-id").read_text().strip(), DIGEST)
            report["local_image_id"] = image_id
            report["build_output_sha256"] = hashlib.sha256(log.encode()).hexdigest()
            report["dependencies"] = build_receipt(
                log, (context / "requirements-api.lock").read_text()
            )
            metadata = json.loads((private / "build-metadata.json").read_text())
            config_digest = safe_token(metadata["containerimage.config.digest"], DIGEST)
            require(config_digest == image_id)
            report["build_metadata"] = {"config_digest": config_digest}
            image = json.loads(
                run(["docker", "image", "inspect", "--format", "{{json .}}", image_id])
            )
            require(
                image["Id"] == image_id
                and image["Os"] == "linux"
                and image["Architecture"] == "amd64"
            )
            require(image["Config"]["User"] == "10001:10001")
            report["configured_image_user"] = "10001:10001"
            if retain is not None:
                report["stage"] = "RETAIN_CANDIDATE"
                retain(image_id, private, run)
        finally:
            # An iidfile can exist even if receipt validation or the CLI fails.
            candidate = private / "image-id"
            if not image_id and candidate.is_file():
                value = candidate.read_text().strip()
                if re.fullmatch(DIGEST, value):
                    image_id = value
            report["cleanup"] = {
                "new_local_image_removed": False,
                "build_cache": "hosted-runner teardown; no broad prune",
                "image_remove_exit_status": "NOT_NEEDED_OR_NOT_REACHED",
            }
            if image_id and image_id not in original_images:
                try:
                    command(["docker", "image", "rm", image_id], child_env, 15)
                except subprocess.CalledProcessError as error:
                    report["cleanup"]["image_remove_exit_status"] = error.returncode
                    raise
                except subprocess.TimeoutExpired:
                    report["cleanup"]["image_remove_exit_status"] = "TIMEOUT"
                    raise
                report["cleanup"]["new_local_image_removed"] = True
                report["cleanup"]["image_remove_exit_status"] = 0
            elif image_id:
                report["cleanup"]["preexisting_image_preserved"] = True
        report["stage"] = "COMPLETE"
        report["status"] = "BUILD_ONLY_PASSED"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {
        "status": "BUILD_NOT_VERIFIED",
        "runtime_readiness": "UNVERIFIED",
        "image_publication": "NOT_RUN",
        "application_start": "NOT_RUN",
        "provider_calls": 0,
        "vps_changes": 0,
        "gaps": [
            "apt archive origins/hashes and repository snapshots not captured",
            "upstream redirects, transport mirrors and effective egress not independently observed",
            "hosted runner/build tools observed, not locked; whole-image bit reproducibility unproven",
            "local config ID is not a published registry manifest or deployment acceptance",
            "daemon cancellation after CLI timeout not independently proven; hosted runner teardown required",
        ],
    }
    # A fresh report only; never overwrite another run's evidence.
    os.umask(0o077)
    with args.report.open("x") as output:
        try:
            build(args.repo_root, args.source_sha, os.environ, report)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            IndexError,
            subprocess.SubprocessError,
        ) as error:
            # Malformed nested tool output must also leave a failed audit record.
            # Retain only the exception class, never its message or captured output.
            report["failure_class"] = type(error).__name__
            report["status"] = "BUILD_NOT_VERIFIED"
        json.dump(report, output, sort_keys=True, indent=2)
        output.write("\n")
    return 0 if report["status"] == "BUILD_ONLY_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
