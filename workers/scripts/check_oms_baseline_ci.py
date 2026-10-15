"""Real kernel regression on disposable GitHub-hosted CI only, never a VPS tool."""

from __future__ import annotations

import copy
import importlib.util
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

spec = importlib.util.spec_from_file_location(
    "restore_oms_staging_baseline", Path(__file__).with_name("restore_oms_staging_baseline.py")
)
if spec is None or spec.loader is None:
    raise RuntimeError("CI_SOURCE_UNAVAILABLE")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def rejected(call: Any, reason: str) -> None:
    try:
        call()
    except baseline.Refused as exc:
        baseline.require(str(exc) == reason, "WRONG_REJECTION")
    else:
        raise baseline.Refused("EXPECTED_REJECTION_MISSING")


def exercise(parent: Path) -> None:
    class ObservedCommands:
        def __init__(self) -> None:
            self.commands = baseline.Commands()
            self.exported = False

        def run(self, args: list[str], data: str | None = None) -> str:
            return str(self.commands.run(args, data))

        def read_json(self, args: list[str]) -> Any:
            value = self.commands.read_json(args)
            if args[:4] == [baseline.IP, "netns", "exec", baseline.NAMESPACE] and not self.exported:
                if any("rule" in item for item in value.get("nftables", [])):
                    print("M7_BASELINE_EXPORT=" + baseline.canonical(value))
                    self.exported = True
            return value

    commands = ObservedCommands()
    folder: Path | None = None
    value: dict[str, Any] | None = None
    try:
        folder = baseline.apply(commands, parent)
        value = baseline.read_receipt(folder)
        baseline.verify(commands, folder, value)
        rejected(lambda: baseline.apply(commands, parent), "EXISTING_NAMESPACE_REFUSED")
        bad = copy.deepcopy(value)
        bad["namespace_identity"][1] += 1
        rejected(lambda: baseline.rollback(commands, folder, bad), "NAMESPACE_OWNERSHIP_MISMATCH")

        # Mutate only the CI-owned, unconnected namespace; no traffic is sent.
        prefix = [baseline.IP, "netns", "exec", baseline.NAMESPACE, baseline.NFT]
        commands.run(
            [
                *prefix,
                "add",
                "element",
                "inet",
                "zippy_oms_staging",
                "provider_v4",
                "{",
                "192.0.2.99",
                "}",
            ]
        )
        rejected(lambda: baseline.verify(commands, folder, value), "BASELINE_POLICY_MISMATCH")
        commands.run(
            [
                *prefix,
                "delete",
                "element",
                "inet",
                "zippy_oms_staging",
                "provider_v4",
                "{",
                "192.0.2.99",
                "}",
            ]
        )
        baseline.verify(commands, folder, value)

        sleeper = subprocess.Popen(
            [baseline.IP, "netns", "exec", baseline.NAMESPACE, "/usr/bin/sleep", "10"],
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        try:
            deadline = time.monotonic() + 2
            while not commands.run([baseline.IP, "netns", "pids", baseline.NAMESPACE]).strip():
                baseline.require(time.monotonic() < deadline, "CI_FIXTURE_NOT_READY")
                time.sleep(0.02)
            rejected(lambda: baseline.rollback(commands, folder, value), "NAMESPACE_HAS_USERS")
        finally:
            sleeper.terminate()
            sleeper.wait(timeout=2)
        baseline.rollback(commands, folder, value)
        baseline.require(not os.path.lexists(baseline.NS_PATH), "CI_CLEANUP_FAILED")
        value = None
        print("BASELINE_KERNEL_ROUND_TRIP_AND_GUARDS_PASSED")
    finally:
        # Never delete a pre-existing/replaced namespace or kill unknown users.
        # On unexpected topology/users/ownership, leave it for runner disposal.
        if value is not None and folder is not None and os.path.lexists(baseline.NS_PATH):
            baseline.rollback(baseline.Commands(), folder, value)


def main() -> None:
    baseline.require(
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.geteuid() == 0
        and platform.node() != "srv1943844",
        "DISPOSABLE_CI_ONLY",
    )
    commands = baseline.Commands()
    addresses = commands.read_json([baseline.IP, "-json", "address", "show"])
    baseline.require(
        not any(a.get("local") == "200.234.43.145" for x in addresses for a in x["addr_info"]),
        "VPS_REFUSED",
    )
    baseline.require(not os.path.lexists(baseline.NS_PATH), "PREEXISTING_CI_NAMESPACE")
    # Test the operational core after the separate CI host gate. Production CLI
    # has no test flag or host bypass and still requires the exact VPS context.
    with tempfile.TemporaryDirectory(prefix="m7-baseline-ci-", dir="/root") as directory:
        parent = Path(directory)
        exercise(parent)

        class FailingApply:
            def __init__(self) -> None:
                self.commands = baseline.Commands()

            def run(self, args: list[str], data: str | None = None) -> str:
                if "--file" in args and "--check" not in args:
                    raise baseline.Refused("CI_INJECTED_APPLY_FAILURE")
                return str(self.commands.run(args, data))

            def read_json(self, args: list[str]) -> Any:
                return self.commands.read_json(args)

        previous = set(parent.iterdir())
        rejected(lambda: baseline.apply(FailingApply(), parent), "CI_INJECTED_APPLY_FAILURE")
        created = set(parent.iterdir()) - previous
        baseline.require(len(created) == 1, "CI_PARTIAL_RECEIPT_MISSING")
        folder = created.pop()
        value = baseline.read_receipt(folder)
        baseline.require(
            value["state"] == "NOT_VERIFIED" and value["created"] is True,
            "CI_PARTIAL_OWNERSHIP_MISSING",
        )
        baseline.rollback(baseline.Commands(), folder, value)
        baseline.require(not os.path.lexists(baseline.NS_PATH), "CI_PARTIAL_CLEANUP_FAILED")
        print("BASELINE_PARTIAL_FAILURE_SCOPED_ROLLBACK_PASSED")


if __name__ == "__main__":
    main()
