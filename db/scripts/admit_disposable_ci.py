"""Verify owner/main/current five-job CI before any disposable resource creation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from db.scripts.disposable_contract import (  # noqa: E402
    BASE_ENV,
    REPOSITORY,
    admission,
    ci_accept,
    require,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise ValueError("GITHUB_REDIRECT_REJECTED")


def get(path: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.github.com/repos/" + REPOSITORY + "/" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
        data = response.read(1_048_577)
    require(len(data) <= 1_048_576, "GITHUB_RESPONSE_REJECTED")
    result: dict[str, Any] = json.loads(data)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--expires", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        identity = admission(os.environ, args.source, args.expires)
        require(
            get("branches/main", os.environ["GH_TOKEN"])["commit"]["sha"] == args.source,
            "MAIN_CHANGED",
        )
        runs = get(
            "actions/workflows/ci.yml/runs?event=push&head_sha=" + args.source + "&per_page=100",
            os.environ["GH_TOKEN"],
        )["workflow_runs"]
        require(runs, "CI_NOT_VERIFIED")
        run = max(runs, key=lambda row: row["id"])
        jobs = get(f"actions/runs/{int(run['id'])}/jobs?per_page=100", os.environ["GH_TOKEN"])
        require(jobs["total_count"] == len(jobs["jobs"]), "CI_NOT_VERIFIED")
        ci_accept(run, jobs["jobs"], args.source)
        require(
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], env=BASE_ENV, text=True, timeout=5
            ).strip()
            == args.source,
            "SOURCE_REJECTED",
        )
        require(
            not subprocess.check_output(
                ["git", "status", "--porcelain"], env=BASE_ENV, text=True, timeout=5
            ),
            "DIRTY_SOURCE_REJECTED",
        )
        os.umask(0o077)
        receipt = {
            "schema": 1,
            "identity": identity,
            "expires": args.expires,
            "ci_run": run["id"],
            "ci_attempt": run["run_attempt"],
            "observed_utc": datetime.now(UTC).isoformat(),
        }
        with args.output.open("x") as output:
            json.dump(receipt, output)
        print("DISPOSABLE_ADMISSION_PASSED")
        return 0
    except Exception:
        # Never print API exceptions, response bodies, token or environment.
        print("DISPOSABLE_ADMISSION_NOT_VERIFIED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
