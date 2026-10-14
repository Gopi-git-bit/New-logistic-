"""Private injected-file metadata only; no key values or provider authority."""

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_staging_target_probe import probe
from test_staging_target_probe import target as target


@pytest.fixture
def credentials(target, monkeypatch, tmp_path):
    directory = tmp_path / "credentials"
    directory.mkdir(mode=0o700)
    key = directory / "provider-key"
    key.write_text("synthetic-sensitive-credential")
    key.chmod(0o400)
    monkeypatch.setattr(probe, "CREDENTIAL_DIRECTORY", directory)
    fstat = os.fstat

    def owned_by_target(fd):
        info = fstat(fd)
        return SimpleNamespace(
            st_mode=info.st_mode, st_uid=10001, st_nlink=info.st_nlink, st_size=info.st_size
        )

    monkeypatch.setattr(os, "fstat", owned_by_target)
    monkeypatch.setattr(os, "read", lambda *_args: pytest.fail("credential bytes read"))
    return directory, key


def test_private_injection_metadata_never_loads_values_or_approves_gates(credentials, capsys):
    assert probe.main(["--verify-staging-credential"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["status"] == "LOCAL_CREDENTIAL_CHECKS_PASSED"
    assert report["credential_injection"] == "PRIVATE_STAGING_FILE_OBSERVED"
    assert report["credential_contents_read"] is False and report["credential_loaded"] is False
    assert report["readiness"] == report["dedicated_key_scope"] == "UNVERIFIED"
    assert report["spending_cap"] == report["trusted_authorization"] == "UNVERIFIED"
    assert report["provider_calls"] == report["socket_attempts"] == 0
    assert "synthetic-sensitive-credential" not in output


@pytest.mark.parametrize("mode", [0o400, 0o600])
def test_private_file_modes_match_future_runner_contract(credentials, mode):
    credentials[1].chmod(mode)
    assert probe.credential_metadata()["observation"] == "PRIVATE_STAGING_FILE_OBSERVED"


@pytest.mark.parametrize("mode", [0o644, 0o666])
def test_group_or_world_readable_key_fails(credentials, mode):
    credentials[1].chmod(mode)
    assert probe.main(["--verify-staging-credential"]) == 1


@pytest.mark.parametrize("size", [0, 2049])
def test_empty_or_oversized_key_fails(credentials, size):
    credentials[1].chmod(0o600)
    credentials[1].write_bytes(b"x" * size)
    assert probe.main(["--verify-staging-credential"]) == 1


def test_foreign_owner_key_fails(credentials, monkeypatch):
    fstat = os.fstat

    def foreign_file(fd):
        info = fstat(fd)
        if stat.S_ISREG(info.st_mode):
            info.st_uid = 10002
        return info

    monkeypatch.setattr(os, "fstat", foreign_file)
    assert probe.main(["--verify-staging-credential"]) == 1


def test_foreign_owner_directory_fails(credentials, monkeypatch):
    fstat = os.fstat

    def foreign_directory(fd):
        info = fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            info.st_uid = 10002
        return info

    monkeypatch.setattr(os, "fstat", foreign_directory)
    assert probe.main(["--verify-staging-credential"]) == 1


@pytest.mark.parametrize("kind", ["missing", "symlink", "hardlink", "fifo"])
def test_missing_linked_or_nonregular_key_fails(credentials, kind):
    directory, key = credentials
    if kind == "hardlink":
        os.link(key, directory / "second-link")
    else:
        key.unlink()
        if kind == "symlink":
            key.symlink_to(directory / "missing")
        elif kind == "fifo":
            os.mkfifo(key, 0o600)
    assert probe.main(["--verify-staging-credential"]) == 1


@pytest.mark.parametrize("kind", ["unsafe_mode", "symlink"])
def test_unsafe_credential_directory_fails(credentials, monkeypatch, tmp_path, kind):
    directory = credentials[0]
    if kind == "unsafe_mode":
        directory.chmod(0o755)
    else:
        link = tmp_path / "linked-directory"
        link.symlink_to(directory, target_is_directory=True)
        monkeypatch.setattr(probe, "CREDENTIAL_DIRECTORY", link)
    assert probe.main(["--verify-staging-credential"]) == 1


@pytest.mark.parametrize("unsafe", ["root", "caps", "mount", "fixture"])
def test_unsafe_boundary_never_opens_injected_key(target, monkeypatch, unsafe):
    monkeypatch.setattr(probe, "credential_metadata", lambda: pytest.fail("unsafe key inspected"))
    if unsafe == "root":
        monkeypatch.setattr(probe.os, "geteuid", lambda: 0)
    elif unsafe == "caps":
        fields = probe.process_fields
        monkeypatch.setattr(
            probe, "process_fields", lambda text: {**fields(text), "effective_capabilities": "1"}
        )
    elif unsafe == "mount":
        monkeypatch.setattr(probe, "bundle_readonly", lambda _text: False)
    else:
        monkeypatch.setattr(probe, "fixture_access", lambda: "ACCESSIBLE")
    assert probe.main(["--verify-staging-credential"]) == 1


def test_credential_free_mode_never_opens_key(target, monkeypatch):
    monkeypatch.setattr(
        probe, "credential_metadata", lambda: pytest.fail("unrequested key inspected")
    )
    assert probe.main([]) == 0


def test_env_key_presence_does_not_supply_a_missing_injected_file(credentials, monkeypatch):
    credentials[1].unlink()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-sensitive-credential")
    monkeypatch.setenv("OMS_STAGING_API_KEY", "synthetic-sensitive-credential")
    assert probe.main(["--verify-staging-credential"]) == 1


def test_descriptors_close_and_metadata_errors_are_redacted(credentials, monkeypatch, capsys):
    closed = []
    close = os.close

    def record_close(fd):
        closed.append(fd)
        close(fd)

    def fail(_fd):
        raise OSError("synthetic-sensitive-credential")

    monkeypatch.setattr(os, "close", record_close)
    monkeypatch.setattr(os, "fstat", fail)
    assert probe.main(["--verify-staging-credential"]) == 1
    assert len(closed) == 1
    assert "synthetic-sensitive-credential" not in capsys.readouterr().out


def test_file_close_error_still_closes_directory_and_denies(credentials, monkeypatch, capsys):
    closed = []
    close = os.close

    def failing_first_close(fd):
        closed.append(fd)
        close(fd)
        if len(closed) == 1:
            raise OSError("synthetic-sensitive-credential")

    with monkeypatch.context() as patch:
        patch.setattr(os, "close", failing_first_close)
        assert probe.main(["--verify-staging-credential"]) == 1
    assert len(closed) == 2
    assert "synthetic-sensitive-credential" not in capsys.readouterr().out


def test_template_injects_only_staging_file_with_separate_marker():
    root = Path(__file__).resolve().parents[2]
    template = (root / "infra/m7-staging/zippy-oms-staging-credential-probe.service.in").read_text()
    assert "LoadCredential=provider-key:/etc/zippy/m7-staging/provider.key" in template
    assert "owner-credential-probe-enabled" in template
    assert "--verify-staging-credential" in template
    for forbidden in (
        "EnvironmentFile=",
        "SetCredential=",
        "OMS_STAGING_API_KEY=",
        "[Install]",
        "StateDirectory=",
    ):
        assert forbidden not in template
