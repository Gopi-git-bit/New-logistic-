"""Read-only observer behavior; no local-host facts promoted to target proof."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/collect_oms_staging_evidence.py"
SPEC = importlib.util.spec_from_file_location("staging_evidence", PATH)
assert SPEC is not None and SPEC.loader is not None
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


def test_wrong_host_cannot_collect_or_claim_target_evidence(monkeypatch):
    monkeypatch.setattr(evidence.platform, "node", lambda: "local-workstation")
    monkeypatch.setattr(evidence, "observe", lambda _args: pytest.fail("wrong host queried target"))
    report = evidence.collect("srv1943844")
    assert report["status"] == "WRONG_HOST" and report["readiness"] == "UNVERIFIED"


@pytest.mark.parametrize("uid,observation", [(0, "PRIVILEGED"), (10001, "NONROOT_OBSERVED")])
def test_effective_uid_and_mount_flags_are_facts_only(uid, observation):
    report = evidence.parse_process(
        f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\nCapEff:\t0000000000000000\n",
        "1 0 0:1 / / ro,nosuid - overlay overlay ro\n"
        "2 1 0:2 / /opt/new-logistic ro,nodev - tmpfs tmpfs ro\n",
    )
    assert report["effective_uid"] == uid and report["identity_observation"] == observation
    assert report["mount_access_denial"] == "UNVERIFIED_NO_ACCESS_PROBE"
    assert len(report["matching_mounts"]) == 2


def test_firewall_policy_or_hash_cannot_claim_effective_destination_denial():
    report = evidence.nft_metadata(
        '{"nftables":[{"chain":{"family":"inet","table":"zippy_oms_staging",'
        '"name":"output","policy":"drop"}}]}'
    )
    assert report["chain_policies"] == {"output": "drop"}
    assert report["effective_destination_denial"] == "UNVERIFIED_NO_CONNECTIVITY_PROBES"
    assert len(report["rules_sha256"]) == 64


@pytest.mark.parametrize("text", [None, "invalid-json", "{}", "[]", '{"nftables":null}'])
def test_missing_or_malformed_firewall_evidence_stays_unknown(text):
    assert evidence.nft_metadata(text) is None


def test_no_running_target_is_not_replaced_by_root_observer(monkeypatch):
    commands = []
    monkeypatch.setattr(evidence.platform, "node", lambda: "srv1943844")
    monkeypatch.setattr(evidence.platform, "system", lambda: "Linux")
    monkeypatch.setattr(evidence.os, "geteuid", lambda: 0)
    monkeypatch.setattr(evidence, "file_metadata", lambda _path: None)

    def observe(args):
        commands.append(args)
        return "LoadState=not-found\nMainPID=0\n" if args[0] == "systemctl" else None

    monkeypatch.setattr(evidence, "observe", observe)
    report = evidence.collect("srv1943844")
    assert report["observer_uid"] == 0
    assert report["process_observation"] == "UNVERIFIED_NO_RUNNING_TARGET"
    assert report["readiness"] == "UNVERIFIED" and report["provider_calls"] == 0
    assert all(args[0] in {"systemctl", "ip"} for args in commands)
    assert "start" not in commands[0] and "apply" not in commands[1]
    assert not any("Environment" in arg or "ExecStart" in arg for arg in commands[0])


def test_credential_metadata_never_reads_or_hashes_contents(tmp_path):
    key = tmp_path / "synthetic.key"
    key.write_text("synthetic-sensitive-data")
    key.chmod(0o600)
    report = evidence.file_metadata(key)
    assert report["regular_file"] and report["mode"] == "0o600"
    assert "synthetic-sensitive-data" not in str(report)
