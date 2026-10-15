"""Fake local commands only; real namespace tests run separately on hosted CI."""

import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/restore_oms_staging_baseline.py"
spec = importlib.util.spec_from_file_location("baseline", SCRIPT)
assert spec and spec.loader
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def empty():
    link = {"ifname": "lo", "operstate": "DOWN", "flags": ["LOOPBACK"], "addr_info": []}
    return {
        "links": [link],
        "addresses": [copy.deepcopy(link)],
        "routes4": [],
        "routes6": [],
        "neighbors": [],
    }


@pytest.fixture(autouse=True)
def no_commands(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unit test attempted real command")

    monkeypatch.setattr(baseline.subprocess, "run", forbidden)


@pytest.fixture
def flow(monkeypatch, tmp_path):
    path = tmp_path / "namespace"
    state = {
        "host": {"fixed": "unchanged"},
        "identity": [8, 99],
        "users": "",
        "record": {},
        "topology": empty(),
        "policy": baseline.expected_policy(),
        "failure": False,
        "replace": False,
        "loaded": False,
    }
    calls = []

    class Fake:
        def run(self, args, data=None):
            calls.append((args, data))
            if args[1:3] == ["netns", "add"]:
                path.touch(exist_ok=False)
            elif args[1:3] == ["netns", "delete"]:
                path.unlink()
            elif args[1:3] == ["netns", "pids"]:
                return state["users"]
            elif "--file" in args:
                assert data.encode() == baseline.POLICY.read_bytes()
                if "--check" not in args:
                    if state["failure"]:
                        raise baseline.Refused("INJECTED_POLICY_FAILURE")
                    if state["replace"]:
                        state["identity"] = [8, 100]
                    state["loaded"] = True
            return ""

        def read_json(self, args):
            assert args[-2:] == ["list", "ruleset"]
            return state["policy"] if state["loaded"] else {"nftables": []}

    monkeypatch.setattr(baseline, "NS_PATH", path)
    monkeypatch.setattr(baseline, "private_folder", lambda folder: None)
    monkeypatch.setattr(baseline, "trusted_parents", lambda folder: None)
    monkeypatch.setattr(baseline, "identity", lambda path: state["identity"])
    monkeypatch.setattr(baseline, "host_state", lambda *args: copy.deepcopy(state["host"]))
    monkeypatch.setattr(baseline, "topology", lambda commands: state["topology"])
    monkeypatch.setattr(
        baseline, "record", lambda folder, value: state.update(record=copy.deepcopy(value))
    )
    return Fake(), state, calls, tmp_path, path


def test_default_passive(capsys):
    assert baseline.main([]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PLAN_ONLY"


def test_apply_verify_rollback(flow):
    commands, state, calls, parent, path = flow
    folder = baseline.apply(commands, parent)
    assert path.exists() and state["record"]["state"] == "BASELINE_VERIFIED"
    baseline.verify(commands, folder, state["record"])
    baseline.rollback(commands, folder, state["record"])
    assert not path.exists() and state["record"]["state"] == "REMOVED"
    writes = [a for a, data in calls if "add" in a or "delete" in a or "--file" in a]
    assert writes[0] == [baseline.IP, "netns", "add", baseline.NAMESPACE]
    assert writes[-1] == [baseline.IP, "netns", "delete", baseline.NAMESPACE]
    assert all(a[1:4] == ["netns", "exec", baseline.NAMESPACE] for a in writes[1:-1])


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_existing_refused(flow, kind):
    commands, state, calls, parent, path = flow
    path.touch() if kind == "file" else path.symlink_to(parent / "missing")
    with pytest.raises(baseline.Refused, match="EXISTING_NAMESPACE_REFUSED"):
        baseline.apply(commands, parent)
    assert not calls and os.path.lexists(path)


@pytest.mark.parametrize("mutation", ["users", "identity", "topology", "host"])
def test_unsafe_rollback_refused(flow, mutation):
    commands, state, calls, parent, path = flow
    folder = baseline.apply(commands, parent)
    value = copy.deepcopy(state["record"])
    if mutation == "users":
        state["users"] = "1234\n"
    elif mutation == "identity":
        state["identity"] = [8, 100]
    elif mutation == "topology":
        state["topology"]["links"].append({"ifname": "eth0"})
    else:
        state["host"] = {"fixed": "changed"}
    with pytest.raises(baseline.Refused):
        baseline.rollback(commands, folder, value)
    assert path.exists() is (mutation != "host")
    assert not any("kill" in a or "flush" in a for a, data in calls)


@pytest.mark.parametrize("mutation", ["failure", "replace"])
def test_partial_failure_keeps_receipt_and_never_autodeletes(flow, mutation):
    commands, state, calls, parent, path = flow
    state[mutation] = True
    with pytest.raises(baseline.Refused):
        baseline.apply(commands, parent)
    assert path.exists() and state["record"]["created"] is True
    assert state["record"]["state"] == "NOT_VERIFIED"
    assert not any(a[1:3] == ["netns", "delete"] for a, data in calls)
    if mutation == "failure":
        baseline.rollback(commands, next(parent.glob("zippy-m7-restore-*")), state["record"])
        assert not path.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "set",
        "extra_rule",
        "verdict",
        "port",
        "chain",
        "order",
        "unknown",
        "missing_set",
        "priority_type",
    ],
)
def test_full_policy_rejects_differences(mutation):
    expected = baseline.expected_policy()
    actual = copy.deepcopy(expected)
    sets = [x["set"] for x in actual["nftables"] if "set" in x]
    rules = [x["rule"] for x in actual["nftables"] if "rule" in x]
    chains = [x["chain"] for x in actual["nftables"] if "chain" in x]
    if mutation == "set":
        sets[0]["elem"] = ["192.0.2.99"]
    elif mutation == "extra_rule":
        actual["nftables"].append({"rule": copy.deepcopy(rules[0])})
    elif mutation == "verdict":
        rules[0]["expr"][-1] = {"drop": None}
    elif mutation == "port":
        rules[1]["expr"][1]["match"]["right"] = 80
    elif mutation == "chain":
        chains[0]["policy"] = "accept"
    elif mutation == "order":
        rules[1]["expr"].reverse()
    elif mutation == "unknown":
        actual["nftables"].append({"flowtable": {"name": "bypass"}})
    elif mutation == "missing_set":
        actual["nftables"].remove(next(x for x in actual["nftables"] if "set" in x))
    else:
        chains[0]["prio"] = False
    try:
        result = baseline.policy_shape(actual)
    except baseline.Refused:
        assert mutation == "unknown"
    else:
        assert result != baseline.policy_shape(expected)


@pytest.mark.parametrize("mutation", ["link", "up", "address", "route4", "route6", "neighbor"])
def test_topology_rejects_connectivity(mutation):
    value = empty()
    if mutation == "link":
        value["links"].append({"ifname": "eth0"})
    elif mutation == "up":
        value["links"][0]["flags"].append("UP")
    elif mutation == "address":
        value["addresses"][0]["addr_info"].append({"local": "127.0.0.1"})
    else:
        value[{"route4": "routes4", "route6": "routes6", "neighbor": "neighbors"}[mutation]] = [{}]
    with pytest.raises(baseline.Refused):
        baseline.empty_topology(value)


def test_host_gate_blocks_before_commands(monkeypatch, capsys):
    monkeypatch.setattr(baseline.platform, "system", lambda: "Linux")
    monkeypatch.setattr(baseline.os, "geteuid", lambda: 0)
    monkeypatch.setattr(baseline.platform, "node", lambda: "not-the-vps")
    assert baseline.main(["apply"]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "HOST_NAME_MISMATCH"


@pytest.mark.parametrize("mutation", ["boot", "script", "state", "mode", "symlink", "hardlink"])
def test_receipt_replay_and_unsafe_file_refused(monkeypatch, tmp_path, mutation):
    receipt = tmp_path / "receipt.json"
    value = {
        "version": 1,
        "namespace": baseline.NAMESPACE,
        "boot_id": baseline.boot_id(),
        "script_sha256": baseline.digest(SCRIPT.read_bytes()),
        "policy_sha256": baseline.POLICY_SHA,
        "state": "BASELINE_VERIFIED",
    }
    if mutation == "boot":
        value["boot_id"] = "old-boot"
    elif mutation == "script":
        value["script_sha256"] = "0" * 64
    elif mutation == "state":
        value["state"] = "IN_PROGRESS"
    receipt.write_text(json.dumps(value))
    receipt.chmod(0o644 if mutation == "mode" else 0o600)
    if mutation == "symlink":
        receipt.rename(tmp_path / "target")
        receipt.symlink_to(tmp_path / "target")
    elif mutation == "hardlink":
        os.link(receipt, tmp_path / "linked")
    monkeypatch.setattr(baseline, "private_folder", lambda path: None)
    original = os.fstat

    def fstat(fd):
        info = original(fd)
        return SimpleNamespace(
            st_mode=info.st_mode, st_uid=0, st_nlink=info.st_nlink, st_size=info.st_size
        )

    monkeypatch.setattr(baseline.os, "fstat", fstat)
    with pytest.raises((OSError, baseline.Refused)):
        baseline.read_receipt(tmp_path)


@pytest.mark.parametrize(
    "mode,uid,valid",
    [
        (0o40755, 0, True),
        (0o41777, 0, True),
        (0o40777, 0, False),
        (0o40755, 1000, False),
        (0o120777, 0, False),
    ],
)
def test_parent_ownership_and_link_guards(mode, uid, valid):
    path = SimpleNamespace(parents=(), lstat=lambda: SimpleNamespace(st_mode=mode, st_uid=uid))
    if valid:
        baseline.trusted_parents(path)
    else:
        with pytest.raises(baseline.Refused, match="EVIDENCE_PARENT_UNSAFE"):
            baseline.trusted_parents(path)


def test_host_policy_comparison_ignores_only_documented_runtime_fields():
    first = "# Generated by iptables-save yesterday\n*filter\n:INPUT DROP [1:2]\n-A INPUT -p tcp --dport 22 -j ACCEPT\nCOMMIT\n"
    later = first.replace("yesterday", "today").replace("[1:2]", "[99:999]")
    assert baseline.iptables_policy(first) == baseline.iptables_policy(later)
    for changed in (
        later.replace("DROP", "ACCEPT"),
        later.replace("--dport 22", "--dport 443"),
        later.replace(":INPUT", ":OUTPUT"),
    ):
        assert baseline.iptables_policy(first) != baseline.iptables_policy(changed)


def test_recorded_real_baseline_export_matches_contract():
    fixture = Path(__file__).parent / "fixtures/nft-1.0.9-baseline.json"
    actual = json.loads(fixture.read_text())
    assert baseline.policy_shape(actual) == baseline.policy_shape(baseline.expected_policy())


def test_bridge_countdowns_do_not_hide_configuration_changes():
    before = [
        {
            "ifindex": 3,
            "ifname": "docker0",
            "mtu": 1500,
            "linkinfo": {
                "info_kind": "bridge",
                "info_data": {
                    "hello_time": 200,
                    "ageing_time": 30000,
                    "hello_timer": 0,
                    "tcn_timer": 0,
                    "topology_change_timer": 0,
                    "gc_timer": 123,
                },
            },
        }
    ]
    after = copy.deepcopy(before)
    after[0]["linkinfo"]["info_data"]["gc_timer"] = 122
    assert baseline.host_links(before) == baseline.host_links(after)
    assert before[0]["linkinfo"]["info_data"]["gc_timer"] == 123
    for field in ("hello_time", "ageing_time", "unexpected_timer"):
        changed = copy.deepcopy(after)
        changed[0]["linkinfo"]["info_data"][field] = -1
        assert baseline.host_links(changed) != baseline.host_links(before)
    after[0]["mtu"] = 1400
    assert baseline.host_links(before) != baseline.host_links(after)
