"""Publish a verified encrypted candidate without a daemon, build or application start."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import tempfile
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


def transfer(folder: Path, env: dict[str, str], auth: dict[str, Any], token: str) -> dict[str, Any]:
    c.require({p.name for p in folder.iterdir()} == {"candidate.age", "transfer.json"})
    c.require(all(p.is_file() and not p.is_symlink() for p in folder.iterdir()))
    c.require(0 < (folder / "candidate.age").stat().st_size <= c.LIMIT)
    c.require(c.digest(folder / "transfer.json") == env["API_TRANSFER_SHA256"])
    record: dict[str, Any] = c.json_file(folder / "transfer.json")
    c.require(record["schema"] == 1 and record["source_sha"] == auth["source_sha"])
    c.require(record["run_id"] == auth["run_id"] and record["authorization"] == auth)
    c.require(
        c.digest(folder / "candidate.age") == record["cipher_sha256"] == env["API_CIPHER_SHA256"]
    )
    c.require(re.fullmatch(r"[1-9][0-9]{0,24}", env["API_ARTIFACT_ID"]))
    artifact = c.api(
        "/repos/" + c.REPOSITORY + "/actions/artifacts/" + env["API_ARTIFACT_ID"], token
    )
    c.require(artifact["id"] == int(env["API_ARTIFACT_ID"]) and not artifact["expired"])
    c.require(artifact["name"] == "encrypted-api-candidate-" + auth["run_id"])
    c.require(
        artifact["digest"] == env["API_ARTIFACT_DIGEST"]
        and re.fullmatch(c.DIGEST, artifact["digest"])
    )
    c.require(artifact["workflow_run"]["id"] == int(auth["run_id"]))
    c.require(artifact["workflow_run"]["head_sha"] == auth["source_sha"])
    c.require(artifact["workflow_run"]["repository_id"] == 1349197102)
    c.require(0 < artifact["size_in_bytes"] <= c.LIMIT)
    return record


def evidence(
    folder: Path,
    record: dict[str, Any],
    auth: dict[str, Any],
    settings: dict[str, Any],
    policy_digest: str,
) -> dict[str, Any]:
    proof: dict[str, Any] = c.json_file(folder / "provenance.json")
    c.require(c.digest(folder / "provenance.json") == record["provenance_sha256"])
    c.require(proof["schema"] == 1 and proof["authorization"] == auth)
    c.require(
        proof["registry"] == c.REGISTRY
        and proof["visibility"] == "private"
        and proof["deployable"] is False
    )
    c.require(proof["policy_sha256"] == policy_digest and proof["tools"] == settings["tools"])
    c.require(proof["gaps"] == settings["gaps"])
    c.require(proof["authenticity"] == "unsigned workflow evidence; not a signed attestation")
    c.require(set(proof["files"]) == FILES - {"provenance.json"})
    for name, expected in proof["files"].items():
        c.require(c.digest(folder / name) == expected, "RETAINED_EVIDENCE_CHANGED")
    build = c.json_file(folder / "build.json")
    c.require(build["status"] == "BUILD_ONLY_PASSED" and build["run_identity"] == auth["identity"])
    c.require(build["context"]["source_sha"] == auth["source_sha"])
    c.require(
        build["configured_image_user"] == "10001:10001"
        and build["cleanup"]["new_local_image_removed"]
    )
    c.require(build["provider_calls"] == 0 and build["image_publication"] == "NOT_RUN")
    c.require(c.image_archive(folder / "image.tar", build["local_image_id"]) == proof["image"])
    c.require(proof["manifest_digest"] == record["manifest_digest"])
    c.load_script("run_api_candidate").security(
        c.json_file(folder / "scan.json"),
        c.json_file(folder / "sbom.json"),
        build["local_image_id"],
    )
    # Scan DB identity is retained; require its validity through publication as well.
    db = c.json_file(folder / "database.json")
    now = datetime.now(UTC)
    updated = datetime.fromisoformat(db["metadata"]["UpdatedAt"].replace("Z", "+00:00"))
    next_update = datetime.fromisoformat(db["metadata"]["NextUpdate"].replace("Z", "+00:00"))
    c.require(
        db["metadata"]["Version"] == 2
        and 0 <= (now - updated).total_seconds() <= 86400
        and now < next_update
    )
    c.require(re.fullmatch(c.DIGEST, db["trivy_db_sha256"]))
    return proof


def registry_evidence(
    manifest: str, config: str, expected: str, image: dict[str, Any]
) -> dict[str, Any]:
    c.require("sha256:" + hashlib.sha256(manifest.encode()).hexdigest() == expected)
    m = json.loads(manifest)
    c.require(
        m["schemaVersion"] == 2
        and m["mediaType"]
        in (
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
        )
    )
    c.require(m["config"]["digest"] == image["config_digest"])
    c.require("sha256:" + hashlib.sha256(config.encode()).hexdigest() == image["config_digest"])
    body = json.loads(config)
    c.require(body["os"] == "linux" and body["architecture"] == "amd64")
    c.require(
        body["config"]["User"] == "10001:10001" and body["rootfs"]["diff_ids"] == image["diff_ids"]
    )
    c.require(len(m["layers"]) == len(image["diff_ids"]))
    for layer in m["layers"]:
        c.require(
            re.fullmatch(c.DIGEST, layer["digest"])
            and type(layer["size"]) is int
            and layer["size"] > 0
        )
        c.require(not layer.get("urls"), "FOREIGN_LAYER_REFUSED")
    return {
        "manifest_digest": expected,
        "config_digest": image["config_digest"],
        "layers": [{"digest": item["digest"], "size": item["size"]} for item in m["layers"]],
        "platform": "linux/amd64",
        "remote_layer_validation": "PASSED",
    }


def publish(
    repo: Path, source: str, env: dict[str, str], folder: Path, result: dict[str, Any]
) -> None:
    auth = c.admit(env, source)
    c.source_check(repo, source)
    settings = c.policy(repo)
    token = env["GH_PUBLISH_TOKEN"]
    c.require(token and env["CANDIDATE_AGE_IDENTITY"], "PUBLICATION_CREDENTIAL_MISSING")
    result["post_merge_ci_run"] = c.green_ci(source, token)
    result["stage"] = "TRANSFER"
    record = transfer(folder, env, auth, token)
    with tempfile.TemporaryDirectory(prefix="api-publish-", dir=env["RUNNER_TEMP"]) as raw:
        private = Path(raw)
        tools = private / "tools"
        c.install_tools(settings, tools, ("age", "crane"))
        child = c.clean_env(private, tools)
        (private / "docker").mkdir(mode=0o700)
        identity = private / "identity.txt"
        with identity.open("x") as output:
            output.write(env["CANDIDATE_AGE_IDENTITY"] + "\n")
        bundle = private / "candidate.tar"
        result["stage"] = "DECRYPT_VALIDATE"
        c.command(
            [
                str(tools / "age"),
                "--decrypt",
                "--identity",
                str(identity),
                "--output",
                str(bundle),
                str(folder / "candidate.age"),
            ],
            child,
        )
        identity.unlink()
        c.require(c.digest(bundle) == record["bundle_sha256"])
        c.unpack(bundle, private, FILES)
        proof = evidence(
            private,
            record,
            auth,
            settings,
            c.digest(repo / "infra/publication/api-candidate-policy.json"),
        )
        archive = private / "image.tar"
        c.command([str(tools / "crane"), "validate", "--tarball", str(archive)], child, 120)
        expected = c.command(
            [str(tools / "crane"), "digest", "--tarball", str(archive)], child
        ).strip()
        c.require(re.fullmatch(c.DIGEST, expected) and expected == proof["manifest_digest"])
        result["stage"] = "REGISTRY_PREFLIGHT"
        before = c.package_check(settings, token)  # 404/unknown stops: no implicit bootstrap.
        c.command(
            [
                str(tools / "crane"),
                "auth",
                "login",
                "ghcr.io",
                "--username",
                "Gopi-git-bit",
                "--password-stdin",
            ],
            child,
            stdin=token,
        )
        tags = c.command([str(tools / "crane"), "ls", c.REGISTRY], child).splitlines()
        c.require(auth["tag"] not in tags, "CANDIDATE_TAG_ALREADY_EXISTS")
        c.admit(env, source)
        c.policy(repo)
        c.green_ci(source, token)
        c.require(c.package_check(settings, token) == before)
        reference = c.REGISTRY + ":" + auth["tag"]
        result.update(
            stage="PUSH",
            publication_state="PUSH_ATTEMPTED_REMOTE_STATE_UNKNOWN",
            push_attempts=1,
            reference=reference,
            expected_manifest_digest=expected,
            artifact_id=env["API_ARTIFACT_ID"],
        )
        remaining = (c.utc(auth["expires_utc"]) - datetime.now(UTC)).total_seconds()
        c.require(remaining > 0)
        c.command(
            [str(tools / "crane"), "push", str(archive), reference], child, min(180, remaining)
        )
        result["stage"] = "REGISTRY_READBACK"
        resolved = c.command([str(tools / "crane"), "digest", reference], child).strip()
        c.require(resolved == expected, "REGISTRY_DIGEST_MISMATCH")
        immutable = c.REGISTRY + "@" + expected
        manifest = c.command([str(tools / "crane"), "manifest", immutable], child)
        config = c.command([str(tools / "crane"), "config", immutable], child)
        # Do not use --fast: validate all referenced remote layers and their content hashes.
        c.command([str(tools / "crane"), "validate", "--remote", immutable], child, 180)
        observed = registry_evidence(manifest, config, expected, proof["image"])
        c.require(c.package_check(settings, token) == before)
        # Keep detailed evidence encrypted even though the source repository is public.
        c.write_json(
            private / "publication.json",
            {
                "authorization": auth,
                "registry": observed,
                "package": before,
                "artifact_id": env["API_ARTIFACT_ID"],
                "provenance_sha256": record["provenance_sha256"],
                "gaps": proof["gaps"],
            },
        )
        destination = Path(env["API_PRIVATE_RESULT"])
        c.require(not destination.exists())
        c.command(
            [
                str(tools / "age"),
                "--recipient",
                settings["recipient"],
                "--output",
                str(destination),
                str(private / "publication.json"),
            ],
            child,
        )
        result.update(
            status="PRIVATE_CANDIDATE_PUBLISHED",
            stage="COMPLETE",
            publication_state="PRIVATE_DIGEST_VERIFIED",
            manifest_digest=expected,
            encrypted_evidence_sha256=c.digest(destination),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    report: dict[str, Any] = {
        "status": "PUBLICATION_NOT_VERIFIED",
        "stage": "ADMISSION",
        "publication_state": "NOT_ATTEMPTED",
        "push_attempts": 0,
        "provider_calls": 0,
        "vps_changes": 0,
        "deployment": "NOT_RUN",
        "runtime_readiness": "UNVERIFIED",
    }
    with args.report.open("x") as stream:
        try:
            publish(args.repo_root, args.source_sha, dict(os.environ), args.artifact, report)
        except Exception as error:
            report["failure_class"] = type(error).__name__
            report["status"] = "PUBLICATION_NOT_VERIFIED"
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
    return 0 if report["status"] == "PRIVATE_CANDIDATE_PUBLISHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
