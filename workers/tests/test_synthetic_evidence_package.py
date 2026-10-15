"""Disposable synthetic artifacts/fake sockets; no namespace or policy activation."""

import copy
import importlib.util
import json
import os
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"workers/scripts/{name}.py")
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


collector = module("collect_oms_synthetic_evidence")
peer = module("serve_oms_synthetic_peer")
contract = module("oms_synthetic_contract")
NOW = datetime(2026, 10, 13, 13, tzinfo=UTC)


def captured_export(phase):
    return json.loads((ROOT / f"workers/tests/fixtures/nft-1.0.9-{phase}.json").read_text())


@pytest.mark.parametrize("phase", ["calibration", "restricted", "peer"])
def test_real_nft_109_exports_match_without_mutating_evidence(phase):
    actual = captured_export(phase)
    original = copy.deepcopy(actual)
    expected = contract.policy(phase)
    original_expected = copy.deepcopy(expected)
    assert contract.policy_shape(actual) == contract.policy_shape(expected)
    assert actual == original
    assert expected == original_expected
    assert len(contract.counter_values(actual)) == 14
    assert all(value == (0, 0) for value in contract.counter_values(actual).values())


@pytest.mark.parametrize("phase", ["calibration", "restricted", "peer"])
@pytest.mark.parametrize("representation", ["source", "export"])
@pytest.mark.parametrize(
    "mutation",
    [
        "source_address",
        "destination_address",
        "family",
        "transport",
        "port",
        "missing_source",
        "missing_destination",
        "missing_port",
        "selector_order",
        "counter_name",
        "missing_counter",
        "verdict",
        "extra_accept",
        "rule_order",
        "extra_rule",
        "chain_policy",
        "chain_hook",
        "chain_priority",
        "table",
        "comment",
        "unknown_expression",
        "reply_state",
        "reply_operator",
        "reply_verdict",
        "conflicting_family_guard",
        "conflicting_transport_guard",
    ],
)
def test_normalization_preserves_security_differences(phase, representation, mutation):
    document = contract.policy(phase) if representation == "source" else captured_export(phase)
    items = document["nftables"]
    rules = [item["rule"] for item in items if "rule" in item]
    rule = next(rule for rule in rules if rule["comment"] == f"M7 {phase} 00")
    expr = rule["expr"]
    payloads = [item for item in expr if "payload" in item.get("match", {}).get("left", {})]
    source, destination, port = payloads
    reply = next(rule for rule in rules if rule["comment"] == "M7 synthetic replies only")
    if mutation == "source_address":
        source["match"]["right"] = "192.0.2.9"
    elif mutation == "destination_address":
        destination["match"]["right"] = "192.0.2.9"
    elif mutation == "family":
        source["match"]["left"]["payload"]["protocol"] = "ip6"
    elif mutation == "transport":
        port["match"]["left"]["payload"]["protocol"] = "udp"
    elif mutation == "port":
        port["match"]["right"] = 444
    elif mutation.startswith("missing_"):
        removed = {
            "missing_source": source,
            "missing_destination": destination,
            "missing_port": port,
            "missing_counter": expr[-2],
        }[mutation]
        expr.remove(removed)
    elif mutation == "selector_order":
        a, b = expr.index(source), expr.index(destination)
        expr[a], expr[b] = expr[b], expr[a]
    elif mutation == "counter_name":
        expr[-2]["counter"] = "m7_01"
    elif mutation == "verdict":
        expr[-1] = {"drop": None}
    elif mutation == "extra_accept":
        expr.insert(0, {"accept": None})
    elif mutation == "rule_order":
        entries = [
            i
            for i, item in enumerate(items)
            if "rule" in item and item["rule"]["chain"] == rule["chain"]
        ]
        a, b = entries[:2]
        items[a], items[b] = items[b], items[a]
    elif mutation == "extra_rule":
        items.append({"rule": copy.deepcopy(rule)})
    elif mutation.startswith("chain_"):
        chain = next(item["chain"] for item in items if "chain" in item)
        key, value = {
            "chain_policy": ("policy", "accept"),
            "chain_hook": ("hook", "prerouting"),
            "chain_priority": ("prio", 1),
        }[mutation]
        chain[key] = value
    elif mutation == "table":
        rule["table"] = "bypass"
    elif mutation == "comment":
        rule["comment"] = "unknown"
    elif mutation == "unknown_expression":
        expr.insert(-1, {"log": {"prefix": "unknown"}})
    elif mutation == "reply_state":
        reply["expr"][0]["match"]["right"]["set"].append("new")
    elif mutation == "reply_operator":
        reply["expr"][0]["match"]["op"] = "!="
    elif mutation == "reply_verdict":
        reply["expr"][-1] = {"drop": None}
    elif mutation == "conflicting_family_guard":
        if representation == "source":
            expr[0]["match"]["right"] = "ipv6"
        else:
            expr.insert(
                0, {"match": {"op": "==", "left": {"meta": {"key": "nfproto"}}, "right": "ipv6"}}
            )
    elif mutation == "conflicting_transport_guard":
        if representation == "source":
            expr[3]["match"]["right"] = "udp"
        else:
            expr.insert(
                2, {"match": {"op": "==", "left": {"meta": {"key": "l4proto"}}, "right": "udp"}}
            )
    else:
        pytest.fail("unhandled mutation")
    assert contract.policy_shape(document) != contract.policy_shape(contract.policy(phase))


def test_collector_accepts_captured_export_shapes_but_keeps_readiness_denied(evidence):
    for phase in ("calibration", "restricted"):
        for side in ("before", "after"):
            for prefix, exported_phase in (("", phase), ("peer-", "peer")):
                envelope = evidence[f"{prefix}{phase}-{side}.json"]
                old = contract.counter_values(envelope["ruleset"])
                actual = captured_export(exported_phase)
                for item in actual["nftables"]:
                    if "counter" in item:
                        value = item["counter"]
                        value["packets"], value["bytes"] = old[value["name"]]
                envelope["ruleset"] = actual
    result = collector.evaluate(evidence)
    assert result["status"] == "SYNTHETIC_CONTROLS_CORRELATED_REVIEW_REQUIRED"
    assert result["readiness"] == "UNVERIFIED"
    assert result["provider_calls"] == 0


def test_export_normalization_does_not_relax_snapshot_replacement_detection():
    actual = captured_export("restricted")
    replaced = copy.deepcopy(actual)
    rule = next(item["rule"] for item in replaced["nftables"] if "rule" in item)
    rule["handle"] += 100
    assert contract.policy_shape(actual) == contract.policy_shape(replaced)
    assert contract.snapshot_identity(actual) != contract.snapshot_identity(replaced)


def at(seconds):
    return (NOW + timedelta(seconds=seconds)).isoformat()


def snapshot(phase, count, seconds, inode):
    ruleset = contract.policy(phase)
    for i, item in enumerate(ruleset["nftables"], 1):
        kind, value = next(iter(item.items()))
        value["handle"] = i
        if kind == "counter":
            value["packets"] = count[value["name"]]
            value["bytes"] = count[value["name"]] * 80
    return {"network_inode": inode, "captured_at_utc": at(seconds), "ruleset": ruleset}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("package test attempted real network activity")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def evidence():
    source = {
        name: contract.digest((ROOT / "workers/scripts" / name).read_bytes())
        for name in (
            "oms_synthetic_contract.py",
            "probe_oms_synthetic_egress.py",
            "serve_oms_synthetic_peer.py",
            "collect_oms_synthetic_evidence.py",
        )
    }
    data = {
        "manifest.json": {
            "version": 1,
            "host": "srv1943844",
            "source_sha": "a" * 40,
            "host_net_inode": 11,
            "target_net_inode": 22,
            "peer_net_inode": 33,
            "host_mount_inode": 100,
            "host_ipc_inode": 200,
            "exclusive_target": True,
            "no_uplink": True,
            "fixture_positive_control": True,
            "restoration_verified": True,
            "source_sha256": source,
            "policy_sha256": {
                p: contract.digest(contract.policy_bytes(p))
                for p in ("calibration", "restricted", "peer")
            },
        }
    }
    boundary = {
        "status": "LOCAL_CHECKS_PASSED",
        "bundle_readonly": True,
        "synthetic_fixture_access": "OBSERVED_DENIAL",
        "target_uid": 10001,
        "process": {
            "effective_uid": 10001,
            "effective_capabilities": "0000000000000000",
            "no_new_privileges": True,
        },
        "namespace_inodes": {"net": 22, "mnt": 101, "ipc": 201},
    }
    events = []
    definitions = contract.cases()
    for phase, start, invocation in (("calibration", 1, "b"), ("restricted", 4, "c")):
        elapsed = 0.0
        results = []
        for i, case in enumerate(definitions):
            permitted = phase == "calibration" or case["permitted"]
            finish = elapsed + (0.02 if permitted else 1)
            challenge = contract.digest(f"{phase}:{i}".encode())
            results.append(
                {
                    **{k: case[k] for k in ("family", "address", "transport", "port")},
                    "expected": "response" if permitted else "policy_correlated_denial",
                    "outcome": "RESPONSE_MATCHED" if permitted else "NO_RESPONSE_UNVERIFIED",
                    "started_elapsed_seconds": elapsed,
                    "finished_elapsed_seconds": finish,
                    "challenge_sha256": challenge,
                }
            )
            if permitted:
                events.append(
                    {"case": i, "at_utc": at(start + elapsed + 0.01), "challenge_sha256": challenge}
                )
            elapsed = finish
        data[f"{phase}.json"] = {
            "unit": f"zippy-oms-staging-egress-probe@{phase}.service",
            "invocation_id": invocation * 32,
            "pid": 123,
            "report": {
                "status": "CALIBRATION_RESPONSES_OBSERVED"
                if phase == "calibration"
                else "CANDIDATE_CONTROLS_REQUIRE_EXTERNAL_PROOF",
                "provider_calls": 0,
                "credential_loaded": False,
                "configuration_changes": 0,
                "pid": 123,
                "phase": phase,
                "socket_attempts": 14,
                "maximum_attempts": 14,
                "run_seconds": 16.0,
                "readiness": "UNVERIFIED",
                "boundary": copy.deepcopy(boundary),
                "started_at_utc": at(start),
                "finished_at_utc": at(start + elapsed + 0.1),
                "results": results,
            },
        }
        zero = {f"m7_{i:02}": 0 for i in range(14)}
        one = dict.fromkeys(zero, 1)
        data[f"{phase}-before.json"] = snapshot(phase, zero, start - 0.5, 22)
        data[f"{phase}-after.json"] = snapshot(phase, one, start + elapsed + 0.2, 22)
        peer_before = zero if phase == "calibration" else one
        peer_after = (
            one
            if phase == "calibration"
            else {f"m7_{i:02}": 2 if case["permitted"] else 1 for i, case in enumerate(definitions)}
        )
        data[f"peer-{phase}-before.json"] = snapshot("peer", peer_before, start - 0.5, 33)
        data[f"peer-{phase}-after.json"] = snapshot("peer", peer_after, start + elapsed + 0.2, 33)
    listener = {
        "status": "LISTENER_COMPLETED",
        "pid": 456,
        "provider_calls": 0,
        "credential_loaded": False,
        "boundary": {
            "safe": True,
            "effective_uid": 10002,
            "capabilities": 1024,
            "no_new_privileges": True,
            "network_inode": 33,
        },
        "bound_cases": list(range(14)),
        "ready_at_utc": at(0),
        "finished_at_utc": at(40),
        "attempted_exchanges": 20,
        "errors": 0,
        "events": events,
    }
    ready = {**listener, "status": "LISTENERS_READY"}
    data["listener-final.json"] = {
        "unit": "zippy-oms-staging-synthetic-peer.service",
        "pid": 456,
        "invocation_id": "d" * 32,
        "report": listener,
    }
    data["listener-ready.json"] = {
        "unit": "zippy-oms-staging-synthetic-peer.service",
        "pid": 456,
        "invocation_id": "d" * 32,
        "report": ready,
    }
    data["original-policy.json"] = {
        "network_inode": 22,
        "captured_at_utc": at(-1),
        "ruleset": {
            "nftables": [{"table": {"family": "inet", "name": "zippy_oms_staging", "handle": 1}}]
        },
    }
    data["restored-policy.json"] = copy.deepcopy(data["original-policy.json"])
    data["restored-policy.json"]["captured_at_utc"] = at(45)
    return data


def test_valid_correlation_still_cannot_authorize_live_or_claim_operator_acceptance(evidence):
    result = collector.evaluate(evidence)
    assert result["status"] == "SYNTHETIC_CONTROLS_CORRELATED_REVIEW_REQUIRED"
    assert result["readiness"] == "UNVERIFIED"
    assert result["effective_egress"] == "UNVERIFIED_PENDING_OPERATOR_ACCEPTANCE"
    assert result["provider_calls"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_phase",
        "missing_counter",
        "zero_drop",
        "changed_handle",
        "extra_accept",
        "wrong_selector",
        "policy_hash",
        "code_hash",
        "wrong_namespace",
        "wrong_uid",
        "privileged_target",
        "unsafe_mount",
        "missing_listener_case",
        "listener_errors",
        "listener_died",
        "nonce_mismatch",
        "nonce_replay",
        "negative_reached_peer",
        "wrong_event_case",
        "late_event",
        "phase_overlap",
        "counter_time",
        "peer_policy",
        "peer_drop_leak",
        "permission_error",
        "unreachable",
        "short_negative",
        "counter_reset",
        "extra_table",
        "restoration",
        "no_uplink",
        "invocation_replay",
        "out_of_order_cases",
        "nan_time",
        "counter_bool",
        "boundary_inodes",
        "stale_counter",
    ],
)
def test_missing_or_misleading_evidence_fails_closed(evidence, mutation):
    restricted = evidence["restricted.json"]["report"]
    after = evidence["restricted-after.json"]["ruleset"]["nftables"]
    counters = [x["counter"] for x in after if "counter" in x]
    rules = [x["rule"] for x in after if "rule" in x]
    peer_counters = [
        x["counter"]
        for x in evidence["peer-restricted-after.json"]["ruleset"]["nftables"]
        if "counter" in x
    ]
    if mutation == "missing_phase":
        del evidence["calibration.json"]
    elif mutation == "missing_counter":
        after.remove(next(x for x in after if "counter" in x))
    elif mutation == "zero_drop":
        counters[3]["packets"] = counters[3]["bytes"] = 0
    elif mutation == "changed_handle":
        counters[3]["handle"] += 99
    elif mutation == "extra_accept":
        rules[1]["expr"].insert(0, {"accept": None})
    elif mutation == "wrong_selector":
        rules[1]["expr"][2]["match"]["right"] = "8.8.8.8"
    elif mutation == "policy_hash":
        evidence["manifest.json"]["policy_sha256"]["restricted"] = "0" * 64
    elif mutation == "code_hash":
        evidence["manifest.json"]["source_sha256"]["serve_oms_synthetic_peer.py"] = "0" * 64
    elif mutation == "wrong_namespace":
        evidence["restricted-after.json"]["network_inode"] = 11
    elif mutation == "wrong_uid":
        restricted["boundary"]["process"]["effective_uid"] = 20001
    elif mutation == "privileged_target":
        restricted["boundary"]["process"]["effective_capabilities"] = "0000000000000400"
    elif mutation == "unsafe_mount":
        restricted["boundary"]["bundle_readonly"] = None
    elif mutation == "missing_listener_case":
        evidence["listener-final.json"]["report"]["bound_cases"] = [0]
    elif mutation == "listener_errors":
        evidence["listener-final.json"]["report"]["errors"] = 1
    elif mutation == "listener_died":
        evidence["listener-final.json"]["report"]["finished_at_utc"] = at(5)
    elif mutation == "nonce_mismatch":
        restricted["results"][0]["challenge_sha256"] = "0" * 64
    elif mutation == "nonce_replay":
        restricted["results"][0]["challenge_sha256"] = evidence["calibration.json"]["report"][
            "results"
        ][0]["challenge_sha256"]
    elif mutation == "negative_reached_peer":
        restricted["results"][3]["outcome"] = "RESPONSE_MATCHED"
    elif mutation == "wrong_event_case":
        evidence["listener-final.json"]["report"]["events"][0]["case"] = 10
    elif mutation == "late_event":
        evidence["listener-final.json"]["report"]["events"][0]["at_utc"] = at(39)
    elif mutation == "phase_overlap":
        restricted["started_at_utc"] = at(1)
    elif mutation == "counter_time":
        evidence["restricted-before.json"]["captured_at_utc"] = at(10)
    elif mutation == "peer_policy":
        evidence["peer-restricted-after.json"]["ruleset"]["nftables"][1]["chain"]["policy"] = (
            "accept"
        )
    elif mutation == "peer_drop_leak":
        peer_counters[3]["packets"] += 1
    elif mutation == "permission_error":
        restricted["results"][3]["outcome"] = "PERMISSION_ERROR_UNVERIFIED"
    elif mutation == "unreachable":
        restricted["results"][3]["outcome"] = "CONNECTIVITY_ERROR_UNVERIFIED"
    elif mutation == "short_negative":
        restricted["results"][3]["finished_elapsed_seconds"] = (
            restricted["results"][3]["started_elapsed_seconds"] + 0.01
        )
    elif mutation == "counter_reset":
        evidence["peer-restricted-before.json"]["ruleset"]["nftables"] = contract.policy("peer")[
            "nftables"
        ]
    elif mutation == "extra_table":
        after.append({"table": {"family": "inet", "name": "bypass", "handle": 99}})
    elif mutation == "restoration":
        evidence["restored-policy.json"]["ruleset"]["nftables"][0]["table"]["name"] = "wrong"
    elif mutation == "no_uplink":
        evidence["manifest.json"]["no_uplink"] = False
    elif mutation == "invocation_replay":
        evidence["restricted.json"]["invocation_id"] = "b" * 32
    elif mutation == "out_of_order_cases":
        restricted["results"].reverse()
    elif mutation == "nan_time":
        restricted["results"][0]["started_elapsed_seconds"] = float("nan")
    elif mutation == "counter_bool":
        counters[0]["packets"] = True
    elif mutation == "boundary_inodes":
        restricted["boundary"]["namespace_inodes"]["mnt"] = 100
    elif mutation == "stale_counter":
        [
            x["counter"]
            for x in evidence["restricted-before.json"]["ruleset"]["nftables"]
            if "counter" in x
        ][0]["packets"] = 1
    with pytest.raises((ValueError, KeyError)):
        collector.evaluate(evidence)


def test_policies_are_exact_fixed_tuples_drop_default_and_no_host_side_effects():
    for phase in ("calibration", "restricted", "peer"):
        path = ROOT / f"infra/m7-staging/synthetic-{phase}.nft.json"
        assert path.read_bytes() == contract.policy_bytes(phase)
        commands = json.loads(path.read_bytes())
        assert all(set(item) == {"add"} for item in commands["nftables"])
        document = {"nftables": [item["add"] for item in commands["nftables"]]}
        assert all(
            next(iter(x)) in {"table", "chain", "rule", "counter"} for x in document["nftables"]
        )
        chains = [x["chain"] for x in document["nftables"] if "chain" in x]
        assert {x["hook"] for x in chains} == {"input", "output", "forward"}
        assert all(x["policy"] == "drop" for x in chains)
        rules = [
            x["rule"]
            for x in document["nftables"]
            if "rule" in x and x["rule"]["comment"].startswith(f"M7 {phase}")
        ]
        assert len(rules) == 14
        assert sum("drop" in x["expr"][-1] for x in rules) == (8 if phase == "restricted" else 0)


def test_private_loading_is_bounded_and_main_redacts_untrusted_fields(evidence, tmp_path, capsys):
    tmp_path.chmod(0o700)
    for name, value in evidence.items():
        path = tmp_path / name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    assert collector.main(["--evidence-dir", str(tmp_path)]) == 0
    capsys.readouterr()
    (tmp_path / "manifest.json").write_text(
        '{"host":"sensitive-synthetic-value","host":"srv1943844"}'
    )
    assert collector.main(["--evidence-dir", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "sensitive-synthetic-value" not in output and "NOT_VERIFIED" in output


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "mode", "oversized", "directory"])
def test_unsafe_evidence_files_fail_before_reading(tmp_path, kind):
    tmp_path.chmod(0o700)
    path = tmp_path / "manifest.json"
    if kind == "fifo":
        os.mkfifo(path, 0o600)
    elif kind == "directory":
        path.mkdir(mode=0o600)
    else:
        path.write_bytes(b"{}")
        path.chmod(0o600)
        if kind == "symlink":
            path.unlink()
            path.symlink_to(tmp_path / "missing")
        elif kind == "hardlink":
            os.link(path, tmp_path / "linked")
        elif kind == "mode":
            path.chmod(0o644)
        elif kind == "oversized":
            path.write_bytes(b"x" * (collector.LIMIT + 1))
    with pytest.raises((ValueError, OSError)):
        collector.load_private(tmp_path)


def test_defaults_are_passive(capsys):
    assert peer.main([]) == collector.main([]) == 0
    assert "PREPARATION_ONLY" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["root", "host", "namespace"])
def test_listener_denies_unsafe_boundary_before_bind(monkeypatch, kind):
    monkeypatch.setattr(peer.platform, "node", lambda: "srv1943844" if kind != "host" else "wrong")
    monkeypatch.setattr(peer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(peer.os, "geteuid", lambda: 0 if kind == "root" else 10002)
    monkeypatch.setattr(peer, "peer_boundary", lambda: {"safe": False})
    assert peer.serve()["status"] == "NOT_VERIFIED"


class Connection:
    def __init__(self, chunks):
        self.chunks = chunks
        self.sent = b""
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recv(self, _size):
        return self.chunks.pop(0)

    def sendall(self, data):
        self.sent += data


@pytest.mark.parametrize("chunks", [[b"wrong" * 9], [b""], [b"M7-CONTROL " + b"0" * 24 + b"extra"]])
def test_listener_rejects_malformed_or_oversized_challenges_without_echo(monkeypatch, chunks):
    monkeypatch.setattr(peer.time, "monotonic", lambda: 0)
    connection = Connection(chunks)
    assert peer.exchange(connection, 1) is None and connection.sent == b""


def test_listener_reassembles_echo_under_one_deadline(monkeypatch):
    clock = iter([0, 0.1, 0.2, 0.3, 0.4])
    monkeypatch.setattr(peer.time, "monotonic", lambda: next(clock))
    connection = Connection([b"M7-CONTROL ", b"0" * 24])
    assert peer.exchange(connection, 1) == b"M7-CONTROL " + b"0" * 24
    assert connection.sent.endswith(b"0" * 24) and all(0 < t <= 1 for t in connection.timeouts)


def test_listener_template_has_only_bind_privilege_and_separate_namespace_marker():
    text = (ROOT / "infra/m7-staging/zippy-oms-staging-synthetic-peer.service.in").read_text()
    assert "CapabilityBoundingSet=CAP_NET_BIND_SERVICE" in text
    assert "AmbientCapabilities=CAP_NET_BIND_SERVICE" in text
    assert "owner-synthetic-peer-enabled" in text
    assert "NetworkNamespacePath=/run/netns/zippy-m7-synthetic-peer" in text
    assert "TimeoutStartSec=42" in text and "Restart=no" in text
    assert "[Install]" not in text and "LoadCredential=" not in text and "CAP_NET_ADMIN" not in text


@pytest.mark.parametrize("mode", ["idle", "partial_bind", "budget"])
def test_listener_closes_every_socket_after_deadline_partial_bind_or_budget(monkeypatch, mode):
    clock = [0.0]
    created = []
    monkeypatch.setattr(peer.platform, "node", lambda: "srv1943844")
    monkeypatch.setattr(peer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(peer.os, "geteuid", lambda: 10002)
    monkeypatch.setattr(peer, "peer_boundary", lambda: {"safe": True})
    monkeypatch.setattr(peer.time, "monotonic", lambda: clock[0])

    class Accepted(Connection):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

    class BoundSocket:
        def __init__(self, family, kind):
            self.family = family
            self.kind = kind
            self.closed = False
            self.bound = None
            self.v6only = False
            created.append(self)

        def setsockopt(self, _level, _name, value):
            self.v6only = value == 1

        def setblocking(self, _value):
            pass

        def bind(self, address):
            if mode == "partial_bind" and len(created) == 3:
                raise OSError("sensitive-synthetic-error")
            self.bound = address

        def listen(self, _backlog):
            pass

        def accept(self):
            return Accepted([b"M7-CONTROL " + b"0" * 24]), ("192.0.2.1", 10000)

        def close(self):
            self.closed = True

    class Selector:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def register(self, _sock, _events, _index):
            pass

        def select(self, _timeout):
            if mode == "idle":
                clock[0] = 40
                return []
            clock[0] += 0.01
            return [(SimpleNamespace(fileobj=created[0], data=0), 1)]

    monkeypatch.setattr(socket, "socket", BoundSocket)
    monkeypatch.setattr(peer.selectors, "DefaultSelector", Selector)
    report = peer.serve()
    assert all(s.closed for s in created)
    if mode == "idle":
        assert report["status"] == "LISTENER_COMPLETED" and len(created) == 14
        assert report["attempted_exchanges"] == 0
        assert all(s.v6only for s in created if s.family == socket.AF_INET6)
    elif mode == "budget":
        assert report["status"] == "NOT_VERIFIED" and report["attempted_exchanges"] == 28
    else:
        assert report["status"] == "NOT_VERIFIED" and len(created) == 3
        assert "sensitive-synthetic-error" not in json.dumps(report)


def test_last_nonce_byte_may_arrive_in_a_separate_tcp_fragment(monkeypatch):
    monkeypatch.setattr(peer.time, "monotonic", lambda: 0)
    connection = Connection([b"M7-CONTROL ", b"0" * 23, b"0"])
    assert peer.exchange(connection, 1) == b"M7-CONTROL " + b"0" * 24


def test_client_receipt_is_only_a_synthetic_fingerprint(monkeypatch):
    from test_synthetic_egress_probe import FakeSocket
    from test_synthetic_egress_probe import probe as client

    connection = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *_args: connection)
    monkeypatch.setattr(client.time, "monotonic", lambda: 0)
    receipt = {}
    assert client.attempt(client.control_cases()[0], 16, receipt=receipt) == "RESPONSE_MATCHED"
    assert receipt == {"challenge_sha256": contract.digest(connection.sent)}
    assert connection.sent.decode() not in json.dumps(receipt)


def test_client_and_policies_use_the_same_fourteen_fixed_cases():
    from test_synthetic_egress_probe import probe as client

    for concrete, expected in zip(client.control_cases(), contract.cases(), strict=True):
        assert concrete.family == (
            socket.AF_INET if expected["family"] == "ipv4" else socket.AF_INET6
        )
        assert (concrete.address, concrete.transport, concrete.port, concrete.permitted) == (
            expected["address"],
            expected["transport"],
            expected["port"],
            expected["permitted"],
        )
