"""Emit an allowlisted build-time receipt; never import or start the API."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

MARKER = "ZIPPY_API_BUILD_EVIDENCE "


def token(value: object, pattern: str = r"[A-Za-z0-9_.+!~:-]{1,160}") -> str:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("UNSAFE_METADATA")
    return value


def source_url(value: object) -> str:
    """Omit credentials, query and fragment; retain the reported download location."""
    if not isinstance(value, str):
        raise ValueError("UNSAFE_SOURCE")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.port not in (None, 443):
        raise ValueError("UNSAFE_SOURCE")
    host = token(parts.hostname, r"[A-Za-z0-9.-]{1,253}")
    if host != "files.pythonhosted.org":
        raise ValueError("UNREVIEWED_PACKAGE_ORIGIN")
    path = token(parts.path, r"/[A-Za-z0-9_./%+~-]{0,1000}")
    return urlunsplit(("https", host, path, "", ""))


def pip_receipt(report: dict[str, Any]) -> list[dict[str, str]]:
    if report.get("version") != "1" or not isinstance(report.get("install"), list):
        raise ValueError("UNSUPPORTED_PIP_REPORT")
    packages = []
    names = set()
    for item in report["install"]:
        metadata = item["metadata"]
        name = re.sub(r"[-_.]+", "-", token(metadata["name"])).lower()
        if name in names:
            raise ValueError("DUPLICATE_DOWNLOAD")
        names.add(name)
        download = item["download_info"]
        packages.append(
            {
                "name": name,
                "version": token(metadata["version"]),
                "url": source_url(download["url"]),
                "sha256": token(download["archive_info"]["hashes"]["sha256"], r"[a-f0-9]{64}"),
            }
        )
    if not packages:
        raise ValueError("EMPTY_DOWNLOAD_RECEIPT")
    return sorted(packages, key=lambda package: package["name"])


def collect(report: dict[str, Any], installed: str, os_release: dict[str, str]) -> dict[str, Any]:
    packages = []
    for row in installed.splitlines():
        name, version = row.split("\t")
        packages.append({"name": token(name), "version": token(version)})
    if not packages:
        raise ValueError("NO_OS_PACKAGES")
    return {
        "schema": 1,
        "python": platform.python_version(),
        "pip": token(report["pip_version"]),
        "os": {key: token(os_release[key]) for key in ("ID", "VERSION_ID")},
        "installed_os_packages": sorted(packages, key=lambda package: package["name"]),
        "pip_downloads": pip_receipt(report),
        "pip_hash_evidence": "pip --require-hashes plus installation-report v1; not independent capture",
        "apt_archive_receipts": "UNVERIFIED; installed versions only, mutable apt repositories",
    }


def main() -> int:
    try:
        report = json.loads(Path(sys.argv[1]).read_text())
        installed = subprocess.run(
            ["/usr/bin/dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        ).stdout
        result = collect(report, installed, platform.freedesktop_os_release())
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError):
        print("BUILD_METADATA_NOT_VERIFIED")
        return 1
    print(MARKER + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
