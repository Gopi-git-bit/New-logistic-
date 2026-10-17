"""Build and scan one candidate; export only an encrypted, run-bound artifact."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import tarfile
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def contract() -> Any:
    spec = importlib.util.spec_from_file_location(
        "candidate", Path(__file__).with_name("api_candidate_contract.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = contract()
FILES = {"image.tar", "build.json", "scan.json", "sbom.json", "database.json", "provenance.json"}


def security(scan: dict[str, Any], sbom: dict[str, Any], image: str) -> None:
    c.require(scan["SchemaVersion"] == 2 and scan["ArtifactType"] == "container_image")
    c.require(scan["Metadata"]["ImageID"] == image and scan["Results"], "SCAN_NOT_BOUND_TO_IMAGE")
    for result in scan["Results"]:
        for field in ("Vulnerabilities", "Secrets"):
            c.require(
                not any(v["Severity"] in ("HIGH", "CRITICAL") for v in result.get(field, [])),
                "IMAGE_SECURITY_FAILED",
            )
    c.require(sbom["bomFormat"] == "CycloneDX" and sbom["specVersion"] in ("1.5", "1.6"))
    c.require(sbom["components"], "SBOM_EMPTY")


def database(cache: Path, now: datetime | None = None) -> dict[str, Any]:
    metadata = c.json_file(cache / "db/metadata.json")
    updated = datetime.fromisoformat(metadata["UpdatedAt"].replace("Z", "+00:00"))
    instant = now or datetime.now(UTC)
    c.require(
        metadata["Version"] == 2 and 0 <= (instant - updated).total_seconds() <= 86400,
        "SCANNER_DATABASE_STALE",
    )
    c.require(instant < datetime.fromisoformat(metadata["NextUpdate"].replace("Z", "+00:00")))
    return {"metadata": metadata, "trivy_db_sha256": c.digest(cache / "db/trivy.db")}


def retain(image: str, archive: Path, run: Callable[[list[str], float], str]) -> None:
    run(["docker", "image", "save", "--output", str(archive), image], 90)
    c.image_archive(archive, image)


def prepare(
    repo: Path, source: str, env: dict[str, str], output: Path, result: dict[str, Any]
) -> None:
    auth = c.admit(env, source)
    c.source_check(repo, source)
    settings = c.policy(repo)
    result["stage"] = "ADMITTED"
    result["post_merge_ci_run"] = c.green_ci(source, env["GH_READ_TOKEN"])
    output.mkdir(mode=0o700)  # Fresh destination only; never export plaintext from here.
    with tempfile.TemporaryDirectory(prefix="api-candidate-", dir=env["RUNNER_TEMP"]) as raw:
        private = Path(raw)
        tools = private / "tools"
        c.install_tools(settings, tools, ("age", "crane", "trivy"))
        child = c.clean_env(private, tools)
        build_report: dict[str, Any] = {"provider_calls": 0, "image_publication": "NOT_RUN"}
        archive = private / "image.tar"
        result["stage"] = "BUILD_RETAIN"
        try:
            c.load_script("run_api_build").build(
                repo,
                source,
                env,
                build_report,
                workflow=c.WORKFLOW,
                retain=lambda image, scratch, run: retain(image, archive, run),
            )
        finally:
            result["build_stage"] = build_report.get("stage", "NOT_VERIFIED")
            result["build_cleanup"] = build_report.get("cleanup", "NOT_REACHED")
        c.require(build_report["status"] == "BUILD_ONLY_PASSED")
        c.require(
            build_report["cleanup"].get("new_local_image_removed"), "PREEXISTING_IMAGE_REFUSED"
        )
        c.write_json(private / "build.json", build_report)
        result["stage"] = "IMAGE_SECURITY"
        c.command([str(tools / "crane"), "validate", "--tarball", str(archive)], child, 120)
        manifest_digest = c.command(
            [str(tools / "crane"), "digest", "--tarball", str(archive)], child
        ).strip()
        c.require(re.fullmatch(c.DIGEST, manifest_digest))
        image = c.image_archive(archive, build_report["local_image_id"])
        cache = private / "trivy-cache"
        flags = [
            str(tools / "trivy"),
            "image",
            "--input",
            str(archive),
            "--config",
            "",
            "--ignorefile",
            os.devnull,
            "--cache-dir",
            str(cache),
            "--timeout",
            "3m",
            "--db-repository",
            "ghcr.io/aquasecurity/trivy-db:2",
            "--disable-telemetry",
            "--skip-version-check",
            "--offline-scan",
        ]
        c.command(
            flags
            + [
                "--scanners",
                "vuln,secret",
                "--image-config-scanners",
                "secret",
                "--severity",
                "HIGH,CRITICAL",
                "--exit-code",
                "1",
                "--format",
                "json",
                "--output",
                str(private / "scan.json"),
            ],
            child,
            210,
        )
        db = database(cache)
        c.write_json(private / "database.json", db)
        c.command(
            flags
            + ["--skip-db-update", "--format", "cyclonedx", "--output", str(private / "sbom.json")],
            child,
            120,
        )
        security(
            c.json_file(private / "scan.json"),
            c.json_file(private / "sbom.json"),
            image["config_digest"],
        )
        c.require(database(cache) == db, "SCANNER_DATABASE_CHANGED")
        provenance = {
            "schema": 1,
            "authenticity": "unsigned workflow evidence; not a signed attestation",
            "authorization": auth,
            "registry": c.REGISTRY,
            "visibility": "private",
            "deployable": False,
            "image": image,
            "manifest_digest": manifest_digest,
            "tools": settings["tools"],
            "gaps": settings["gaps"],
            "policy_sha256": c.digest(repo / "infra/publication/api-candidate-policy.json"),
            "files": {
                name: c.digest(private / name) for name in sorted(FILES - {"provenance.json"})
            },
        }
        c.write_json(private / "provenance.json", provenance)
        bundle = private / "candidate.tar"
        with tarfile.open(bundle, "w", format=tarfile.USTAR_FORMAT) as package:
            for name in sorted(FILES):
                package.add(private / name, arcname=name, recursive=False)
        c.require(bundle.stat().st_size <= c.LIMIT)
        c.admit(env, source)  # Recheck expiry after build/scan, before exporting.
        result["stage"] = "ENCRYPT_EXPORT"
        cipher = output / "candidate.age"
        c.command(
            [
                str(tools / "age"),
                "--recipient",
                settings["recipient"],
                "--output",
                str(cipher),
                str(bundle),
            ],
            child,
        )
        c.require(0 < cipher.stat().st_size <= c.LIMIT)
        identity = {
            "schema": 1,
            "source_sha": source,
            "run_id": auth["run_id"],
            "authorization": auth,
            "cipher_sha256": c.digest(cipher),
            "bundle_sha256": c.digest(bundle),
            "provenance_sha256": c.digest(private / "provenance.json"),
            "manifest_digest": manifest_digest,
        }
        c.write_json(output / "transfer.json", identity)
        with Path(env["GITHUB_OUTPUT"]).open("a") as stream:
            stream.write("cipher_sha256=" + identity["cipher_sha256"] + "\n")
            stream.write("transfer_sha256=" + c.digest(output / "transfer.json") + "\n")
        result.update(
            status="ENCRYPTED_CANDIDATE_PREPARED",
            stage="COMPLETE",
            source_sha=source,
            run_id=auth["run_id"],
            cipher_sha256=identity["cipher_sha256"],
            manifest_digest=manifest_digest,
            image_publication="NOT_RUN",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    report: dict[str, Any] = {
        "status": "CANDIDATE_NOT_VERIFIED",
        "stage": "ADMISSION",
        "provider_calls": 0,
        "vps_changes": 0,
        "publication": "NOT_RUN",
    }
    with args.report.open("x") as stream:
        try:
            prepare(args.repo_root, args.source_sha, dict(os.environ), args.output, report)
        except Exception as error:
            # External output, exception strings, tokens and image contents never reach public logs.
            report["failure_class"] = type(error).__name__
            report["status"] = "CANDIDATE_NOT_VERIFIED"
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
    return 0 if report["status"] == "ENCRYPTED_CANDIDATE_PREPARED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
