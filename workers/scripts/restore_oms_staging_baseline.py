"""New review-only namespace bootstrap. Default is passive; never starts services."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

NAMESPACE = "zippy-oms-staging"
NS_PATH = Path("/run/netns") / NAMESPACE
SOURCE = "10f12c5cc693217dc1ec5be0b9f2d424fbae2369"
POLICY_SHA = "4d75914aeefda08f9fc8700290afdbc212eb2cd7990dda138c25b5f3d7d2dfb4"
POLICY = Path(__file__).resolve().parents[2] / "infra/m7-staging/egress.nft.in"
IP = "/usr/sbin/ip"
NFT = "/usr/sbin/nft"
PRESERVED = (
    "/etc/systemd/system/zippy-oms-staging-probe.service",
    "/opt/zippy-m7-staging/workers/scripts/probe_oms_staging_target.py",
    "/etc/netns/zippy-oms-staging/resolv.conf",
    "/etc/zippy/m7-staging/owner-probe-enabled",
    "/var/lib/zippy-m7-denial-fixtures/readable.fixture",
)


class Refused(ValueError):
    pass


def require(condition: object, reason: str) -> None:
    if not condition:
        raise Refused(reason)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity(path: Path) -> list[int]:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0, "NAMESPACE_PATH_UNSAFE")
    return [info.st_dev, info.st_ino]


class Commands:
    """Fixed local commands, clean environment and one shared 90-second bound."""

    def __init__(self) -> None:
        self.deadline = time.monotonic() + 90

    def run(self, args: list[str], data: str | None = None) -> str:
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "DEADLINE_EXHAUSTED")
        result = subprocess.run(
            args,
            input=data,
            text=True,
            capture_output=True,
            timeout=min(5, remaining),
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        require(result.returncode == 0, "LOCAL_COMMAND_FAILED")
        require(len(result.stdout.encode()) <= 2_097_152, "OBSERVATION_TOO_LARGE")
        return result.stdout

    def read_json(self, args: list[str]) -> Any:
        return json.loads(self.run(args))


def host_gate(commands: Commands) -> None:
    require(platform.system() == "Linux" and os.geteuid() == 0, "HOST_ROOT_REQUIRED")
    require(platform.node() == "srv1943844", "HOST_NAME_MISMATCH")
    require(Path("/proc/1/comm").read_text().strip() == "systemd", "HOST_INIT_UNVERIFIED")
    for kind in ("net", "mnt"):
        require(
            os.stat(f"/proc/self/ns/{kind}").st_ino == os.stat(f"/proc/1/ns/{kind}").st_ino,
            "HOST_NAMESPACE_MISMATCH",
        )
    addresses = commands.read_json([IP, "-json", "address", "show"])
    require(
        any(a.get("local") == "200.234.43.145" for x in addresses for a in x["addr_info"]),
        "HOST_IP_UNVERIFIED",
    )


def policy_shape(document: dict[str, Any]) -> str:
    objects: dict[str, list[dict[str, Any]]] = {k: [] for k in ("table", "chain", "set", "rule")}
    for item in document["nftables"]:
        if set(item) == {"metainfo"}:
            require(item["metainfo"]["json_schema_version"] == 1, "NFT_SCHEMA_UNSUPPORTED")
            continue
        require(len(item) == 1, "NFT_OBJECT_INVALID")
        kind, value = next(iter(item.items()))
        require(kind in objects and isinstance(value, dict), "NFT_OBJECT_UNEXPECTED")
        cleaned = {k: v for k, v in value.items() if k != "handle"}
        if kind == "set" and cleaned.get("elem") == []:
            cleaned.pop("elem")
        objects[kind].append(cleaned)
    for kind in ("table", "chain", "set"):
        objects[kind].sort(key=lambda x: x["name"])
    objects["rule"].sort(key=lambda x: x["chain"])
    return canonical(objects)


def expected_policy() -> dict[str, Any]:
    table = {"family": "inet", "table": "zippy_oms_staging"}
    items: list[dict[str, Any]] = [{"table": {"family": "inet", "name": table["table"]}}]
    for name in ("input", "output", "forward"):
        items.append(
            {
                "chain": {
                    **table,
                    "name": name,
                    "type": "filter",
                    "hook": name,
                    "prio": 0,
                    "policy": "drop",
                }
            }
        )
    for name in ("provider_v4", "provider_v6", "dns_v4", "dns_v6"):
        items.append(
            {
                "set": {
                    **table,
                    "name": name,
                    "type": "ipv4_addr" if name.endswith("v4") else "ipv6_addr",
                }
            }
        )
    items.append(
        {
            "rule": {
                **table,
                "chain": "input",
                "expr": [
                    {
                        "match": {
                            "op": "==",
                            "left": {"ct": {"key": "state"}},
                            "right": {"set": ["established", "related"]},
                        }
                    },
                    {"accept": None},
                ],
            }
        }
    )
    for name, protocol, port in (
        ("provider_v4", "tcp", 443),
        ("provider_v6", "tcp", 443),
        ("dns_v4", "udp", 53),
        ("dns_v4", "tcp", 53),
        ("dns_v6", "udp", 53),
        ("dns_v6", "tcp", 53),
    ):
        family = "ip" if name.endswith("v4") else "ip6"
        expr = [
            {
                "match": {
                    "op": "==",
                    "left": {"payload": {"protocol": p, "field": f}},
                    "right": right,
                }
            }
            for p, f, right in ((family, "daddr", "@" + name), (protocol, "dport", port))
        ]
        items.append({"rule": {**table, "chain": "output", "expr": [*expr, {"accept": None}]}})
    return {"nftables": items}


def topology(commands: Commands) -> dict[str, Any]:
    prefix = [IP, "-netns", NAMESPACE, "-json"]
    return {
        "links": commands.read_json([*prefix, "link", "show"]),
        "addresses": commands.read_json([*prefix, "address", "show"]),
        "routes4": commands.read_json([*prefix, "-4", "route", "show", "table", "all"]),
        "routes6": commands.read_json([*prefix, "-6", "route", "show", "table", "all"]),
        "neighbors": commands.read_json([*prefix, "neigh", "show"]),
    }


def empty_topology(value: dict[str, Any]) -> None:
    require(
        not value["routes4"] and not value["routes6"] and not value["neighbors"],
        "TOPOLOGY_NOT_EMPTY",
    )
    require(len(value["links"]) == len(value["addresses"]) == 1, "UNEXPECTED_LINKS")
    for link in (*value["links"], *value["addresses"]):
        require(
            link["ifname"] == "lo"
            and link["operstate"] == "DOWN"
            and set(link["flags"]) == {"LOOPBACK"},
            "LOOPBACK_NOT_DOWN",
        )
        require(not link.get("addr_info"), "UNEXPECTED_ADDRESSES")


def preserved_files() -> str:
    records: list[list[object]] = []
    for name in PRESERVED:
        path = Path(name)
        if not path.exists() and not path.is_symlink():
            records.append([name, "absent"])
            continue
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "PRESERVED_PATH_UNSAFE")
        require(info.st_size <= 262_144, "PRESERVED_FILE_TOO_LARGE")
        records.append([name, info.st_uid, info.st_gid, info.st_mode, digest(path.read_bytes())])
    return digest(canonical(records).encode())


def host_state(commands: Commands, folder: Path) -> dict[str, str]:
    config = folder / "docker-config"
    require(
        config.is_dir() and not config.is_symlink() and not list(config.iterdir()),
        "DOCKER_CONFIG_NOT_EMPTY",
    )
    docker = ["/usr/bin/docker", "--config", str(config), "--host", "unix:///var/run/docker.sock"]
    ids = commands.run([*docker, "network", "ls", "--quiet", "--no-trunc"]).splitlines()
    require(
        all(len(x) == 64 and all(c in "0123456789abcdef" for c in x) for x in ids),
        "DOCKER_NETWORK_IDS_INVALID",
    )
    network_data = commands.read_json([*docker, "network", "inspect", *sorted(ids)]) if ids else []
    outputs = {
        "nft": commands.run([NFT, "--json", "--stateless", "--handle", "list", "ruleset"]),
        "iptables": commands.run(["/usr/sbin/iptables-save"]),
        "ip6tables": commands.run(["/usr/sbin/ip6tables-save"]),
        "links": canonical(commands.read_json([IP, "-json", "-details", "link", "show"])),
        "docker_networks": canonical(network_data),
    }
    # iptables-save adds wall-clock comments even when its rules are unchanged.
    for name in ("iptables", "ip6tables"):
        outputs[name] = "\n".join(x for x in outputs[name].splitlines() if not x.startswith("#"))
    return {**{k: digest(v.encode()) for k, v in outputs.items()}, "files": preserved_files()}


def boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def private_folder(folder: Path) -> None:
    for path in (folder, *folder.parents):
        info = path.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid == 0
            and (not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX),
            "EVIDENCE_PARENT_UNSAFE",
        )
    require(stat.S_IMODE(folder.stat().st_mode) == 0o700, "EVIDENCE_MODE_UNSAFE")


def record(folder: Path, value: dict[str, Any]) -> None:
    private_folder(folder)
    temporary = folder / "receipt.next"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(canonical(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, folder / "receipt.json")


def read_receipt(folder: Path) -> dict[str, Any]:
    private_folder(folder)
    fd = os.open(folder / "receipt.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_uid == 0
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size <= 65_536,
            "RECEIPT_UNSAFE",
        )
        result: dict[str, Any] = json.loads(handle.read(65_537))
    require(
        result["namespace"] == NAMESPACE and result["boot_id"] == boot_id(),
        "RECEIPT_IDENTITY_MISMATCH",
    )
    require(
        result["script_sha256"] == digest(Path(__file__).read_bytes())
        and result["policy_sha256"] == POLICY_SHA,
        "RECEIPT_SOURCE_MISMATCH",
    )
    require(result["state"] in ("BASELINE_VERIFIED", "NOT_VERIFIED"), "RECEIPT_STATE_REFUSED")
    return result


def owned(value: dict[str, Any]) -> None:
    require(
        value.get("created") is True and identity(NS_PATH) == value["namespace_identity"],
        "NAMESPACE_OWNERSHIP_MISMATCH",
    )
    require(identity(NS_PATH)[1] != os.stat("/proc/self/ns/net").st_ino, "HOST_NAMESPACE_REFUSED")


def verify(commands: Commands, folder: Path, value: dict[str, Any]) -> None:
    owned(value)
    empty_topology(topology(commands))
    actual = commands.read_json(
        [IP, "netns", "exec", NAMESPACE, NFT, "--json", "--handle", "list", "ruleset"]
    )
    require(policy_shape(actual) == policy_shape(expected_policy()), "BASELINE_POLICY_MISMATCH")
    require(not commands.run([IP, "netns", "pids", NAMESPACE]).strip(), "NAMESPACE_HAS_USERS")
    require(host_state(commands, folder) == value["host_before"], "HOST_PRESERVATION_UNVERIFIED")
    owned(value)


def apply(commands: Commands, parent: Path) -> Path:
    require(not os.path.lexists(NS_PATH), "EXISTING_NAMESPACE_REFUSED")
    policy = POLICY.read_bytes()
    require(digest(policy) == POLICY_SHA, "POLICY_SOURCE_MISMATCH")
    folder = Path(tempfile.mkdtemp(prefix="zippy-m7-restore-", dir=parent))
    private_folder(folder)
    (folder / "docker-config").mkdir(mode=0o700)
    value: dict[str, Any] = {
        "version": 1,
        "namespace": NAMESPACE,
        "boot_id": boot_id(),
        "script_sha256": digest(Path(__file__).read_bytes()),
        "policy_source_sha": SOURCE,
        "policy_sha256": POLICY_SHA,
        "created": False,
        "state": "IN_PROGRESS",
        "provider_requests": 0,
        "reboot_persistent": False,
    }
    record(folder, value)
    try:
        value["host_before"] = host_state(commands, folder)
        require(not os.path.lexists(NS_PATH), "EXISTING_NAMESPACE_REFUSED")
        commands.run([IP, "netns", "add", NAMESPACE])
        value["namespace_identity"] = identity(NS_PATH)
        value["created"] = True
        record(folder, value)
        owned(value)
        empty_topology(topology(commands))
        require(not commands.run([IP, "netns", "pids", NAMESPACE]).strip(), "NAMESPACE_HAS_USERS")
        owned(value)
        initial = commands.read_json(
            [IP, "netns", "exec", NAMESPACE, NFT, "--json", "list", "ruleset"]
        )
        require(
            all(set(item) == {"metainfo"} for item in initial["nftables"]),
            "NEW_NAMESPACE_RULESET_NOT_EMPTY",
        )
        commands.run(
            [IP, "netns", "exec", NAMESPACE, NFT, "--check", "--file", "-"], policy.decode()
        )
        owned(value)
        commands.run([IP, "netns", "exec", NAMESPACE, NFT, "--file", "-"], policy.decode())
        verify(commands, folder, value)
        value["state"] = "BASELINE_VERIFIED"
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        value["state"] = "NOT_VERIFIED"
        record(folder, value)
        print(
            canonical(
                {
                    "status": "NOT_VERIFIED",
                    "evidence_dir": str(folder),
                    "created": value["created"],
                    "automatic_cleanup": False,
                    "reason": str(exc) if isinstance(exc, Refused) else type(exc).__name__,
                }
            )
        )
        raise
    record(folder, value)
    return folder


def rollback(commands: Commands, folder: Path, value: dict[str, Any]) -> None:
    owned(value)
    empty_topology(topology(commands))
    require(not commands.run([IP, "netns", "pids", NAMESPACE]).strip(), "NAMESPACE_HAS_USERS")
    owned(value)
    commands.run([IP, "netns", "delete", NAMESPACE])
    require(not os.path.lexists(NS_PATH), "NAMESPACE_REMOVAL_UNVERIFIED")
    value["state"] = "REMOVED"
    record(folder, value)
    require(host_state(commands, folder) == value["host_before"], "HOST_PRESERVATION_UNVERIFIED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", nargs="?", choices=("plan", "apply", "verify", "rollback"), default="plan"
    )
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args(argv)
    if args.action == "plan":
        print(
            canonical(
                {
                    "status": "PLAN_ONLY",
                    "namespace": NAMESPACE,
                    "policy_source_sha": SOURCE,
                    "policy_sha256": POLICY_SHA,
                    "execution_authorized": False,
                }
            )
        )
        return 0
    try:
        commands = Commands()
        host_gate(commands)
        if args.action == "apply":
            require(args.evidence_dir is None, "APPLY_REQUIRES_NEW_EVIDENCE")
            folder = apply(commands, Path("/opt"))
        else:
            folder = args.evidence_dir
            require(
                folder is not None
                and folder.is_absolute()
                and folder.parent == Path("/opt")
                and folder.name.startswith("zippy-m7-restore-"),
                "EVIDENCE_PATH_REFUSED",
            )
            value = read_receipt(folder)
            if args.action == "verify":
                verify(commands, folder, value)
            else:
                rollback(commands, folder, value)
        print(
            canonical(
                {
                    "status": "LOCAL_BASELINE_CHECKS_PASSED",
                    "action": args.action,
                    "evidence_dir": str(folder),
                    "live_readiness": "DENIED",
                    "provider_requests": 0,
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(
            canonical(
                {
                    "status": "NOT_VERIFIED",
                    "action": args.action,
                    "provider_requests": 0,
                    "reason": str(exc) if isinstance(exc, Refused) else type(exc).__name__,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
