"""Secret-free build admission, evidence and cleanup regressions; no Docker calls."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = script("run_api_build")
emitter = script("emit_api_build_metadata")
SOURCE = "a" * 40
IMAGE = "sha256:" + "b" * 64
LOCK = "example==1.0 --hash=sha256:" + "c" * 64 + "\n"


def identity():
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": runner.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ACTOR": "Gopi-git-bit",
        "GITHUB_ACTOR_ID": "200721521",
        "GITHUB_TRIGGERING_ACTOR": "Gopi-git-bit",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": SOURCE,
        "GITHUB_WORKFLOW_SHA": SOURCE,
        "GITHUB_WORKFLOW_REF": runner.WORKFLOW,
        "GITHUB_RUN_ID": "123456",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
    }


def pip_report():
    return {
        "version": "1",
        "pip_version": "26.2.1",
        "install": [
            {
                "metadata": {"name": "Example", "version": "1.0", "description": "DO_NOT_LOG"},
                "download_info": {
                    "url": "https://synthetic-user:DO_NOT_LOG@files.pythonhosted.org/example.whl?token=DO_NOT_LOG#DO_NOT_LOG",
                    "archive_info": {"hashes": {"sha256": "c" * 64}},
                },
            }
        ],
        "environment": {"private": "DO_NOT_LOG"},
    }


def receipt():
    return emitter.collect(pip_report(), "libpq5\t17.0-1\n", {"ID": "debian", "VERSION_ID": "13"})


class FakeBuildCommands:
    def __init__(self):
        self.calls = []
        self.preexisting = False
        self.fail_build = False
        self.bad_receipt = False
        self.timeout = False
        self.cleanup_failure = False
        self.dirty = False
        self.remote_builder = False
        self.wrong_platform = False

    def __call__(self, args, env, timeout):
        self.calls.append((args, env.copy(), timeout))
        if args[0] == "git":
            return SOURCE if args[-1] == "HEAD" else (" M Dockerfile.api" if self.dirty else "")
        if any("prepare_api_build_context.py" in arg for arg in args):
            context = Path(args[args.index("--output") + 1])
            context.mkdir()
            (context / "Dockerfile.api").write_text("FROM " + runner.BASE_IMAGE + "\n")
            (context / "requirements-api.lock").write_text(LOCK)
            return json.dumps({"status": "CONTEXT_PREPARED", "source_sha": SOURCE})
        if any("validate_api_staging_config.py" in arg for arg in args):
            return json.dumps({"status": "OFFLINE_CONTRACT_VALIDATED"})
        if args[:3] == ["docker", "buildx", "inspect"]:
            return (
                "Driver: remote\nEndpoint: tcp://synthetic.invalid\n"
                if self.remote_builder
                else "Driver: docker\nEndpoint: default\n"
            )
        if args[:3] == ["docker", "buildx", "imagetools"]:
            return json.dumps(
                {
                    "manifests": [
                        {
                            "digest": "sha256:" + "d" * 64,
                            "platform": {
                                "os": "linux",
                                "architecture": "arm64" if self.wrong_platform else "amd64",
                            },
                        }
                    ]
                }
            )
        if args[:3] == ["docker", "image", "ls"]:
            return IMAGE if self.preexisting else ""
        if args[:3] == ["docker", "buildx", "build"]:
            Path(args[args.index("--iidfile") + 1]).write_text(IMAGE)
            Path(args[args.index("--metadata-file") + 1]).write_text(
                json.dumps({"containerimage.config.digest": IMAGE})
            )
            if self.fail_build:
                raise subprocess.CalledProcessError(23, args, output="DO_NOT_LOG")
            if self.timeout:
                raise subprocess.TimeoutExpired(args, timeout, output="DO_NOT_LOG")
            data = receipt()
            if self.bad_receipt:
                data["pip_downloads"][0]["sha256"] = "e" * 64
            return "#8 3.141 " + emitter.MARKER + json.dumps(data) + "\n"
        if args[:3] == ["docker", "image", "inspect"]:
            return json.dumps(
                {
                    "Id": IMAGE,
                    "Os": "linux",
                    "Architecture": "amd64",
                    "Config": {"User": "10001:10001", "Env": ["DO_NOT_LOG"]},
                }
            )
        if args[:3] == ["docker", "image", "rm"]:
            if self.cleanup_failure:
                raise subprocess.CalledProcessError(24, args, output="DO_NOT_LOG")
            return ""
        return "1.2.3"


class TestBuildAdmission(unittest.TestCase):
    def test_every_identity_mismatch_and_missing_value_denied_before_commands(self):
        for key in identity():
            for value in (None, "untrusted"):
                with self.subTest(key=key, value=value):
                    env = identity()
                    if value is None:
                        del env[key]
                    else:
                        env[key] = value
                    fake = FakeBuildCommands()
                    with self.assertRaises(runner.BuildError):
                        runner.build(ROOT, SOURCE, env, {}, fake)
                    self.assertEqual(fake.calls, [])

    def test_named_sha_and_rerun_are_denied(self):
        for source in ("main", "f" * 40, SOURCE.upper(), "$(synthetic)"):
            with self.subTest(source=source), self.assertRaises(runner.BuildError):
                runner.admit(identity(), source)
        env = identity() | {"GITHUB_RUN_ATTEMPT": "2"}
        with self.assertRaises(runner.BuildError):
            runner.admit(env, SOURCE)


class TestDependencyReceipts(unittest.TestCase):
    def test_only_allowlisted_package_metadata_retained(self):
        data = receipt()
        self.assertNotIn("DO_NOT_LOG", json.dumps(data))
        self.assertEqual(
            data["pip_downloads"][0]["url"], "https://files.pythonhosted.org/example.whl"
        )
        self.assertEqual(data["pip_downloads"][0]["name"], "example")
        runner.downloads_match(data, LOCK)

    def test_malformed_missing_and_duplicate_receipts_fail(self):
        for mutation in ("version", "hash", "duplicate", "missing", "url"):
            with self.subTest(mutation=mutation):
                data = pip_report()
                if mutation == "version":
                    data["version"] = "2"
                elif mutation == "hash":
                    data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = (
                        "invalid"
                    )
                elif mutation == "duplicate":
                    data["install"].append(copy.deepcopy(data["install"][0]))
                elif mutation == "missing":
                    data["install"] = []
                else:
                    data["install"][0]["download_info"]["url"] = "file:///private/synthetic"
                with self.assertRaises(ValueError):
                    emitter.pip_receipt(data)

    def test_build_output_must_have_one_receipt_and_match_lock(self):
        line = "#3 1.234 " + emitter.MARKER + json.dumps(receipt()) + "\n"
        self.assertEqual(runner.build_receipt(line, LOCK)["schema"], 1)
        for log in ("", line * 2, "#3 RUN echo " + emitter.MARKER + json.dumps(receipt())):
            with self.subTest(log=log), self.assertRaises(ValueError):
                runner.build_receipt(log, LOCK)
        for lock in (
            LOCK.replace("example==1.0", "example==2.0"),
            LOCK.replace("c" * 64, "d" * 64),
            LOCK + "extra==1 --hash=sha256:" + "a" * 64,
        ):
            with self.subTest(lock=lock), self.assertRaises(ValueError):
                runner.build_receipt(line, lock)
        data = receipt() | {"unexpected": "DO_NOT_LOG"}
        with self.assertRaises(ValueError):
            runner.build_receipt("#3 1.234 " + emitter.MARKER + json.dumps(data), LOCK)


class TestBoundedBuild(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.env = identity() | {
            "RUNNER_TEMP": self.temporary.name,
            "DEEPSEEK_API_KEY": "DO_NOT_LOG",
            "DOCKER_HOST": "tcp://untrusted.invalid",
            "GITHUB_TOKEN": "DO_NOT_LOG",
        }

    def test_success_keeps_image_unpublished_and_only_removes_new_image(self):
        fake = FakeBuildCommands()
        report = {}
        runner.build(ROOT, SOURCE, self.env, report, fake)
        self.assertEqual(report["status"], "BUILD_ONLY_PASSED")
        self.assertTrue(report["cleanup"]["new_local_image_removed"])
        self.assertNotIn("DO_NOT_LOG", json.dumps(report))
        commands = [call[0] for call in fake.calls]
        build = next(args for args in commands if args[:3] == ["docker", "buildx", "build"])
        for flag in ("--load", "--pull", "--no-cache", "--iidfile", "--metadata-file"):
            self.assertIn(flag, build)
        for args, env, timeout in fake.calls:
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 600)
            self.assertNotIn("DO_NOT_LOG", json.dumps(env))
            self.assertEqual(env["DOCKER_HOST"], "unix:///var/run/docker.sock")
            for forbidden in (
                "push",
                "login",
                "run",
                "up",
                "--secret",
                "--ssh",
                "--cache-to",
                "--build-arg",
            ):
                self.assertNotIn(forbidden, args)
        self.assertEqual(commands[-1], ["docker", "image", "rm", IMAGE])
        self.assertEqual(list(Path(self.temporary.name).iterdir()), [])

    def test_preexisting_image_is_preserved(self):
        fake = FakeBuildCommands()
        fake.preexisting = True
        report = {}
        runner.build(ROOT, SOURCE, self.env, report, fake)
        self.assertTrue(report["cleanup"]["preexisting_image_preserved"])
        self.assertFalse(any(args[:3] == ["docker", "image", "rm"] for args, _, _ in fake.calls))

    def test_failure_timeout_and_bad_receipt_never_pass_and_cleanup_owned_image(self):
        for failure in ("fail_build", "timeout", "bad_receipt", "cleanup_failure"):
            with self.subTest(failure=failure):
                fake = FakeBuildCommands()
                setattr(fake, failure, True)
                report = {}
                with self.assertRaises(
                    (runner.BuildError, subprocess.TimeoutExpired, subprocess.CalledProcessError)
                ):
                    runner.build(ROOT, SOURCE, self.env, report, fake)
                self.assertNotEqual(report.get("status"), "BUILD_ONLY_PASSED")
                self.assertEqual(fake.calls[-1][0], ["docker", "image", "rm", IMAGE])
                if failure == "fail_build":
                    self.assertEqual(report["command_results"][-1]["exit_status"], 23)
                elif failure == "timeout":
                    self.assertEqual(report["command_results"][-1]["exit_status"], "TIMEOUT")
                elif failure == "cleanup_failure":
                    self.assertEqual(report["cleanup"]["image_remove_exit_status"], 24)

    def test_dirty_source_remote_builder_and_wrong_base_platform_stop_before_build(self):
        for failure in ("dirty", "remote_builder", "wrong_platform"):
            with self.subTest(failure=failure):
                fake = FakeBuildCommands()
                setattr(fake, failure, True)
                with self.assertRaises(runner.BuildError):
                    runner.build(ROOT, SOURCE, self.env, {}, fake)
                self.assertFalse(
                    any(args[:3] == ["docker", "buildx", "build"] for args, _, _ in fake.calls)
                )

    def test_command_failure_does_not_attach_raw_output(self):
        result = subprocess.CompletedProcess(["synthetic"], 9, "DO_NOT_LOG", "DO_NOT_LOG")
        with patch.object(runner.subprocess, "run", return_value=result):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                runner.execute(["synthetic"], {}, 1)
        self.assertIsNone(caught.exception.output)
        self.assertNotIn("DO_NOT_LOG", str(caught.exception))

    def test_cli_denial_writes_private_redacted_report(self):
        report = Path(self.temporary.name) / "report.json"
        with patch.dict(os.environ, {"GITHUB_ACTOR": "DO_NOT_LOG"}, clear=True):
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ROOT / "scripts/run_api_build.py"),
                    "--repo-root",
                    str(ROOT),
                    "--source-sha",
                    SOURCE,
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        self.assertEqual(result.returncode, 1)
        data = report.read_text()
        self.assertNotIn("DO_NOT_LOG", data + result.stdout + result.stderr)
        self.assertEqual(json.loads(data)["stage"], "ADMISSION")
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_workflow_is_manual_main_owner_bound_read_only_and_not_dispatched_by_ci(self):
        text = (ROOT / ".github/workflows/api-build-only.yml").read_text()
        workflow = yaml.load(text, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"build-only"})
        job = workflow["jobs"]["build-only"]
        self.assertEqual(job["runs-on"], "ubuntu-24.04")
        self.assertEqual(job["timeout-minutes"], "15")
        for guard in (
            "workflow_dispatch",
            "Gopi-git-bit/New-logistic-",
            "refs/heads/main",
            "200721521",
            "github.triggering_actor",
            "github.run_attempt == 1",
            "github.sha == inputs.source_sha",
            "github.workflow_sha == github.sha",
        ):
            self.assertIn(guard, job["if"])
        self.assertNotIn("environment", job)
        checkout = job["steps"][0]
        self.assertEqual(
            checkout["uses"], "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
        )
        self.assertEqual(checkout["with"]["persist-credentials"], "false")
        self.assertEqual(checkout["with"]["ref"], "${{ inputs.source_sha }}")
        for step in job["steps"]:
            self.assertNotIn("${{", step.get("run", ""))
        for forbidden in (
            "secrets.",
            "Production",
            "upload-artifact",
            "docker push",
            "workflow_call",
            "pull_request_target",
        ):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("api-build-only.yml", (ROOT / ".github/workflows/ci.yml").read_text())
        dockerfile = (ROOT / "Dockerfile.api").read_text()
        for flag in (
            "--isolated",
            "--only-binary=:all:",
            "--force-reinstall",
            "--require-hashes",
            "--report",
            "--index-url https://pypi.org/simple",
        ):
            self.assertIn(flag, dockerfile)


if __name__ == "__main__":
    unittest.main()
