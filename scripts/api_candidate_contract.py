"""Closed candidate contracts and bounded, pinned tools; no application imports."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY = "Gopi-git-bit/New-logistic-"
REGISTRY = "ghcr.io/gopi-git-bit/zippy-api"
WORKFLOW = REPOSITORY + "/.github/workflows/api-candidate.yml@refs/heads/main"
GAPS = "REPRO-01,REPRO-02,REPRO-03,REPRO-04"
DIGEST = r"sha256:[a-f0-9]{64}"
LIMIT = 2 * 1024**3
JSON_LIMIT = 20 * 1024**2
CHECKS = {"api-tests", "python-checks", "security-scan", "secret-safety", "compose-config"}


def require(condition: object, code: str = "CANDIDATE_NOT_VERIFIED") -> None:
    if not condition:
        raise ValueError(code)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    require(spec is not None and spec.loader is not None)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def json_file(path: Path) -> Any:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= JSON_LIMIT)
    return json.loads(path.read_text())


def utc(value: str) -> datetime:
    require(bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value)))
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def admit(env: Mapping[str, str], source: str, now: datetime | None = None) -> dict[str, Any]:
    identity = load_script("run_api_build").admit(env, source, WORKFLOW)
    instant = now or datetime.now(UTC)
    expiry = utc(env.get("API_AUTHORIZATION_EXPIRES", ""))
    require(0 < (expiry - instant).total_seconds() <= 3600, "AUTHORIZATION_EXPIRED_OR_TOO_LONG")
    require(env.get("API_ACCEPT_GAPS") == GAPS, "GAPS_NOT_EXPLICITLY_ACCEPTED")
    require(
        env.get("API_PUBLICATION_SCOPE") == "one-private-nondeployable-candidate", "WRONG_SCOPE"
    )
    return {
        "identity": identity,
        "expires_utc": env["API_AUTHORIZATION_EXPIRES"],
        "accepted_gaps": GAPS.split(","),
        "scope": "one-private-nondeployable-candidate",
        "tag": "candidate-" + source + "-" + env["GITHUB_RUN_ID"],
        "source_sha": source,
        "run_id": env["GITHUB_RUN_ID"],
    }


def policy(repo: Path, now: datetime | None = None) -> dict[str, Any]:
    result: dict[str, Any] = json_file(repo / "infra/publication/api-candidate-policy.json")
    require(result["schema"] == 1 and result["registry"] == REGISTRY)
    require(result["visibility"] == "private" and result["max_archive_bytes"] == LIMIT)
    require(result["artifact_retention_days"] == 1)
    require(type(result["package_id"]) is int and result["package_id"] > 0, "PACKAGE_NOT_APPROVED")
    require(
        isinstance(result["recipient"], str)
        and re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", result["recipient"]),
        "RECIPIENT_NOT_PINNED",
    )
    require(
        isinstance(result["access_review_sha256"], str)
        and re.fullmatch(r"[a-f0-9]{64}", result["access_review_sha256"]),
        "ACCESS_REVIEW_MISSING",
    )
    require(
        utc(result["access_review_expires_utc"]) > (now or datetime.now(UTC)),
        "ACCESS_REVIEW_EXPIRED",
    )
    require(set(result["gaps"]) == set(GAPS.split(",")))
    require(set(result["tools"]) == {"age", "crane", "trivy"})
    return result


def clean_env(home: Path, tools: Path) -> dict[str, str]:
    return {
        "PATH": str(tools) + os.pathsep + os.defpath,
        "HOME": str(home),
        "DOCKER_CONFIG": str(home / "docker"),
        "LC_ALL": "C",
        "TZ": "UTC",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
    }


def source_check(repo: Path, source: str) -> None:
    environment = {
        "PATH": os.defpath,
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    require(
        command(["git", "-C", str(repo), "rev-parse", "HEAD"], environment, 10).strip() == source,
        "CHECKOUT_SOURCE_MISMATCH",
    )
    require(
        not command(["git", "-C", str(repo), "status", "--porcelain"], environment, 10).strip(),
        "DIRTY_CHECKOUT_REFUSED",
    )


def command(
    args: list[str], env: dict[str, str], timeout: float = 120, stdin: str | None = None
) -> str:
    result = subprocess.run(
        args, env=env, input=stdin, capture_output=True, text=True, timeout=timeout, check=False
    )
    require(result.returncode == 0, "TOOL_FAILED")
    return result.stdout


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def api(path: str, token: str) -> Any:
    # Fixed API origin, no credential-bearing redirects, no shell/CLI token argument.
    require(
        path.startswith("/repos/" + REPOSITORY + "/")
        or path == "/users/Gopi-git-bit/packages/container/zippy-api"
    )
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open(
        request, timeout=15
    ) as response:
        raw = response.read(JSON_LIMIT + 1)
    require(len(raw) <= JSON_LIMIT)
    return json.loads(raw)


def green_ci(source: str, token: str) -> int:
    branch = api("/repos/" + REPOSITORY + "/branches/main", token)
    require(branch["commit"]["sha"] == source, "MAIN_MOVED")
    runs = api(
        "/repos/"
        + REPOSITORY
        + "/actions/workflows/ci.yml/runs?head_sha="
        + source
        + "&event=push&per_page=20",
        token,
    )
    candidates = [
        r
        for r in runs["workflow_runs"]
        if r["head_sha"] == source
        and r["head_branch"] == "main"
        and r["event"] == "push"
        and r["status"] == "completed"
        and r["conclusion"] == "success"
    ]
    require(len(candidates) == 1, "POST_MERGE_CI_UNVERIFIED")
    run = candidates[0]
    jobs = api(
        "/repos/" + REPOSITORY + "/actions/runs/" + str(run["id"]) + "/jobs?per_page=100", token
    )
    require(jobs["total_count"] == 5 and len(jobs["jobs"]) == 5)
    require({j["name"] for j in jobs["jobs"]} == CHECKS)
    require(all(j["conclusion"] == "success" for j in jobs["jobs"]))
    return int(run["id"])


def package_check(settings: dict[str, Any], token: str) -> dict[str, Any]:
    p = api("/users/Gopi-git-bit/packages/container/zippy-api", token)
    require(p["id"] == settings["package_id"] and p["name"] == "zippy-api")
    require(
        p["package_type"] == "container" and p["visibility"] == "private", "PACKAGE_NOT_PRIVATE"
    )
    require(p["owner"]["id"] == 200721521 and p["owner"]["login"] == "Gopi-git-bit")
    require(
        p["repository"]["id"] == 1349197102 and p["repository"]["full_name"] == REPOSITORY,
        "PACKAGE_LINK_UNVERIFIED",
    )
    # API does not enumerate the effective package ACL: independent, expiring review is required.
    return {
        "id": p["id"],
        "visibility": p["visibility"],
        "repository_id": p["repository"]["id"],
        "access_review_sha256": settings["access_review_sha256"],
    }


def install_tools(settings: dict[str, Any], output: Path, names: tuple[str, ...]) -> None:
    output.mkdir(mode=0o700)
    for name in names:
        entry = settings["tools"][name]
        require(re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]))
        prefixes = {
            "age": "https://github.com/FiloSottile/age/releases/download/",
            "crane": "https://github.com/google/go-containerregistry/releases/download/",
            "trivy": "https://github.com/aquasecurity/trivy/releases/download/",
        }
        require(
            entry["url"].startswith(prefixes[name])
            and entry["url"].startswith(prefixes[name] + entry["version"] + "/")
            and entry["member"] == ("age/age" if name == "age" else name)
        )
        archive = output / (name + ".tar.gz")
        with (
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                entry["url"], timeout=30
            ) as response,
            archive.open("xb") as stream,
        ):
            require(response.url.startswith("https://"))
            copied = 0
            while chunk := response.read(1024**2):
                copied += len(chunk)
                require(copied <= 100 * 1024**2, "TOOL_TOO_LARGE")
                stream.write(chunk)
        require(digest(archive) == "sha256:" + entry["sha256"], "TOOL_HASH_MISMATCH")
        with tarfile.open(archive, "r:gz") as bundle:
            members = [m for m in bundle if m.name == entry["member"]]
            require(len(members) == 1 and members[0].isfile() and members[0].size <= 200 * 1024**2)
            executable = bundle.extractfile(members[0])
            require(executable is not None)
            assert executable is not None
            with (output / name).open("xb") as target:
                shutil.copyfileobj(executable, target)
        (output / name).chmod(0o700)
        archive.unlink()


def members(bundle: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    result: dict[str, tarfile.TarInfo] = {}
    total = 0
    for member in bundle:
        path = PurePosixPath(member.name)
        require(
            not path.is_absolute()
            and ".." not in path.parts
            and str(path) == member.name.rstrip("/")
            and (not member.name.endswith("/") or member.isdir())
        )
        require(member.name not in result and (member.isfile() or member.isdir()))
        require(not member.pax_headers, "PAX_METADATA_REFUSED")
        total += member.size
        require(total <= LIMIT and len(result) < 10000, "ARCHIVE_TOO_LARGE")
        result[member.name] = member
    return result


def image_archive(path: Path, image_id: str) -> dict[str, Any]:
    require(path.stat().st_size <= LIMIT)
    with tarfile.open(path, "r:") as bundle:
        entries = members(bundle)
        manifest = bundle.extractfile(entries["manifest.json"])
        require(manifest is not None and entries["manifest.json"].size <= JSON_LIMIT)
        assert manifest is not None
        images = json.load(manifest)
        require(isinstance(images, list) and len(images) == 1)
        entry = images[0]
        config = bundle.extractfile(entries[entry["Config"]])
        require(config is not None and entries[entry["Config"]].size <= JSON_LIMIT)
        assert config is not None
        raw = config.read()
        require("sha256:" + hashlib.sha256(raw).hexdigest() == image_id)
        content = json.loads(raw)
        require(content["os"] == "linux" and content["architecture"] == "amd64")
        require(content["config"]["User"] == "10001:10001")
        diffs = content["rootfs"]["diff_ids"]
        require(
            content["rootfs"]["type"] == "layers" and 0 < len(diffs) == len(entry["Layers"]) <= 100
        )
        require(len(set(entry["Layers"])) == len(diffs))
        for layer, expected in zip(entry["Layers"], diffs, strict=True):
            require(re.fullmatch(DIGEST, expected) and entries[layer].isfile())
            stream = bundle.extractfile(entries[layer])
            assert stream is not None
            checksum = hashlib.sha256()
            while chunk := stream.read(1024**2):
                checksum.update(chunk)
            require("sha256:" + checksum.hexdigest() == expected)
    return {
        "config_digest": image_id,
        "diff_ids": diffs,
        "platform": "linux/amd64",
        "configured_user": "10001:10001",
    }


def unpack(bundle_path: Path, destination: Path, expected: set[str]) -> None:
    require(bundle_path.stat().st_size <= LIMIT)
    with tarfile.open(bundle_path, "r:") as bundle:
        entries = members(bundle)
        require(set(entries) == expected and all(m.isfile() for m in entries.values()))
        for name, member in entries.items():
            require("/" not in name)
            require(member.size <= (LIMIT if name == "image.tar" else JSON_LIMIT))
            stream = bundle.extractfile(member)
            assert stream is not None
            with (destination / name).open("xb") as output:
                shutil.copyfileobj(stream, output)
