"""One owner-authorized, bounded operations + governance proof on a disposable runner.

No provider/production secrets are read. This route reuses canonical SQL and test
assertions, not the legacy host-test execution mode. Every external command is
bounded and captured privately; the only exported object is an allowlisted report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from db.scripts.disposable_contract import (  # noqa: E402
    BASE_ENV,
    POSTGRES,
    PYTHON,
    ProofError,
    accept_runtime,
    admission,
    digest,
    inspect_container,
    read_private,
    require,
    sanitized,
    status_observation,
    utc,
)
from scripts.run_api_build import build_receipt  # noqa: E402


class Executor:
    def __init__(self, private: Path, deadline: float, report: dict[str, Any]):
        self.private, self.deadline, self.report = private, deadline, report
        self.environment = BASE_ENV | {
            "HOME": str(private),
            "DOCKER_CONFIG": str(private / "docker"),
            "DOCKER_HOST": "unix:///var/run/docker.sock",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        (private / "docker").mkdir(mode=0o700)

    def run(
        self,
        args: list[str],
        *,
        timeout: float = 20,
        data: str | None = None,
        check: bool = True,
        cleanup: bool = False,
    ) -> tuple[int, str]:
        remaining = timeout if cleanup else min(timeout, self.deadline - time.monotonic())
        require(remaining > 0, "PHASE_TIMEOUT")
        entry: dict[str, Any] = {
            "index": len(self.report["commands"]),
            "exit": "UNKNOWN",
            "stage": self.report.get("stage", "PREFLIGHT"),
            "operation": args[:2],
            "started_utc": datetime.now(UTC).isoformat(),
        }
        self.report["commands"].append(entry)
        # No argv/env/raw output in the public ledger. Output bytes are file-bounded.
        with tempfile.TemporaryFile(dir=self.private) as output:

            def bounded_output() -> None:
                resource.setrlimit(resource.RLIMIT_FSIZE, (20_971_520, 20_971_520))

            process = subprocess.Popen(
                args,
                env=self.environment,
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=output,
                start_new_session=True,
                preexec_fn=bounded_output,
            )
            try:
                process.communicate(None if data is None else data.encode(), timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=3)
                entry["exit"] = "TIMEOUT"
                entry["ended_utc"] = datetime.now(UTC).isoformat()
                raise ProofError("COMMAND_TIMEOUT") from None
            entry["exit"] = process.returncode
            entry["ended_utc"] = datetime.now(UTC).isoformat()
            output.seek(0)
            raw = output.read(20_971_521)
            require(len(raw) <= 20_971_520, "COMMAND_OUTPUT_TOO_LARGE")
        text = raw.decode("utf-8", errors="strict")
        require(not check or process.returncode == 0, "COMMAND_FAILED")
        return process.returncode, text

    def out(self, args: list[str], **kwargs: Any) -> str:
        return self.run(args, **kwargs)[1]


def environment_file(path: Path, values: dict[str, str]) -> Path:
    require(
        all(
            re.fullmatch(r"[A-Z][A-Z0-9_]*", k) and "\n" not in v and "\r" not in v
            for k, v in values.items()
        ),
        "ENVIRONMENT_REJECTED",
    )
    with path.open("x") as output:
        output.write("".join(k + "=" + v + "\n" for k, v in values.items()))
    path.chmod(0o600)
    return path


def prepare_source(
    repo: Path, source: Path, context: Path, run: Executor, sha: str
) -> dict[str, str]:
    # sudo changes identity: trust only this checkout for these read-only Git calls.
    # Never persist global trust or use safe.directory=*.
    git = ["git", "-c", "safe.directory=" + str(repo.resolve()), "-C", str(repo)]
    require(run.out(git + ["rev-parse", "HEAD"]).strip() == sha, "SOURCE_REJECTED")
    require(
        not run.out(git + ["status", "--porcelain"]).strip(),
        "DIRTY_SOURCE_REJECTED",
    )
    tracked = run.out(git + ["ls-files", "-z"]).split("\0")
    selected = [
        p for p in tracked if p.startswith(("api/", "db/")) and "/tests/__pycache__/" not in p
    ]
    selected += ["requirements-api-dev.lock", "scripts/emit_api_build_metadata.py"]
    hashes = {}
    for name in selected:
        require(
            ".." not in Path(name).parts and not Path(name).is_absolute(), "SOURCE_PATH_REJECTED"
        )
        original = repo / name
        info = original.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "SOURCE_PATH_REJECTED")
        expected = run.out(git + ["show", sha + ":" + name]).encode()
        data = original.read_bytes()
        require(data == expected, "SOURCE_BYTES_REJECTED")
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        target.write_bytes(data)
        target.chmod(0o755 if info.st_mode & 0o111 else 0o644)
        hashes[name] = digest(data)
    require(len(hashes) > 90, "SOURCE_INCOMPLETE")
    # The orchestrator uses umask 077; explicitly make public source traversable
    # inside its read-only bind for the unprivileged test UID.
    source.chmod(0o755)
    for directory in source.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o755)
    context.mkdir(mode=0o700)
    for original, name in [
        (source / "db/Dockerfile.proof", "Dockerfile"),
        (source / "requirements-api-dev.lock", "requirements-api-dev.lock"),
        (source / "scripts/emit_api_build_metadata.py", "emit_api_build_metadata.py"),
    ]:
        shutil.copyfile(original, context / name)
    return hashes


class Phase:
    def __init__(
        self,
        phase: str,
        private: Path,
        source: Path,
        image: str,
        uid: int,
        gid: int,
        identity: dict[str, Any],
        executor: Executor,
    ):
        self.phase, self.source, self.image = phase, source, image
        self.record: dict[str, Any] = {
            "phase": phase,
            "status": "NOT_VERIFIED",
            "cleanup": "UNKNOWN",
        }
        executor.report.setdefault("allocations", []).append(self.record)
        private = private / (phase + "-" + secrets.token_hex(8))
        private.mkdir(mode=0o700)
        self.private = private
        self.uid, self.gid, self.identity, self.run = uid, gid, identity, executor
        self.nonce = secrets.token_hex(12)
        self.label = identity["run_id"] + ":" + phase + ":" + self.nonce
        self.name = "zippy-proof-" + self.nonce
        self.volume = self.name + "-data"
        self.database = (
            "zippy_m2_disposable_" if phase == "operations" else "paperclip_m5_disposable_"
        ) + self.nonce
        self.login = "zippy_m2_runner" if phase == "operations" else "paperclip_m5_runner"
        self.app = "zippy_m2_app_login" if phase == "operations" else "paperclip_m5_app_login"
        self.passwords = {
            key: secrets.token_hex(32)
            for key in ("super", "migration", "app", "readonly", "envelope")
        }
        self.containers: dict[str, str] = {}
        self.volume_intent = False
        self.socket = Path(
            tempfile.mkdtemp(
                prefix="paperclip-m5b." if phase == "governance" else "zippy-m4-socket-"
            )
        )
        self.output = private / (phase + "-output")
        self.output.mkdir(mode=0o700)
        self.control = private / (phase + "-control")
        self.control.mkdir(mode=0o755)
        self.control.chmod(0o755)
        os.chown(self.socket, uid, gid)
        self.socket.chmod(0o700)
        self.record.update(
            {
                "phase": phase,
                "nonce": self.nonce,
                "status": "NOT_VERIFIED",
                "cleanup": "UNKNOWN",
                "resources": {
                    "label": self.label,
                    "containers": self.containers,
                    "volume": self.volume,
                    "socket": str(self.socket),
                    "socket_identity": [self.socket.stat().st_dev, self.socket.stat().st_ino],
                },
            }
        )
        self.common = {
            "PGHOST": "/var/run/postgresql",
            "PGDATABASE": self.database,
            "PGUSER": self.login,
            "PGPASSWORD": self.passwords["super"],
            "PAPERCLIP_ALLOW_DISPOSABLE_DB": "YES",
            "ZIPPY_ALLOW_DISPOSABLE_DB": "YES",
            "ZIPPY_CONFIRM_DISPOSABLE_DATABASE": self.database,
            "ZIPPY_DISPOSABLE_MARKER": self.nonce,
            "ZIPPY_EXPECTED_CONTAINER": self.name,
            "ZIPPY_EXPECTED_VOLUME": self.volume,
            "ZIPPY_EXPECTED_IMAGE_DIGEST": POSTGRES,
        }
        self.admin = environment_file(
            private / (phase + "-admin.env"),
            self.common
            | {
                "POSTGRES_USER": self.login,
                "POSTGRES_PASSWORD": self.passwords["super"],
                "POSTGRES_DB": self.database,
                "POSTGRES_INITDB_ARGS": "--auth-local=scram-sha-256 --auth-host=scram-sha-256",
                "ZIPPY_M2_MIGRATION_PASSWORD": self.passwords["migration"],
                "ZIPPY_M2_APP_PASSWORD": self.passwords["app"],
                "ZIPPY_M2_READONLY_PASSWORD": self.passwords["readonly"],
                "M5B_APP_PASSWORD": self.passwords["app"],
            },
        )
        self.migrator = environment_file(
            private / (phase + "-migrator.env"),
            self.common
            | {
                "PGUSER": "zippy_m2_migration_login",
                "PGPASSWORD": self.passwords["migration"],
                "PGOPTIONS": "-c role=zippy_migrator",
                "ZIPPY_CONFIRM_DISPOSABLE_DOWN": self.database,
            },
        )

    def inspect(self, name: str, *, cleanup: bool = False) -> dict[str, Any]:
        result = json.loads(self.run.out(["docker", "container", "inspect", name], cleanup=cleanup))
        require(len(result) == 1, "CONTAINER_IDENTITY_REJECTED")
        value: dict[str, Any] = result[0]
        return value

    def create(
        self,
        name: str,
        options: list[str],
        image: str,
        command: list[str],
        mounts: dict[str, tuple[str, bool]],
        test_uid: int | None,
    ) -> str:
        require(
            not self.run.out(["docker", "ps", "-aq", "--filter", "name=^/" + name + "$"]).strip(),
            "RESOURCE_CONFLICT",
        )
        self.containers[name] = ""
        args = [
            "docker",
            "create",
            "--name",
            name,
            "--label",
            "zippy.proof=" + self.label,
            "--network",
            "none",
            "--ipc",
            "private",
            "--security-opt",
            "no-new-privileges",
            "--log-driver",
            "none",
            *options,
            image,
            *command,
        ]
        cid = self.run.out(args).strip()
        require(re.fullmatch(r"[a-f0-9]{64}", cid), "CONTAINER_IDENTITY_REJECTED")
        self.containers[name] = cid
        inspect_container(
            self.inspect(name), image=image, label=self.label, mounts=mounts, test_uid=test_uid
        )
        self.run.out(["docker", "start", cid])
        return cid

    def wait(self, cid: str, timeout: float) -> None:
        status = self.run.out(["docker", "wait", cid], timeout=timeout).strip()
        require(status == "0", "CONTAINER_EXIT_REJECTED")

    def sql(self, script: str, *, migration: bool = False) -> str:
        return self.run.out(
            [
                "docker",
                "exec",
                "-i",
                "--env-file",
                str(self.migrator if migration else self.admin),
                self.containers[self.name],
                "bash",
                "-euo",
                "pipefail",
                "-s",
            ],
            data=script,
            timeout=120,
        )

    def test_container(
        self,
        name: str,
        environment: Path | None,
        command: list[str],
        extra: dict[str, tuple[str, bool]],
        uid: int,
        bounded_output: bool = False,
    ) -> str:
        options = [
            "--cpus",
            "2",
            "--memory",
            "2g",
            "--memory-swap",
            "2g",
            "--pids-limit",
            "256",
            "--user",
            f"{uid}:{uid}",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size=268435456,uid={uid},gid={uid}",
        ]
        if bounded_output:
            options += [
                "--tmpfs",
                f"/out:rw,noexec,nosuid,nodev,size=8388608,uid={uid},gid={uid},mode=0700",
            ]
        mounts = {"/workspace": (str(self.source), False)} | extra
        for target, (origin, writable) in mounts.items():
            options += [
                "--mount",
                "type=bind,source="
                + origin
                + ",target="
                + target
                + ("" if writable else ",readonly"),
            ]
        if environment is not None:
            options += ["--env-file", str(environment)]
        return self.create(name, options, self.image, command, mounts, uid)

    def socket_controls(self) -> None:
        # A reachable synthetic socket proves the unrelated UID's probe can connect.
        import socket

        endpoint = self.control / "control.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(endpoint))
            server.listen(1)
            endpoint.chmod(0o666)
            cid = self.test_container(
                self.name + "-positive",
                None,
                [
                    "python",
                    "-I",
                    "/workspace/db/scripts/disposable_runtime.py",
                    "accessible",
                    "/control/control.sock",
                ],
                {"/control": (str(self.control), False)},
                65534,
            )
            self.wait(cid, 8)
        cid = self.test_container(
            self.name + "-negative",
            None,
            [
                "python",
                "-I",
                "/workspace/db/scripts/disposable_runtime.py",
                "denied",
                str(self.socket / ".s.PGSQL.5432"),
            ],
            {str(self.socket): (str(self.socket), False)},
            65534,
        )
        self.wait(cid, 8)
        self.record["socket_controls"] = {
            "unrelated_uid": 65534,
            "accessible": "PASS",
            "private": "EACCES_OR_EPERM",
        }

    def start(self, pg_image: str) -> None:
        require(self.uid != 65534, "CONTROL_UID_COLLISION")
        require(
            not self.run.out(
                ["docker", "volume", "ls", "-q", "--filter", "name=^" + self.volume + "$"]
            ).strip(),
            "RESOURCE_CONFLICT",
        )
        self.volume_intent = True
        self.run.out(
            ["docker", "volume", "create", "--label", "zippy.proof=" + self.label, self.volume]
        )
        volume = json.loads(self.run.out(["docker", "volume", "inspect", self.volume]))[0]
        require(
            volume["Labels"].get("zippy.proof") == self.label and volume["Name"] == self.volume,
            "VOLUME_IDENTITY_REJECTED",
        )
        mounts = {
            "/workspace": (str(self.source), False),
            "/var/run/postgresql": (str(self.socket), True),
            "/var/lib/postgresql/data": (volume["Mountpoint"], True),
        }
        options = [
            "--cpus",
            "1",
            "--memory",
            "1g",
            "--memory-swap",
            "1g",
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "SETUID",
            "--cap-add",
            "SETGID",
            "--cap-add",
            "DAC_OVERRIDE",
            "--cap-add",
            "FOWNER",
            "--env-file",
            str(self.admin),
            "--mount",
            f"type=volume,source={self.volume},target=/var/lib/postgresql/data",
            "--mount",
            f"type=bind,source={self.socket},target=/var/run/postgresql",
            "--mount",
            f"type=bind,source={self.source},target=/workspace,readonly",
        ]
        self.create(
            self.name,
            options,
            pg_image,
            [
                "postgres",
                "-c",
                "listen_addresses=",
                "-c",
                "unix_socket_directories=/var/run/postgresql",
            ],
            mounts,
            None,
        )
        ready_until = time.monotonic() + 60
        while True:
            info = self.inspect(self.name)
            require(info["State"]["Running"], "POSTGRES_EXITED")
            if (
                self.run.run(
                    [
                        "docker",
                        "exec",
                        "--env-file",
                        str(self.admin),
                        self.containers[self.name],
                        "pg_isready",
                        "-q",
                    ],
                    check=False,
                )[0]
                == 0
            ):
                # The entrypoint uses a temporary server; PID 1 must now be postgres.
                if (
                    self.run.out(
                        ["docker", "exec", self.containers[self.name], "cat", "/proc/1/comm"]
                    ).strip()
                    == "postgres"
                ):
                    break
            require(time.monotonic() < ready_until, "POSTGRES_READINESS_TIMEOUT")
            time.sleep(0.25)
        self.socket.chmod(0o700)
        require(
            self.socket.stat().st_uid == self.uid
            and self.socket.stat().st_gid == self.gid
            and stat.S_IMODE(self.socket.stat().st_mode) & 0o777 == 0o700
            and (self.socket / ".s.PGSQL.5432").is_socket(),
            "SOCKET_IDENTITY_REJECTED",
        )
        auth = self.sql(
            "psql -X -tA -v ON_ERROR_STOP=1 -c \"SELECT current_setting('listen_addresses'), string_agg(DISTINCT auth_method, ',') FROM pg_hba_file_rules WHERE type='local'\""
        )
        require(auth.strip() == "|scram-sha-256", "POSTGRES_AUTH_REJECTED")
        pg_process = status_observation(
            self.run.out(["docker", "exec", self.containers[self.name], "cat", "/proc/1/status"]),
            self.uid,
        )
        version = self.sql('psql -X -tA -v ON_ERROR_STOP=1 -c "SHOW server_version_num"').strip()
        require(re.fullmatch(r"[0-9]{5,6}", version), "POSTGRES_VERSION_REJECTED")
        self.record["postgres"] = {
            "version_num": version,
            "uid": self.uid,
            "gid": self.gid,
            "process": pg_process,
            "image": pg_image,
            "network": "none",
            "tcp_listener": False,
            "local_auth": "scram-sha-256",
        }

    def fixtures(self) -> None:
        if self.phase == "operations":
            self.sql(
                f"psql -X -v ON_ERROR_STOP=1 -d postgres <<'SQL'\nALTER DATABASE {self.database} SET \"zippy.m2_marker\" TO '{self.nonce}';\nALTER DATABASE {self.database} SET \"zippy.m2_container\" TO '{self.name}';\nALTER DATABASE {self.database} SET \"zippy.m2_volume\" TO '{self.volume}';\nALTER DATABASE {self.database} SET \"zippy.m2_image_digest\" TO '{POSTGRES}';\nSQL\nbash /workspace/db/zippy/scripts/roles.sh bootstrap\n"
            )
            self.sql("bash /workspace/db/zippy/scripts/migrate.sh up\n", migration=True)
            self.sql(
                "psql -X -v ON_ERROR_STOP=1 -f /workspace/db/zippy/tests/setup_m3.sql\npsql -X -v ON_ERROR_STOP=1 -f /workspace/db/zippy/tests/setup_m4.sql\n"
            )
        else:
            self.sql(
                "cd /workspace\nbash db/paperclip/scripts/roles.sh bootstrap\nbash db/paperclip/scripts/migrate.sh up\npsql -X -v ON_ERROR_STOP=1 <<'SQL'\n\\getenv app_password M5B_APP_PASSWORD\nSELECT format('ALTER ROLE paperclip_m5_app_login PASSWORD %L', :'app_password') \\gexec\nSQL\n"
                + self.governance_checks()
                + "bash db/paperclip/scripts/migrate.sh down\nbash db/paperclip/scripts/migrate.sh up\npsql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/setup.sql\n"
            )

    @staticmethod
    def governance_checks() -> str:
        return "".join(
            "psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/" + name + ".sql\n"
            for name in ("setup", "verify", "verify_security", "verify_concurrency")
        )

    def test(self) -> None:
        url = f"host={self.socket} dbname={self.database} user={self.app} password={self.passwords['app']} connect_timeout=3"
        values = {
            "PATH": BASE_ENV["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "APP_ENV": "test",
            "AUTH_MODE": "test_jwt",
            "AUTH_JWT_SECRET": "m3-test-secret-that-is-at-least-32-bytes",
            "DATABASE_URL": url,
            "ZIPPY_PLATFORM_ID": "10000000-0000-0000-0000-000000000001",
            "M3_PRICING_POLICY_VERSION": "test-m3-v1",
            "M3_PRICING_CURRENCY": "INR",
            "M3_PRICING_BASE_AMOUNT": "100.00",
            "M3_PRICING_PER_KM": "12.50",
            "M3_PRICING_PER_KG": "0.75",
            "RAZORPAY_WEBHOOK_SECRET": "m4-synthetic-webhook-secret-32bytes!",
            "PAPERCLIP_DATABASE_URL": url
            if self.phase == "governance"
            else "host=/not-mounted dbname=unused user=unused",
            "PAPERCLIP_OWNER_SUBJECT": "paperclip-owner-test",
            "PAPERCLIP_EXECUTOR_SUBJECT": "paperclip-executor-test",
            "PAPERCLIP_POLICY_ID": "11111111-1111-1111-1111-111111111113",
            "PAPERCLIP_AGENT_BINDINGS_JSON": '{"paperclip-agent-test":"11111111-1111-1111-1111-111111111112"}',
            "PAPERCLIP_ENVELOPE_SIGNING_KEY": self.passwords["envelope"],
            "PAPERCLIP_ENVELOPE_TTL_SECONDS": "300",
            "DISPOSABLE_PHASE": self.phase,
            "DISPOSABLE_SOURCE": self.identity["source_sha"],
            "DISPOSABLE_RUN": self.identity["run_id"],
            "DISPOSABLE_NONCE": self.nonce,
        }
        if self.phase == "operations":
            values |= {"ZIPPY_M3_TEST_DATABASE_URL": url, "ZIPPY_M4_TEST_DATABASE_URL": url}
        else:
            values["PAPERCLIP_DISPOSABLE_PROOF"] = "YES"
        envfile = environment_file(self.private / (self.phase + "-test.env"), values)
        cid = self.test_container(
            self.name + "-tests",
            envfile,
            ["python", "-I", "-c", "import time; time.sleep(590)"],
            {str(self.socket): (str(self.socket), False)},
            self.uid,
            bounded_output=True,
        )
        self.run.out(
            [
                "docker",
                "exec",
                cid,
                "python",
                "-I",
                "/workspace/db/scripts/disposable_runtime.py",
                "test",
            ],
            timeout=550,
        )
        info = self.inspect(self.name + "-tests")
        require(info["State"]["Running"], "TEST_CONTAINER_EXITED")
        require(set(info["HostConfig"]["Tmpfs"]) == {"/tmp", "/out"}, "OUTPUT_TMPFS_REJECTED")
        inspect_container(
            info,
            image=self.image,
            label=self.label,
            mounts={
                "/workspace": (str(self.source), False),
                str(self.socket): (str(self.socket), False),
            },
            test_uid=self.uid,
        )
        # Copy only two bounded regular outputs while the owned tmpfs is still alive.
        for name in ("runtime.json", "results.xml"):
            target = self.output / name
            require(not target.exists(), "STALE_REPORT_REJECTED")
            self.run.out(["docker", "cp", cid + ":/out/" + name, str(target)], timeout=5)
            read_private(target, 4_194_304)
        result = json.loads(read_private(self.output / "runtime.json"))
        accept_runtime(
            result,
            self.output / "results.xml",
            phase=self.phase,
            source=self.identity["source_sha"],
            run_id=self.identity["run_id"],
            nonce=self.nonce,
            uid=self.uid,
        )
        host_namespaces = {n: os.stat("/proc/self/ns/" + n).st_ino for n in ("net", "mnt", "ipc")}
        require(
            all(result["namespaces"][n] != v for n, v in host_namespaces.items()),
            "NAMESPACE_REJECTED",
        )
        result["host_namespaces"] = host_namespaces
        result.pop("nonce")
        self.record["tests"] = result

    def rollback_reapply(self) -> None:
        if self.phase == "operations":
            self.sql("bash /workspace/db/zippy/scripts/migrate.sh down\n", migration=True)
            require(
                self.sql(
                    "psql -X -tA -v ON_ERROR_STOP=1 -c \"SELECT count(*) FROM pg_namespace WHERE nspname='zippy'\""
                ).strip()
                == "0",
                "ROLLBACK_REJECTED",
            )
            self.sql(
                "bash /workspace/db/zippy/scripts/migrate.sh up\nbash /workspace/db/zippy/scripts/migrate.sh verify\n",
                migration=True,
            )
            self.sql(
                "psql -X -v ON_ERROR_STOP=1 -f /workspace/db/zippy/tests/setup_m3.sql\npsql -X -v ON_ERROR_STOP=1 -f /workspace/db/zippy/tests/setup_m4.sql\n"
            )
            self.sql("bash /workspace/db/zippy/scripts/migrate.sh down\n", migration=True)
            self.sql(
                f"export ZIPPY_CONFIRM_DISPOSABLE_ROLE_TEARDOWN='{self.database}:{self.name}:{self.volume}'\nbash /workspace/db/zippy/scripts/roles.sh teardown\n"
            )
        else:
            self.sql("cd /workspace\nbash db/paperclip/scripts/migrate.sh down\n")
            require(
                self.sql(
                    "psql -X -tA -v ON_ERROR_STOP=1 -c \"SELECT count(*) FROM pg_namespace WHERE nspname='paperclip'\""
                ).strip()
                == "0",
                "ROLLBACK_REJECTED",
            )
            self.sql(
                "cd /workspace\nbash db/paperclip/scripts/migrate.sh up\n"
                + self.governance_checks()
            )
        self.record["rollback_reapply"] = "PASS"

    def cleanup(self) -> None:
        errors = []
        deadline = time.monotonic() + 45

        def output(args: list[str]) -> str:
            left = min(5, deadline - time.monotonic())
            require(left > 0, "CLEANUP_TIMEOUT")
            return self.run.out(args, timeout=left, cleanup=True)

        for name, cid in reversed(list(self.containers.items())):
            try:
                listed = output(["docker", "ps", "-aq", "--filter", "name=^/" + name + "$"]).strip()
                if not listed:
                    continue
                info = json.loads(output(["docker", "container", "inspect", name]))[0]
                require(
                    (not cid or info["Id"] == cid)
                    and info["Config"]["Labels"].get("zippy.proof") == self.label,
                    "CLEANUP_OWNERSHIP_REJECTED",
                )
                output(["docker", "rm", "-f", info["Id"]])
                require(
                    not output(["docker", "ps", "-aq", "--filter", "name=^/" + name + "$"]).strip(),
                    "CLEANUP_REJECTED",
                )
            except Exception:
                errors.append("CONTAINER_CLEANUP_UNKNOWN")
        if self.volume_intent:
            try:
                if output(
                    ["docker", "volume", "ls", "-q", "--filter", "name=^" + self.volume + "$"]
                ).strip():
                    volume = json.loads(output(["docker", "volume", "inspect", self.volume]))[0]
                    require(
                        volume["Labels"].get("zippy.proof") == self.label,
                        "CLEANUP_OWNERSHIP_REJECTED",
                    )
                    output(["docker", "volume", "rm", self.volume])
                    require(
                        not output(
                            [
                                "docker",
                                "volume",
                                "ls",
                                "-q",
                                "--filter",
                                "name=^" + self.volume + "$",
                            ]
                        ).strip(),
                        "CLEANUP_REJECTED",
                    )
            except Exception:
                errors.append("VOLUME_CLEANUP_UNKNOWN")
        if not errors:
            try:
                info = self.socket.lstat()
                require(
                    stat.S_ISDIR(info.st_mode)
                    and [info.st_dev, info.st_ino] == self.record["resources"]["socket_identity"],
                    "SOCKET_CLEANUP_OWNERSHIP_REJECTED",
                )
                shutil.rmtree(self.socket)
                require(not self.socket.exists(), "SOCKET_CLEANUP_REJECTED")
            except Exception:
                errors.append("SOCKET_CLEANUP_UNKNOWN")
        self.record["cleanup"] = "PASS" if not errors else "UNKNOWN"
        self.record["cleanup_errors"] = errors
        require(not errors, "CLEANUP_NOT_VERIFIED")


def run_proof(repo: Path, receipt: dict[str, Any], report: dict[str, Any], private: Path) -> None:
    identity = admission(receipt["identity"], receipt["identity"]["GITHUB_SHA"], receipt["expires"])
    require(
        os.geteuid() == 0 and os.environ.get("GITHUB_ACTIONS") == "true", "ROOT_OR_HOST_REJECTED"
    )
    require(
        0 <= (datetime.now(UTC) - utc(receipt["observed_utc"])).total_seconds() < 300,
        "STALE_ADMISSION_REJECTED",
    )
    report.update(
        source_sha=identity["GITHUB_SHA"],
        workflow_sha=identity["GITHUB_WORKFLOW_SHA"],
        run_id=identity["GITHUB_RUN_ID"],
        ci_run=receipt["ci_run"],
        ci_attempt=receipt["ci_attempt"],
    )
    run = Executor(private, time.monotonic() + 1620, report)
    require(shutil.disk_usage(private).free >= 6_442_450_944, "CAPACITY_REJECTED")
    available = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())[
        "MemAvailable"
    ]
    require(
        int(available.split()[0]) >= 3_145_728 and (os.cpu_count() or 0) >= 2, "CAPACITY_REJECTED"
    )
    require(not run.out(["ss", "-H", "-ltn", "sport = :5432"]).strip(), "HOST_PORT_CONFLICT")
    report["host_port_5432_before"] = "ABSENT"
    report["tools"] = {
        "docker": run.out(["docker", "--version"]).strip(),
        "compose": run.out(["docker", "compose", "version", "--short"]).strip(),
        "python": sys.version.split()[0],
    }
    source, context = private / "source", private / "build-context"
    source.mkdir(mode=0o755)
    report["source_inputs"] = prepare_source(repo, source, context, run, identity["GITHUB_SHA"])
    image_name = "zippy-disposable-proof:" + secrets.token_hex(12)
    image_created = False
    failures = []
    generated: list[str] = []
    try:
        report["stage"] = "SETUP"
        setup_deadline = time.monotonic() + 360
        for reference in (POSTGRES, PYTHON):
            run.out(
                ["docker", "pull", "--platform", "linux/amd64", reference],
                timeout=min(180, setup_deadline - time.monotonic()),
            )
        pg = json.loads(run.out(["docker", "image", "inspect", POSTGRES]))[0]
        require(
            any(
                x.endswith("@" + POSTGRES.split("@", 1)[1])
                and x.split("@")[0] in {"postgres", "docker.io/library/postgres"}
                for x in pg["RepoDigests"]
            )
            and pg["Architecture"] == "amd64"
            and pg["Os"] == "linux"
            and set(pg["Config"].get("Volumes") or {}) == {"/var/lib/postgresql/data"},
            "IMAGE_IDENTITY_REJECTED",
        )
        require(
            not run.out(
                ["docker", "image", "ls", "-q", "--filter", "reference=" + image_name]
            ).strip(),
            "IMAGE_CONFLICT",
        )
        iid = private / "proof-image.id"
        image_created = True
        build = run.out(
            [
                "docker",
                "build",
                "--pull=false",
                "--no-cache",
                "--progress=plain",
                "--platform",
                "linux/amd64",
                "--label",
                "zippy.proof=" + identity["GITHUB_RUN_ID"],
                "--iidfile",
                str(iid),
                "-t",
                image_name,
                str(context),
            ],
            timeout=min(240, setup_deadline - time.monotonic()),
        )
        image = iid.read_text().strip()
        require(re.fullmatch(r"sha256:[a-f0-9]{64}", image), "IMAGE_IDENTITY_REJECTED")
        report["proof_image"] = {
            "config_id": image,
            "base": PYTHON,
            "build_receipt": build_receipt(
                build, (context / "requirements-api-dev.lock").read_text()
            ),
        }
        # Bounded UID/GID control uses only owned private bind output.
        uid, gid = postgres_identity(pg["Id"], image, private, source, identity, run)
        for kind in ("operations", "governance"):
            report["stage"] = kind.upper()
            require(datetime.now(UTC) < utc(receipt["expires"]), "AUTHORIZATION_EXPIRED")
            phase = Phase(
                kind,
                private,
                source,
                image,
                uid,
                gid,
                {"run_id": identity["GITHUB_RUN_ID"], "source_sha": identity["GITHUB_SHA"]},
                run,
            )
            generated.extend(phase.passwords.values())
            report["phases"].append(phase.record)
            previous_deadline = run.deadline
            run.deadline = min(previous_deadline, time.monotonic() + 600)
            phase.record["started_utc"] = datetime.now(UTC).isoformat()
            try:
                phase.start(pg["Id"])
                phase.fixtures()
                phase.socket_controls()
                phase.test()
                phase.rollback_reapply()
                phase.record["status"] = "CHECKS_PASSED"
            finally:
                phase.record["ended_utc"] = datetime.now(UTC).isoformat()
                phase.cleanup()
                run.deadline = previous_deadline
        require(not run.out(["ss", "-H", "-ltn", "sport = :5432"]).strip(), "HOST_PORT_CHANGED")
        report["host_port_unchanged"] = True
        report["status"] = "DISPOSABLE_PROOF_PASSED"
    finally:
        if image_created:
            try:
                if run.out(
                    ["docker", "image", "ls", "-q", "--filter", "reference=" + image_name],
                    cleanup=True,
                ).strip():
                    actual = json.loads(
                        run.out(["docker", "image", "inspect", image_name], cleanup=True)
                    )[0]
                    require(
                        actual["Config"]["Labels"].get("zippy.proof") == identity["GITHUB_RUN_ID"],
                        "IMAGE_CLEANUP_OWNERSHIP_REJECTED",
                    )
                    run.out(["docker", "image", "rm", actual["Id"]], timeout=10, cleanup=True)
                    require(
                        not run.out(
                            ["docker", "image", "ls", "-q", "--filter", "reference=" + image_name],
                            cleanup=True,
                        ).strip(),
                        "IMAGE_CLEANUP_REJECTED",
                    )
            except Exception:
                failures.append("IMAGE_CLEANUP_UNKNOWN")
        report["image_cleanup"] = "UNKNOWN" if failures else "PASS"
        report["setup_cache"] = "EPHEMERAL_RUNNER_ONLY_NOT_PRUNED"
        require(not failures, "CLEANUP_NOT_VERIFIED")
        try:
            sanitized(report, generated)
        except Exception:
            report.clear()
            report.update(
                schema=1,
                status="NOT_VERIFIED",
                failure="SUMMARY_REJECTED",
                provider_calls=0,
                publication=False,
            )
            raise ProofError("SUMMARY_REJECTED") from None


def postgres_identity(
    pg_image: str,
    test_image: str,
    private: Path,
    source: Path,
    identity: dict[str, str],
    run: Executor,
) -> tuple[int, int]:
    phase = Phase(
        "identity",
        private,
        source,
        test_image,
        10001,
        10001,
        {"run_id": identity["GITHUB_RUN_ID"], "source_sha": identity["GITHUB_SHA"]},
        run,
    )
    directory = private / "postgres-identity"
    directory.mkdir(mode=0o700)
    os.chown(directory, 65534, 65534)
    data_dir = directory / "data"
    data_dir.mkdir(mode=0o700)
    os.chown(data_dir, 65534, 65534)
    run.report.setdefault("controls", []).append(phase.record)
    try:
        cid = phase.create(
            phase.name + "-identity",
            [
                "--cpus",
                "1",
                "--memory",
                "128m",
                "--pids-limit",
                "16",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--user",
                "65534:65534",
                "--mount",
                f"type=bind,source={directory},target=/identity",
                "--mount",
                f"type=bind,source={data_dir},target=/var/lib/postgresql/data",
            ],
            pg_image,
            ["sh", "-c", "id -u postgres > /identity/uid; id -g postgres > /identity/gid"],
            {
                "/identity": (str(directory), True),
                "/var/lib/postgresql/data": (str(data_dir), True),
            },
            65534,
        )
        phase.wait(cid, 5)
        values = [(directory / name).read_text().strip() for name in ("uid", "gid")]
        require(all(re.fullmatch(r"[1-9][0-9]{0,5}", v) for v in values), "POSTGRES_UID_REJECTED")
        return int(values[0]), int(values[1])
    finally:
        phase.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {
        "schema": 1,
        "status": "NOT_VERIFIED",
        "commands": [],
        "phases": [],
        "provider_calls": 0,
        "publication": False,
        "started_utc": datetime.now(UTC).isoformat(),
    }
    try:
        os.umask(0o077)
        require(
            args.report.parent.resolve() == args.admission.parent.resolve()
            and not args.report.exists(),
            "REPORT_PATH_REJECTED",
        )
        receipt = json.loads(read_private(args.admission))
        private = Path(tempfile.mkdtemp(prefix="zippy-disposable-", dir=args.report.parent))
        try:
            run_proof(args.repo.resolve(), receipt, report, private)
        finally:
            # Retain private paths if a possibly live container could still use them.
            records = report.get("allocations", [])
            if all(record.get("cleanup") == "PASS" for record in records):
                shutil.rmtree(private)
                report["private_cleanup"] = "PASS"
            else:
                report["private_cleanup"] = "UNKNOWN_RETAINED_ON_DISPOSABLE_RUNNER"

    except Exception as error:
        report["status"] = "NOT_VERIFIED"
        report["failure"] = (
            str(error) if isinstance(error, ProofError) else "EXECUTION_NOT_VERIFIED"
        )
    report["ended_utc"] = datetime.now(UTC).isoformat()
    try:
        with args.report.open("xb") as output:
            output.write(sanitized(report, []))
        args.report.chmod(0o644)  # Sanitized public artifact; raw files are never exported.
    except Exception:
        print("DISPOSABLE_REPORT_NOT_VERIFIED")
        return 1
    print(report["status"])
    return 0 if report["status"] == "DISPOSABLE_PROOF_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
