"""Offline regressions for admission, process boundaries and uncertain cleanup.

These tests never invoke Docker, PostgreSQL, provider endpoints or GitHub APIs.
Synthetic XML/command responses test the verifier, not the 72 integration cases.
"""

from __future__ import annotations

import copy
import errno
import json
import os
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from db.scripts import admit_disposable_ci as admit
from db.scripts import disposable_contract as c
from db.scripts import disposable_runtime as runtime
from db.scripts import run_disposable_ci as runner

SHA = "a" * 40
NOW = datetime(2026, 10, 17, tzinfo=UTC)
EXPIRY = (NOW + timedelta(minutes=45)).isoformat()


def environment():
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": c.REPOSITORY,
        "GITHUB_REPOSITORY_ID": "1349197102",
        "GITHUB_REPOSITORY_OWNER_ID": "200721521",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ACTOR": "Gopi-git-bit",
        "GITHUB_ACTOR_ID": "200721521",
        "GITHUB_TRIGGERING_ACTOR": "Gopi-git-bit",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": SHA,
        "GITHUB_WORKFLOW_SHA": SHA,
        "GITHUB_WORKFLOW_REF": c.WORKFLOW,
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
        "GITHUB_RUN_ID": "123",
    }


def test_owner_exact_main_first_attempt_is_admitted():
    assert c.admission(environment(), SHA, EXPIRY, NOW) == environment()


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_REF", "refs/tags/main"),
        ("GITHUB_REPOSITORY", "fork/repo"),
        ("GITHUB_ACTOR", "someone"),
        ("GITHUB_ACTOR_ID", "1"),
        ("GITHUB_TRIGGERING_ACTOR", "someone"),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("GITHUB_SHA", "b" * 40),
        ("GITHUB_WORKFLOW_SHA", "b" * 40),
        ("RUNNER_ENVIRONMENT", "self-hosted"),
        ("RUNNER_OS", "Windows"),
        ("RUNNER_ARCH", "ARM64"),
        ("GITHUB_RUN_ID", "1; echo injection"),
        ("GITHUB_WORKFLOW_REF", "unreviewed"),
    ],
)
def test_unauthorized_context_fails_before_resources(field, value):
    env = environment() | {field: value}
    with pytest.raises(c.ProofError):
        c.admission(env, SHA, EXPIRY, NOW)


@pytest.mark.parametrize(
    "expiry", [NOW.isoformat(), (NOW + timedelta(hours=2)).isoformat(), "2026-10-17T00:45:00"]
)
def test_stale_unbounded_or_naive_authorization_is_rejected(expiry):
    with pytest.raises(c.ProofError):
        c.admission(environment(), SHA, expiry, NOW)


def ci():
    run = {
        "head_sha": SHA,
        "event": "push",
        "head_branch": "main",
        "path": ".github/workflows/ci.yml",
        "status": "completed",
        "conclusion": "success",
    }
    jobs = [
        {"name": name, "head_sha": SHA, "status": "completed", "conclusion": "success"}
        for name in sorted(c.CHECKS)
    ]
    return run, jobs


def test_matching_five_job_postmerge_ci_is_required():
    c.ci_accept(*ci(), SHA)


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "failed", "wrong_sha", "wrong_workflow", "pr_event"]
)
def test_unrelated_or_incomplete_ci_cannot_authorize(change):
    run, jobs = ci()
    if change == "missing":
        jobs.pop()
    if change == "duplicate":
        jobs[-1] = dict(jobs[0])
    if change == "failed":
        jobs[0]["conclusion"] = "failure"
    if change == "wrong_sha":
        jobs[0]["head_sha"] = "b" * 40
    if change == "wrong_workflow":
        run["path"] = "other.yml"
    if change == "pr_event":
        run["event"] = "pull_request"
    with pytest.raises(c.ProofError):
        c.ci_accept(run, jobs, SHA)


def container():
    return {
        "Config": {"Labels": {"zippy.proof": "run:nonce"}, "User": "10001:10001"},
        "Image": "sha256:" + "b" * 64,
        "HostConfig": {
            "NetworkMode": "none",
            "PortBindings": {},
            "Privileged": False,
            "PidMode": "",
            "IpcMode": "private",
            "Devices": [],
            "Memory": 2_147_483_648,
            "NanoCpus": 2_000_000_000,
            "PidsLimit": 256,
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "SecurityOpt": ["no-new-privileges"],
            "Tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=268435456"},
        },
        "Mounts": [
            {"Type": "bind", "Destination": "/workspace", "Source": "/owned/source", "RW": False}
        ],
    }


def verify(info):
    c.inspect_container(
        info,
        image="sha256:" + "b" * 64,
        label="run:nonce",
        mounts={"/workspace": ("/owned/source", False)},
        test_uid=10001,
    )


def test_hardened_unprivileged_container_passes_observation():
    verify(container())


@pytest.mark.parametrize(
    "field,value",
    [
        ("NetworkMode", "bridge"),
        ("PortBindings", {"5432/tcp": [{}]}),
        ("Privileged", True),
        ("PidMode", "host"),
        ("IpcMode", "host"),
        ("Devices", [{"PathOnHost": "/dev/kvm"}]),
        ("Memory", 0),
        ("NanoCpus", 0),
        ("PidsLimit", -1),
        ("ReadonlyRootfs", False),
        ("CapDrop", []),
        ("CapAdd", ["SYS_ADMIN"]),
        ("SecurityOpt", []),
        ("Tmpfs", {"/tmp": "size=1073741824"}),
    ],
)
def test_weakened_container_boundary_is_rejected(field, value):
    info = container()
    info["HostConfig"][field] = value
    with pytest.raises(c.ProofError):
        verify(info)


@pytest.mark.parametrize(
    "change", ["root", "wrong_image", "wrong_label", "writable", "extra", "duplicate"]
)
def test_wrong_identity_or_unsafe_mount_cannot_pass(change):
    info = container()
    if change == "root":
        info["Config"]["User"] = "0:0"
    if change == "wrong_image":
        info["Image"] = "sha256:" + "c" * 64
    if change == "wrong_label":
        info["Config"]["Labels"]["zippy.proof"] = "foreign"
    if change == "writable":
        info["Mounts"][0]["RW"] = True
    if change == "extra":
        info["Mounts"].append(
            {
                "Type": "bind",
                "Destination": "/var/run/docker.sock",
                "Source": "/var/run/docker.sock",
                "RW": True,
            }
        )
    if change == "duplicate":
        info["Mounts"].append(copy.deepcopy(info["Mounts"][0]))
    with pytest.raises(c.ProofError):
        verify(info)


@pytest.mark.parametrize("uid,caps,nnp", [(0, "0", "1"), (10001, "1", "1"), (10001, "0", "0")])
def test_observed_process_privileges_cannot_be_inferred_from_template(uid, caps, nnp):
    text = f"Uid:\t{uid} {uid} {uid} {uid}\nCapEff:\t{caps}\nNoNewPrivs:\t{nnp}\n"
    with pytest.raises(c.ProofError):
        c.status_observation(text, uid)


@pytest.mark.parametrize(
    "denied,error,accepted",
    [
        (True, errno.EACCES, True),
        (True, errno.EPERM, True),
        (True, errno.ENOENT, False),
        (True, errno.ECONNREFUSED, False),
        (True, errno.ETIMEDOUT, False),
        (True, None, False),
        (False, None, True),
        (False, errno.EACCES, False),
    ],
)
def test_only_real_permission_denial_counts_for_private_socket(
    monkeypatch, denied, error, accepted
):
    probe = Mock()
    probe.__enter__ = Mock(return_value=probe)
    probe.__exit__ = Mock(return_value=False)
    if error is not None:
        probe.connect.side_effect = OSError(error, "synthetic")
    monkeypatch.setattr(socket, "socket", lambda *_: probe)
    if accepted:
        runtime.socket_control("/synthetic/socket", denied)
    else:
        with pytest.raises(c.ProofError):
            runtime.socket_control("/synthetic/socket", denied)
    probe.settimeout.assert_called_once_with(5)


def xml_report(path, phase):
    root = ET.Element("testsuite")
    for module, count in c.GROUPS[phase].items():
        for number in range(count):
            ET.SubElement(
                root, "testcase", classname="api.tests." + module, name=f"test_case_{number}"
            )
    ET.ElementTree(root).write(path)
    path.chmod(0o600)


@pytest.mark.parametrize("phase,count", [("operations", 60), ("governance", 12)])
def test_report_inventory_requires_canonical_integration_groups(tmp_path, phase, count):
    path = tmp_path / "results.xml"
    xml_report(path, phase)
    cases, groups = c.report_cases(path, phase)
    assert len(cases) == sum(groups.values()) == count


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_any_unsuccessful_result_keeps_database_gap_open(tmp_path, outcome):
    path = tmp_path / "results.xml"
    xml_report(path, "operations")
    tree = ET.parse(path)
    ET.SubElement(tree.getroot()[0], outcome)
    tree.write(path)
    with pytest.raises(ValueError):
        c.report_cases(path, "operations")


def test_private_receipt_rejects_symlink_hardlink_and_open_permissions(tmp_path):
    source = tmp_path / "receipt.json"
    source.write_text("{}")
    source.chmod(0o644)
    with pytest.raises(c.ProofError):
        c.read_private(source)
    source.chmod(0o600)
    link = tmp_path / "linked.json"
    link.symlink_to(source)
    with pytest.raises(c.ProofError):
        c.read_private(link)
    os.link(source, tmp_path / "hard.json")
    with pytest.raises(c.ProofError):
        c.read_private(source)


@pytest.mark.parametrize(
    "payload,secrets",
    [
        ({"note": "generated-sensitive-value"}, ["generated-sensitive-value"]),
        ({"note": "Bearer synthetic-token"}, []),
        ({"note": "postgresql://synthetic"}, []),
        ({"note": "x" * 1_048_576}, []),
    ],
)
def test_secret_bearing_or_oversized_summary_is_rejected(payload, secrets):
    with pytest.raises(c.ProofError):
        c.sanitized(payload, secrets)


def test_child_environment_excludes_ambient_credentials_and_proxies(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-never-forward")
    monkeypatch.setenv("DATABASE_URL", "synthetic-never-forward")
    monkeypatch.setenv("GH_TOKEN", "synthetic-never-forward")
    monkeypatch.setenv("HTTP_PROXY", "synthetic-never-forward")
    executor = runner.Executor(tmp_path, time.monotonic() + 5, {"commands": []})
    assert (
        not {"DEEPSEEK_API_KEY", "DATABASE_URL", "GH_TOKEN", "HTTP_PROXY"}
        & executor.environment.keys()
    )


def test_nonzero_exit_and_timeout_are_not_masked_by_log_capture(tmp_path):
    report = {"commands": []}
    executor = runner.Executor(tmp_path, time.monotonic() + 5, report)
    with pytest.raises(c.ProofError, match="COMMAND_FAILED"):
        executor.run([sys.executable, "-c", "print('synthetic-private');raise SystemExit(7)"])
    assert report["commands"][0]["exit"] == 7
    with pytest.raises(c.ProofError, match="COMMAND_TIMEOUT"):
        executor.run([sys.executable, "-c", "import time;time.sleep(1)"], timeout=0.02)
    assert report["commands"][1]["exit"] == "TIMEOUT"


def phase(tmp_path, monkeypatch):
    original = runner.tempfile.mkdtemp
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda **kw: original(dir=tmp_path, **kw))
    monkeypatch.setattr(runner.os, "chown", lambda *_: None)
    command = Mock()
    command.report = {}
    return runner.Phase(
        "operations",
        tmp_path,
        tmp_path / "source",
        "sha256:" + "b" * 64,
        os.getuid() or 10001,
        os.getgid() or 10001,
        {"run_id": "123", "source_sha": SHA},
        command,
    ), command


def test_daemon_failure_is_not_absence_and_preserves_bind_paths(tmp_path, monkeypatch):
    proof, command = phase(tmp_path, monkeypatch)
    proof.containers["owned"] = "a" * 64
    command.out.side_effect = c.ProofError("COMMAND_FAILED")
    with pytest.raises(c.ProofError, match="CLEANUP_NOT_VERIFIED"):
        proof.cleanup()
    assert proof.record["cleanup"] == "UNKNOWN"
    assert proof.socket.exists()


def test_cleanup_refuses_foreign_labels(tmp_path, monkeypatch):
    proof, command = phase(tmp_path, monkeypatch)
    proof.containers["owned"] = "a" * 64
    command.out.side_effect = [
        "a" * 64,
        json.dumps([{"Id": "a" * 64, "Config": {"Labels": {"zippy.proof": "foreign"}}}]),
    ]
    with pytest.raises(c.ProofError):
        proof.cleanup()
    assert not any(call.args[0][1:3] == ["rm", "-f"] for call in command.out.call_args_list)
    assert proof.socket.exists()


def test_unknown_create_exit_can_only_reconcile_owned_label(tmp_path, monkeypatch):
    proof, command = phase(tmp_path, monkeypatch)
    proof.containers["owned"] = ""
    command.out.side_effect = [
        "a" * 64,
        json.dumps([{"Id": "a" * 64, "Config": {"Labels": {"zippy.proof": proof.label}}}]),
        "",
        "",
    ]
    proof.cleanup()
    assert proof.record["cleanup"] == "PASS"
    assert not proof.socket.exists()
    assert any(
        call.args[0] == ["docker", "rm", "-f", "a" * 64] for call in command.out.call_args_list
    )


def test_wrong_socket_inode_is_preserved_instead_of_deleted(tmp_path, monkeypatch):
    proof, _ = phase(tmp_path, monkeypatch)
    proof.record["resources"]["socket_identity"][1] += 1
    with pytest.raises(c.ProofError):
        proof.cleanup()
    assert proof.socket.exists()


def test_workflow_has_manual_only_trigger_and_pinned_actions():
    # Structural trigger/permission regression; no hosted workflow is dispatched.
    import re

    text = (
        Path(__file__).resolve().parents[2] / ".github/workflows/disposable-db-proofs.yml"
    ).read_text()
    assert "  workflow_dispatch:" in text
    assert not any(
        trigger in text
        for trigger in ("  pull_request:", "  push:", "workflow_run:", "pull_request_target:")
    )
    assert "secrets." not in text and "packages: write" not in text and "id-token:" not in text
    actions = re.findall(r"uses: ([^\s]+)", text)
    assert len(actions) == 2 and all(
        re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", action) for action in actions
    )
    assert "github.run_attempt == 1" in text and "timeout-minutes: 30" in text


def test_admission_failure_does_not_print_api_exception(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        ["admit", "--source", SHA, "--expires", EXPIRY, "--output", str(tmp_path / "receipt")],
    )
    monkeypatch.setattr(admit, "admission", lambda *_: environment())
    monkeypatch.setenv("GH_TOKEN", "synthetic-never-print")
    monkeypatch.setattr(admit, "get", Mock(side_effect=ValueError("synthetic-never-print")))
    assert admit.main() == 1
    assert capsys.readouterr().out.strip() == "DISPOSABLE_ADMISSION_NOT_VERIFIED"
    assert not (tmp_path / "receipt").exists()


def test_runtime_unexpected_error_is_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["runtime", "test"])
    monkeypatch.setattr(os, "geteuid", lambda: 10001)
    monkeypatch.setattr(Path, "exists", lambda _: False)
    monkeypatch.setattr(
        runtime, "run_phase", Mock(side_effect=RuntimeError("synthetic-private-value"))
    )
    assert runtime.main() == 1
    assert capsys.readouterr().out.strip() == "DISPOSABLE_RUNTIME_NOT_VERIFIED"


def bound_report(tmp_path):
    path = tmp_path / "results.xml"
    xml_report(path, "operations")
    cases, counts = c.report_cases(path, "operations")
    result = {
        "schema": 1,
        "phase": "operations",
        "source_sha": SHA,
        "run_id": "123",
        "nonce": "fresh",
        "process": {
            "effective_uid": 10001,
            "effective_capabilities": "0000000000000000",
            "no_new_privileges": True,
        },
        "namespaces": {"net": 3, "mnt": 4, "ipc": 5},
        "network_none_observed": True,
        "role": "zippy_m2_app_login",
        "restricted_role": True,
        "positive_authentication": True,
        "pytest_exit": 0,
        "report_sha256": c.digest(path.read_bytes()),
        "cases": cases,
        "integration_counts": counts,
        "skips": 0,
    }
    return path, result


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha", "b" * 40),
        ("run_id", "122"),
        ("nonce", "old"),
        ("phase", "governance"),
        ("report_sha256", "0" * 64),
        ("pytest_exit", 1),
        ("skips", 1),
        ("restricted_role", False),
        ("network_none_observed", False),
    ],
)
def test_stale_mismatched_or_unsuccessful_runtime_cannot_close_gap(tmp_path, field, value):
    path, result = bound_report(tmp_path)
    result[field] = value
    with pytest.raises(c.ProofError):
        c.accept_runtime(
            result, path, phase="operations", source=SHA, run_id="123", nonce="fresh", uid=10001
        )


def test_bound_successful_report_is_accepted_without_extra_fields(tmp_path):
    path, result = bound_report(tmp_path)
    c.accept_runtime(
        result, path, phase="operations", source=SHA, run_id="123", nonce="fresh", uid=10001
    )
    result["unreviewed"] = "synthetic-private-value"
    with pytest.raises(c.ProofError):
        c.accept_runtime(
            result, path, phase="operations", source=SHA, run_id="123", nonce="fresh", uid=10001
        )


def test_environment_file_rejects_newline_injection_and_is_private(tmp_path):
    path = tmp_path / "environment"
    with pytest.raises(c.ProofError):
        runner.environment_file(path, {"APP_ENV": "test\nGH_TOKEN=unexpected"})
    assert not path.exists()
    runner.environment_file(path, {"APP_ENV": "test"})
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        runner.environment_file(path, {"APP_ENV": "test"})


def test_source_drift_is_rejected_before_build_context(tmp_path):
    repo, source, context = tmp_path / "repo", tmp_path / "source", tmp_path / "context"
    repo.mkdir()
    source.mkdir()
    (repo / "api").mkdir()
    (repo / "api/changed.py").write_text("unreviewed\n")
    command = Mock()
    command.out.side_effect = [SHA, "", "api/changed.py\0", "reviewed\n"]
    with pytest.raises(c.ProofError, match="SOURCE_BYTES_REJECTED"):
        runner.prepare_source(repo, source, context, command, SHA)
    assert not context.exists()


def test_existing_container_name_refused_without_mutation(tmp_path, monkeypatch):
    proof, command = phase(tmp_path, monkeypatch)
    command.out.return_value = "preexisting-container-id"
    with pytest.raises(c.ProofError, match="RESOURCE_CONFLICT"):
        proof.create("preexisting", [], "image", [], {}, None)
    assert proof.containers == {}
    assert all(call.args[0][1] == "ps" for call in command.out.call_args_list)
    proof.socket.rmdir()


def test_two_phases_never_reuse_credentials_or_socket_paths(tmp_path, monkeypatch):
    first, _ = phase(tmp_path, monkeypatch)
    # Reuse the already stubbed filesystem controls without wrapping mkdtemp twice.
    second = runner.Phase(
        "governance",
        tmp_path,
        tmp_path / "source",
        first.image,
        first.uid,
        first.gid,
        {"run_id": "123", "source_sha": SHA},
        Mock(report={}),
    )
    assert first.socket != second.socket and first.volume != second.volume
    assert first.passwords["app"] != second.passwords["app"]
    assert second.socket.name.startswith("paperclip-m5b.")
    first.socket.rmdir()
    second.socket.rmdir()


def test_private_umask_does_not_make_readonly_source_unreadable(tmp_path):
    repo, source, context = tmp_path / "repo", tmp_path / "source", tmp_path / "context"
    repo.mkdir()
    source.mkdir()
    paths = [f"api/module_{n}.py" for n in range(95)] + [
        "db/Dockerfile.proof",
        "requirements-api-dev.lock",
        "scripts/emit_api_build_metadata.py",
    ]
    for name in paths:
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("public synthetic source\n")

    def git(args):
        if args[-2:] == ["rev-parse", "HEAD"]:
            return SHA
        if args[-2:] == ["status", "--porcelain"]:
            return ""
        if args[-2:] == ["ls-files", "-z"]:
            return "\0".join(paths) + "\0"
        return (repo / args[-1].split(":", 1)[1]).read_text()

    command = Mock()
    command.out.side_effect = git
    previous = os.umask(0o077)
    try:
        runner.prepare_source(repo, source, context, command, SHA)
    finally:
        os.umask(previous)
    assert source.stat().st_mode & 0o777 == 0o755
    assert all(path.stat().st_mode & 0o777 == 0o755 for path in source.rglob("*") if path.is_dir())
    assert all(path.stat().st_mode & 0o444 == 0o444 for path in source.rglob("*") if path.is_file())


def test_existing_public_timestamp_parameter_is_not_rejected_as_unsafe_identity(tmp_path):
    path = tmp_path / "results.xml"
    xml_report(path, "operations")
    tree = ET.parse(path)
    ET.SubElement(
        tree.getroot(),
        "testcase",
        classname="api.tests.test_routes",
        name="test_order_rejects_invalid_business_input[requested_pickup_at-2030-01-02T10:00:00]",
    )
    tree.write(path)
    cases, counts = c.report_cases(path, "operations")
    assert len(cases) == 61 and sum(counts.values()) == 60


def test_source_reads_trust_only_exact_checkout_under_different_owner(tmp_path):
    repo, source, context = tmp_path / "repo", tmp_path / "source", tmp_path / "context"
    repo.mkdir()
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    paths = [f"api/module_{n}.py" for n in range(95)] + [
        "db/Dockerfile.proof",
        "requirements-api-dev.lock",
        "scripts/emit_api_build_metadata.py",
    ]
    for name in paths:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public synthetic source\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    private = tmp_path / "private"
    private.mkdir()
    command = runner.Executor(private, time.monotonic() + 30, {"commands": []})
    command.environment["GIT_TEST_ASSUME_DIFFERENT_OWNER"] = "1"
    code, output = command.run(["git", "-C", str(repo), "status", "--porcelain"], check=False)
    assert code == 128 and "dubious ownership" in output
    hashes = runner.prepare_source(repo, source, context, command, sha)
    assert len(hashes) == len(paths)
    assert (context / "Dockerfile").read_text() == "public synthetic source\n"
    # The exact-path override did not persist trust for this or another checkout.
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    for checkout in (repo, other):
        code, output = command.run(
            ["git", "-C", str(checkout), "status", "--porcelain"], check=False
        )
        assert code == 128 and "dubious ownership" in output
    (repo / paths[0]).write_text("unreviewed drift\n")
    with pytest.raises(c.ProofError, match="DIRTY_SOURCE_REJECTED"):
        runner.prepare_source(repo, source, context, command, sha)
