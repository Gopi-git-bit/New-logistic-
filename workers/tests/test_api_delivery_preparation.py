"""Offline regressions for committed build inputs and validation-only staging."""

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


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


context = load_script("prepare_api_build_context")
validator = load_script("validate_api_staging_config")
MANIFEST = ROOT / "infra/staging/api-validation.compose.json"


class TestCommittedBuildContext(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.command("init", "-q")
        self.write("Dockerfile.api", "FROM scratch\nCOPY api/ /api/\n")
        self.write("requirements-api.lock", "example==1.0 --hash=sha256:" + "a" * 64 + "\n")
        self.write("api/__init__.py", "")
        self.write("api/config.py", "VALUE = 'committed'\n")
        self.write("api/main.py", "VALUE = 'synthetic'\n")
        self.write("api/tests/test_example.py", "TEST = True\n")
        self.write("docs/not-an-input.md", "irrelevant\n")
        self.sha = self.commit()

    def command(self, *args):
        return (
            subprocess.run(
                ["git", "-C", str(self.repo), "-c", "commit.gpgsign=false", *args],
                env={
                    "PATH": os.defpath,
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                },
                check=True,
                capture_output=True,
                timeout=5,
            )
            .stdout.decode()
            .strip()
        )

    def write(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self):
        self.command("add", ".")
        self.command(
            "-c",
            "user.name=Synthetic Test",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-qm",
            "synthetic fixture",
        )
        return self.command("rev-parse", "HEAD")

    def test_exports_only_committed_inputs_and_preserves_dirty_files(self):
        self.write("api/config.py", "VALUE = 'dirty local value'\n")
        self.write("api/local_secret.py", "NOT_FOR_IMAGE = 'synthetic local sentinel'\n")
        self.write(".env", "DO_NOT_COPY=synthetic\n")
        output = self.root / "context"
        report = context.prepare_context(self.repo, self.sha, output)
        self.assertEqual((output / "api/config.py").read_text(), "VALUE = 'committed'\n")
        self.assertEqual(len(report["files"]), 5)
        self.assertEqual(report["source_sha"], self.sha)
        self.assertEqual(report["image_build"], "NOT_RUN")
        self.assertFalse((output / "api/local_secret.py").exists())
        self.assertFalse((output / ".env").exists())
        self.assertFalse((output / ".git").exists())
        self.assertFalse((output / "api/tests").exists())
        self.assertIn("dirty local value", (self.repo / "api/config.py").read_text())
        self.assertNotIn("synthetic local sentinel", json.dumps(report))

    def test_context_identity_is_independent_of_destination(self):
        a = context.prepare_context(self.repo, self.sha, self.root / "a")
        b = context.prepare_context(self.repo, self.sha, self.root / "b")
        self.assertEqual(a, b)

    def test_source_mismatch_and_non_commit_selector_refused_before_writing(self):
        for sha in ("main", "f" * 40):
            with self.subTest(sha=sha):
                with self.assertRaises(context.ContextError):
                    context.prepare_context(self.repo, sha, self.root / "context")
                self.assertFalse((self.root / "context").exists())

    def test_existing_destination_is_never_overwritten(self):
        output = self.root / "context"
        output.mkdir()
        (output / "sentinel").write_text("keep")
        with self.assertRaises(context.ContextError):
            context.prepare_context(self.repo, self.sha, output)
        self.assertEqual((output / "sentinel").read_text(), "keep")

    def test_output_inside_checkout_is_refused(self):
        with self.assertRaisesRegex(context.ContextError, "OUTSIDE_REPOSITORY"):
            context.prepare_context(self.repo, self.sha, self.repo / "new-context")
        self.assertFalse((self.repo / "new-context").exists())

    def test_tracked_secret_and_symlink_are_refused(self):
        self.write("api/provider.key", "synthetic")
        sha = self.commit()
        with self.assertRaisesRegex(context.ContextError, "UNSUPPORTED"):
            context.prepare_context(self.repo, sha, self.root / "context")
        (self.repo / "api/provider.key").unlink()
        (self.repo / "api/link.py").symlink_to("config.py")
        sha = self.commit()
        with self.assertRaisesRegex(context.ContextError, "NON_REGULAR"):
            context.prepare_context(self.repo, sha, self.root / "context")
        self.assertFalse((self.root / "context").exists())

    def test_missing_required_runtime_file_refused(self):
        (self.repo / "api/main.py").unlink()
        sha = self.commit()
        with self.assertRaisesRegex(context.ContextError, "REQUIRED_BUILD_INPUT"):
            context.prepare_context(self.repo, sha, self.root / "context")

    def test_bad_lock_prevents_any_context_creation(self):
        for lock in (
            "example==1.0\n",
            "-r==foo --hash=sha256:" + "a" * 64 + "\n",
            "--extra-index-url==evil --hash=sha256:" + "a" * 64 + "\n",
            "example==1.0 --hash=sha256:"
            + "a" * 64
            + "\n# comment \\\n--extra-index-url https://synthetic.invalid\n",
        ):
            with self.subTest(lock=lock):
                self.write("requirements-api.lock", lock)
                sha = self.commit()
                with self.assertRaisesRegex(context.ContextError, "UNHASHED_LOCK"):
                    context.prepare_context(self.repo, sha, self.root / "context")
                self.assertFalse((self.root / "context").exists())

    def test_distribution_names_have_alphanumeric_edges(self):
        digest = " --hash=sha256:" + "a" * 64
        for name in (
            "-r",
            "-e",
            "--extra-index-url",
            "--no-index",
            ".package",
            "_package",
            "package-",
            "package.",
            "package_",
        ):
            with self.subTest(name=name), self.assertRaises(context.ContextError):
                context.validate_lock((name + "==1.0" + digest).encode())
        for name in ("a", "Z", "2", "Package.Name_2-extra"):
            with self.subTest(name=name):
                self.assertEqual(context.validate_lock((name + "==1.0" + digest).encode()), 1)
        with self.assertRaisesRegex(context.ContextError, "DUPLICATE"):
            context.validate_lock(
                ("Package.Name==1.0" + digest + "\npackage-name==1.0" + digest).encode()
            )

    def test_comment_continuation_cannot_hide_pip_option(self):
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=newline), self.assertRaises(context.ContextError):
                content = (
                    "example==1.0 --hash=sha256:"
                    + "a" * 64
                    + newline
                    + "# comment \\"
                    + newline
                    + "--extra-index-url https://synthetic.invalid"
                    + newline
                )
                context.validate_lock(content.encode())

    def test_lock_rejects_unhashed_urls_options_and_duplicates(self):
        for raw in (
            "",
            "example==1.0",
            "-r other.txt",
            "--index-url https://example.invalid",
            "example @ https://example.invalid/package.whl",
            "example==1.0 --hash=sha256:bad",
            ("example==1.0 --hash=sha256:" + "a" * 64 + "\n") * 2,
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(context.ContextError):
                    context.validate_lock(raw.encode())
        self.assertEqual(context.validate_lock((ROOT / "requirements-api.lock").read_bytes()), 17)


class TestOfflineStagingContract(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "manifest.json"

    def validate(self, manifest):
        self.path.write_text(json.dumps(manifest))
        return validator.validate_contract(self.path, ROOT)

    def test_real_config_validates_without_app_import_socket_or_ambient_credentials(self):
        poison = {"DEEPSEEK_API_KEY": "SYNTHETIC_DO_NOT_LOG", "APP_ENV": "production"}
        with (
            patch.dict(os.environ, poison),
            patch("socket.socket", side_effect=AssertionError("socket forbidden")),
            patch.dict(sys.modules, {"api.main": None, "psycopg": None, "fastapi": None}),
        ):
            result = self.validate(self.manifest)
            self.assertEqual(os.environ["APP_ENV"], "production")
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], poison["DEEPSEEK_API_KEY"])
        self.assertEqual(result["status"], "OFFLINE_CONTRACT_VALIDATED")
        self.assertEqual(result["provider_execution"], "DENIED")
        self.assertNotIn("SYNTHETIC_DO_NOT_LOG", json.dumps(result))

    def test_every_missing_environment_name_is_rejected(self):
        for name in validator.ENV_NAMES:
            manifest = copy.deepcopy(self.manifest)
            del manifest["services"]["api-validation"]["environment"][name]
            with self.subTest(name=name), self.assertRaises(validator.ContractError):
                self.validate(manifest)

    def test_config_validation_does_not_create_bytecode(self):
        repo = Path(self.temporary.name) / "repo"
        (repo / "api").mkdir(parents=True)
        (repo / "api/config.py").write_bytes((ROOT / "api/config.py").read_bytes())
        self.path.write_text(json.dumps(self.manifest))
        result = validator.validate_contract(self.path, repo)
        self.assertEqual(result["status"], "OFFLINE_CONTRACT_VALIDATED")
        self.assertFalse((repo / "api/__pycache__").exists())

    def test_runtime_wiring_and_extra_services_are_rejected(self):
        for key, value in (
            ("ports", ["8000:8000"]),
            ("volumes", ["/var/run/docker.sock:/var/run/docker.sock"]),
            ("env_file", [".env"]),
            ("privileged", True),
            ("build", "."),
            ("network_mode", "host"),
            ("user", "0"),
            ("read_only", False),
            ("read_only", 1),
            ("entrypoint", ["uvicorn", "api.main:app"]),
        ):
            manifest = copy.deepcopy(self.manifest)
            manifest["services"]["api-validation"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(validator.ContractError):
                self.validate(manifest)
        self.manifest["services"]["database"] = {"image": "postgres"}
        with self.assertRaises(validator.ContractError):
            self.validate(self.manifest)

    def test_live_or_malformed_settings_are_rejected_without_environment_leak(self):
        for name, value in (
            ("APP_ENV", "production"),
            ("AUTH_MODE", "disabled"),
            ("DATABASE_URL", "postgresql://synthetic.invalid/live"),
            ("AUTH_JWT_SECRET", "SYNTHETIC_VALUE_MUST_NOT_APPEAR_IN_OUTPUT"),
            ("M3_PRICING_BASE_AMOUNT", "1"),
            ("M3_PRICING_POLICY_VERSION", "production"),
            ("PAPERCLIP_ENVELOPE_TTL_SECONDS", "301"),
            ("ZIPPY_PLATFORM_ID", "invalid"),
            ("PAPERCLIP_OWNER_SUBJECT", "synthetic-executor"),
            ("PAPERCLIP_AGENT_BINDINGS_JSON", "{}"),
            ("PAPERCLIP_AGENT_BINDINGS_JSON", '{"synthetic-agent":"invalid"}'),
            ("M3_PRICING_CURRENCY", "${REAL_ENVIRONMENT_VALUE}"),
            ("DEEPSEEK_STAGING_API_KEY", "synthetic-unexpected-provider-key"),
        ):
            manifest = copy.deepcopy(self.manifest)
            manifest["services"]["api-validation"]["environment"][name] = value
            with patch.dict(os.environ, {"APP_ENV": "outside-sentinel"}):
                with (
                    self.subTest(name=name, value=value),
                    self.assertRaises(validator.ContractError),
                ):
                    self.validate(manifest)
                self.assertEqual(os.environ["APP_ENV"], "outside-sentinel")

    def test_duplicate_json_and_cli_redaction_fail_closed(self):
        self.path.write_text('{"name":"x","name":"y"}')
        with self.assertRaises(validator.ContractError):
            validator.validate_contract(self.path, ROOT)
        sentinel = "SYNTHETIC_VALUE_MUST_NOT_APPEAR_IN_OUTPUT"
        self.manifest["services"]["api-validation"]["environment"]["AUTH_JWT_SECRET"] = sentinel
        self.path.write_text(json.dumps(self.manifest))
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(ROOT / "scripts/validate_api_staging_config.py"),
                "--repo-root",
                str(ROOT),
                "--manifest",
                str(self.path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(sentinel, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "OFFLINE_CONTRACT_NOT_VERIFIED")

    def test_ci_consumes_hash_lock_and_only_validates_staging(self):
        workflow = yaml.load(
            (ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
        )
        api_steps = workflow["jobs"]["api-tests"]["steps"]
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        for name in ("api-tests", "compose-config"):
            self.assertIn("timeout-minutes", workflow["jobs"][name])
            checkout = workflow["jobs"][name]["steps"][0]
            self.assertEqual(checkout["with"]["persist-credentials"], "false")
        self.assertTrue(
            any(
                s.get("run") == "pip install --require-hashes -r requirements-api-dev.lock"
                for s in api_steps
            )
        )
        steps = workflow["jobs"]["compose-config"]["steps"]
        validation = next(
            s["run"] for s in steps if s.get("name") == "Validate API delivery preparation"
        )
        self.assertIn("prepare_api_build_context.py", validation)
        self.assertIn("validate_api_staging_config.py", validation)
        self.assertIn("config --quiet", validation)
        for forbidden in ("compose up", "compose run", "docker build", "docker push", "secrets."):
            self.assertNotIn(forbidden, validation)


if __name__ == "__main__":
    unittest.main()
