"""Export committed API build inputs only; never build or start an image."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

ROOT_INPUTS = frozenset(
    {"Dockerfile.api", "requirements-api.lock", "scripts/emit_api_build_metadata.py"}
)
REQUIRED = ROOT_INPUTS | {"api/__init__.py", "api/config.py", "api/main.py"}
TEST_DIRECTORIES = frozenset({"tests", "tests_m4", "tests_m5"})


class ContextError(ValueError):
    """A build input cannot be established from the requested commit."""


def git(repo: Path, *args: str) -> bytes:
    executable = shutil.which("git", path=os.defpath)
    if executable is None:
        raise ContextError("GIT_UNAVAILABLE")
    # Ignore ambient GIT_DIR, replacement objects, global config and credentials.
    result = subprocess.run(
        [executable, "-C", str(repo), *args],
        env={
            "PATH": os.defpath,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_NO_REPLACE_OBJECTS": "1",
            "LC_ALL": "C",
        },
        capture_output=True,
        timeout=5,
        check=False,
    )
    if result.returncode:
        raise ContextError("GIT_INPUT_UNAVAILABLE")
    return result.stdout


def validate_lock(content: bytes) -> int:
    """Require exact registry pins and SHA-256 constraints, not arbitrary pip flags."""
    names: set[str] = set()
    text = content.decode("utf-8")
    # Pip does not continue full-line comments. Refuse this ambiguous form rather
    # than joining a following option into a comment and silently dropping it.
    if any(
        line.lstrip().startswith("#") and line.rstrip().endswith("\\") for line in text.splitlines()
    ):
        raise ContextError("UNSAFE_OR_UNHASHED_LOCK")
    for line in text.replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            # Names cannot begin with pip-option punctuation or end with separators.
            r"([A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)==([A-Za-z0-9_.+!-]+)"
            r"(?:\s+--hash=sha256:[a-f0-9]{64})+",
            line,
        )
        if match is None:
            raise ContextError("UNSAFE_OR_UNHASHED_LOCK")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in names:
            raise ContextError("DUPLICATE_LOCK_REQUIREMENT")
        names.add(name)
    if not names:
        raise ContextError("EMPTY_LOCK")
    return len(names)


def prepare_context(repo: Path, source_sha: str, output: Path) -> dict[str, object]:
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ContextError("EXACT_SOURCE_SHA_REQUIRED")
    if os.path.lexists(output):
        raise ContextError("OUTPUT_ALREADY_EXISTS")
    repo = repo.resolve(strict=True)
    if output.resolve().is_relative_to(repo):
        raise ContextError("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
    if Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo:
        raise ContextError("REPOSITORY_ROOT_REQUIRED")
    if git(repo, "rev-parse", "HEAD").decode().strip() != source_sha:
        raise ContextError("SOURCE_HEAD_MISMATCH")

    inputs: dict[str, tuple[str, bytes]] = {}
    for entry in git(repo, "ls-tree", "-r", "-z", source_sha).split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        parts = PurePosixPath(path).parts
        if path not in ROOT_INPUTS:
            if not parts or parts[0] != "api":
                continue
            if len(parts) > 1 and parts[1] in TEST_DIRECTORIES:
                continue
            if (
                not path.endswith(".py")
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)
                or any(part.startswith(".") for part in parts)
            ):
                raise ContextError("UNSUPPORTED_API_RUNTIME_INPUT")
        mode, kind, oid = metadata.decode("ascii").split()
        if mode != "100644" or kind != "blob":
            raise ContextError("NON_REGULAR_BUILD_INPUT")
        if int(git(repo, "cat-file", "-s", oid)) > 4 * 1024 * 1024:
            raise ContextError("BUILD_INPUT_TOO_LARGE")
        content = git(repo, "cat-file", "blob", oid)
        observed = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if observed != oid:
            raise ContextError("GIT_BLOB_MISMATCH")
        inputs[path] = (oid, content)
    if not REQUIRED.issubset(inputs):
        raise ContextError("REQUIRED_BUILD_INPUT_MISSING")
    locked = validate_lock(inputs["requirements-api.lock"][1])
    files = [
        {"path": path, "git_blob_sha1": oid, "sha256": hashlib.sha256(content).hexdigest()}
        for path, (oid, content) in sorted(inputs.items())
    ]
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    # Validate everything before creating the new destination. No overwrite or deletion.
    output.mkdir(mode=0o700)
    for path, (_, content) in sorted(inputs.items()):
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        target.chmod(0o644)
    return {
        "status": "CONTEXT_PREPARED",
        "source_sha": source_sha,
        "source_tree": git(repo, "rev-parse", source_sha + "^{tree}").decode().strip(),
        "context_manifest_sha256": digest,
        "locked_distributions": locked,
        "files": files,
        "image_build": "NOT_RUN",
        "runtime_readiness": "UNVERIFIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare_context(args.repo_root, args.source_sha, args.output)
    except (ContextError, OSError, ValueError, subprocess.SubprocessError):
        print(json.dumps({"status": "CONTEXT_NOT_VERIFIED"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
