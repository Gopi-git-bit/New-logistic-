"""Fixed synthetic tuples and exact, namespace-local nftables policy contracts."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

TARGET_TABLE = "zippy_oms_staging"
PEER_TABLE = "zippy_m7_synthetic_peer"
CHALLENGE = re.compile(rb"M7-CONTROL [0-9a-f]{24}\Z")
PEER_SECONDS = 40.0
MAX_EXCHANGES = 28


def cases() -> list[dict[str, Any]]:
    result = []
    for family, source, allowed, denied in (
        ("ipv4", "192.0.2.1", "192.0.2.2", "192.0.2.3"),
        ("ipv6", "2001:db8:7::1", "2001:db8:7::2", "2001:db8:7::3"),
    ):
        for address, permitted in ((allowed, True), (denied, False)):
            for transport, port in (("tcp", 443), ("tcp", 53), ("udp", 53)):
                result.append(
                    {
                        "family": family,
                        "source": source,
                        "address": address,
                        "transport": transport,
                        "port": port,
                        "permitted": permitted,
                    }
                )
        result.append(
            {
                "family": family,
                "source": source,
                "address": allowed,
                "transport": "tcp",
                "port": 5432,
                "permitted": False,
            }
        )
    return result


def payload(protocol: str, field: str, value: Any) -> dict[str, Any]:
    return {
        "match": {
            "op": "==",
            "left": {"payload": {"protocol": protocol, "field": field}},
            "right": value,
        }
    }


def selector(case: dict[str, Any]) -> list[dict[str, Any]]:
    protocol = "ip" if case["family"] == "ipv4" else "ip6"
    return [
        {"match": {"op": "==", "left": {"meta": {"key": "nfproto"}}, "right": case["family"]}},
        payload(protocol, "saddr", case["source"]),
        payload(protocol, "daddr", case["address"]),
        {"match": {"op": "==", "left": {"meta": {"key": "l4proto"}}, "right": case["transport"]}},
        payload(case["transport"], "dport", case["port"]),
    ]


def policy(phase: str) -> dict[str, Any]:
    if phase not in {"calibration", "restricted", "peer"}:
        raise ValueError("UNSUPPORTED_SYNTHETIC_POLICY")
    table = PEER_TABLE if phase == "peer" else TARGET_TABLE
    items: list[dict[str, Any]] = [{"table": {"family": "inet", "name": table}}]
    for chain in ("input", "output", "forward"):
        items.append(
            {
                "chain": {
                    "family": "inet",
                    "table": table,
                    "name": chain,
                    "type": "filter",
                    "hook": chain,
                    "prio": 0,
                    "policy": "drop",
                }
            }
        )
    # The peer replies only to established flows. The target accepts only replies.
    reply_chain = "output" if phase == "peer" else "input"
    items.append(
        {
            "rule": {
                "family": "inet",
                "table": table,
                "chain": reply_chain,
                "expr": [
                    {
                        "match": {
                            "op": "in",
                            "left": {"ct": {"key": "state"}},
                            "right": {"set": ["established", "related"]},
                        }
                    },
                    {"accept": None},
                ],
                "comment": "M7 synthetic replies only",
            }
        }
    )
    for i, case in enumerate(cases()):
        name = f"m7_{i:02}"
        items.append(
            {"counter": {"family": "inet", "table": table, "name": name, "packets": 0, "bytes": 0}}
        )
        verdict = "accept" if phase != "restricted" or case["permitted"] else "drop"
        items.append(
            {
                "rule": {
                    "family": "inet",
                    "table": table,
                    "chain": "input" if phase == "peer" else "output",
                    "expr": [*selector(case), {"counter": name}, {verdict: None}],
                    "comment": f"M7 {phase} {i:02}",
                }
            }
        )
    return {"nftables": items}


def policy_bytes(phase: str) -> bytes:
    commands = {"nftables": [{"add": item} for item in policy(phase)["nftables"]]}
    return (json.dumps(commands, indent=2) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def policy_shape(document: dict[str, Any]) -> dict[str, Any]:
    """Keep selectors, order and all security fields; drop only runtime metadata."""
    objects: dict[str, list[dict[str, Any]]] = {
        k: [] for k in ("table", "chain", "counter", "rule")
    }
    for item in document["nftables"]:
        if set(item) == {"metainfo"}:
            if item["metainfo"].get("json_schema_version") != 1:
                raise ValueError("NFT_SCHEMA_UNSUPPORTED")
            continue
        if len(item) != 1:
            raise ValueError("NFT_OBJECT_INVALID")
        kind, value = next(iter(item.items()))
        if kind not in objects or not isinstance(value, dict):
            raise ValueError("NFT_OBJECT_UNEXPECTED")
        cleaned = {k: v for k, v in value.items() if k != "handle"}
        if kind == "counter":
            cleaned.pop("packets", None)
            cleaned.pop("bytes", None)
        objects[kind].append(cleaned)
    # nft lists counters/chains by kernel enumeration, not source creation order.
    for kind in ("table", "chain", "counter"):
        objects[kind].sort(key=lambda value: value["name"])
    # Chain order is irrelevant; rule order within each chain is preserved.
    objects["rule"].sort(key=lambda value: value["chain"])
    return dict(objects)


def counter_values(document: dict[str, Any]) -> dict[str, tuple[int, int]]:
    result = {}
    for item in document["nftables"]:
        if "counter" not in item:
            continue
        value = item["counter"]
        name = value["name"]
        packets, size = value["packets"], value["bytes"]
        if name in result or type(packets) is not int or type(size) is not int:
            raise ValueError("COUNTER_INVALID")
        if min(packets, size) < 0:
            raise ValueError("COUNTER_INVALID")
        result[name] = (packets, size)
    return result


def snapshot_identity(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect replacement of a table/rule/counter between phase snapshots."""
    result = []
    for item in document["nftables"]:
        if "metainfo" in item:
            continue
        kind, value = next(iter(item.items()))
        if type(value.get("handle")) is not int or value["handle"] <= 0:
            raise ValueError("NFT_HANDLES_REQUIRED")
        cleaned = dict(value)
        if kind == "counter":
            cleaned.pop("packets")
            cleaned.pop("bytes")
        result.append({kind: cleaned})
    return sorted(result, key=lambda item: json.dumps(item, sort_keys=True))
