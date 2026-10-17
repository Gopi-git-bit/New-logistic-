"""Offline candidate/publication failures; network, crypto tools and registry are fakes."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = script("run_api_candidate")
publisher = script("publish_api_candidate")
c = builder.c
SOURCE = "a" * 40
SENTINEL = "SYNTHETIC_DO_NOT_LOG"


def identity():
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": c.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ACTOR": "Gopi-git-bit",
        "GITHUB_ACTOR_ID": "200721521",
        "GITHUB_TRIGGERING_ACTOR": "Gopi-git-bit",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": SOURCE,
        "GITHUB_WORKFLOW_SHA": SOURCE,
        "GITHUB_WORKFLOW_REF": c.WORKFLOW,
        "GITHUB_RUN_ID": "123456",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
        "API_AUTHORIZATION_EXPIRES": (datetime.now(UTC) + timedelta(minutes=45)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "API_PUBLICATION_SCOPE": "one-private-nondeployable-candidate",
        "API_ACCEPT_GAPS": c.GAPS,
    }


def settings():
    value = json.loads((ROOT / "infra/publication/api-candidate-policy.json").read_text())
    value.update(
        package_id=123,
        recipient="age1" + "a" * 58,
        access_review_sha256="d" * 64,
        access_review_expires_utc="2099-01-01T00:00:00Z",
    )
    return value


def pack(path, values, *, duplicate=None, special=None):
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, content in values.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        if duplicate:
            member = tarfile.TarInfo(duplicate)
            archive.addfile(member, io.BytesIO(b""))
        if special:
            member = tarfile.TarInfo(special)
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/shadow"
            archive.addfile(member)


def image(path):
    layer = b"synthetic uncompressed layer"
    diff = "sha256:" + hashlib.sha256(layer).hexdigest()
    config = json.dumps(
        {
            "os": "linux",
            "architecture": "amd64",
            "config": {"User": "10001:10001"},
            "rootfs": {"type": "layers", "diff_ids": [diff]},
        }
    ).encode()
    image_id = "sha256:" + hashlib.sha256(config).hexdigest()
    manifest = json.dumps(
        [{"Config": "config.json", "Layers": ["layer.tar"], "RepoTags": None}]
    ).encode()
    pack(path, {"manifest.json": manifest, "config.json": config, "layer.tar": layer})
    remote = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {"digest": image_id, "size": len(config)},
            "layers": [{"digest": "sha256:" + "f" * 64, "size": len(layer)}],
        }
    )
    return image_id, remote, config.decode()


def scan(image_id):
    return {
        "SchemaVersion": 2,
        "ArtifactType": "container_image",
        "Metadata": {"ImageID": image_id},
        "Results": [{"Target": "synthetic", "Vulnerabilities": [], "Secrets": []}],
    }


def sbom():
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"name": "example", "version": "1.0"}],
    }


class CandidateContracts(unittest.TestCase):
    def test_pinned_tool_archive_checksum_and_selected_member_only(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "age.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                data = b"synthetic binary; never executed"
                entry = tarfile.TarInfo("age/age")
                entry.size = len(data)
                package.addfile(entry, io.BytesIO(data))
            value = settings()
            value["tools"]["age"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()

            def response(*args, **kwargs):
                stream = io.BytesIO(archive.read_bytes())
                stream.url = "https://release-assets.githubusercontent.com/synthetic"
                return stream

            opener = SimpleNamespace(open=response)
            with patch.object(c.urllib.request, "build_opener", return_value=opener):
                c.install_tools(value, root / "tools", ("age",))
                self.assertEqual((root / "tools/age").read_bytes(), data)
                self.assertEqual((root / "tools/age").stat().st_mode & 0o777, 0o700)
                value["tools"]["age"]["sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "TOOL_HASH_MISMATCH"):
                    c.install_tools(value, root / "bad-tools", ("age",))

    def test_source_check_refuses_dirty_checkout_and_token_redirects(self):
        with patch.object(c, "command", side_effect=[SOURCE, " M Dockerfile.api"]):
            with self.assertRaisesRegex(ValueError, "DIRTY_CHECKOUT"):
                c.source_check(ROOT, SOURCE)
        self.assertIsNone(
            c.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.test")
        )

    def test_original_builder_retention_hook_preserves_admission_and_cleanup(self):
        spec = importlib.util.spec_from_file_location(
            "build_tests", ROOT / "workers/tests/test_api_build_only.py"
        )
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        runner = script("run_api_build")
        with tempfile.TemporaryDirectory() as raw:
            env = identity() | {"RUNNER_TEMP": raw}
            calls = []
            fake = baseline.FakeBuildCommands()
            report = {}
            runner.build(
                ROOT,
                SOURCE,
                env,
                report,
                command=fake,
                workflow=c.WORKFLOW,
                retain=lambda image_id, private, run: calls.append(image_id),
            )
            self.assertEqual(calls, [baseline.IMAGE])
            self.assertTrue(report["cleanup"]["new_local_image_removed"])
            fake = baseline.FakeBuildCommands()

            def fail(*args):
                raise ValueError("synthetic retain failure")

            report = {}
            with self.assertRaises(ValueError):
                runner.build(
                    ROOT, SOURCE, env, report, command=fake, workflow=c.WORKFLOW, retain=fail
                )
            self.assertTrue(report["cleanup"]["new_local_image_removed"])

    def test_failed_publisher_cli_preserves_unknown_push_state_without_secret_output(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "report.json"

            def fail(repo, source, env, folder, report):
                report.update(
                    stage="PUSH",
                    push_attempts=1,
                    publication_state="PUSH_ATTEMPTED_REMOTE_STATE_UNKNOWN",
                )
                raise ValueError(SENTINEL)

            argv = [
                "publish",
                "--repo-root",
                str(ROOT),
                "--source-sha",
                SOURCE,
                "--artifact",
                raw,
                "--report",
                str(output),
            ]
            stream = io.StringIO()
            old_umask = os.umask(0o077)
            try:
                with (
                    patch("sys.argv", argv),
                    patch.object(publisher, "publish", side_effect=fail),
                    contextlib.redirect_stdout(stream),
                ):
                    self.assertEqual(publisher.main(), 1)
            finally:
                os.umask(old_umask)
            report = json.loads(output.read_text())
            self.assertEqual(report["publication_state"], "PUSH_ATTEMPTED_REMOTE_STATE_UNKNOWN")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(SENTINEL, output.read_text() + stream.getvalue())

    def test_owner_main_attempt_source_and_workflow_admission(self):
        good = identity()
        self.assertEqual(c.admit(good, SOURCE)["run_id"], "123456")
        for key in (
            "GITHUB_ACTOR",
            "GITHUB_ACTOR_ID",
            "GITHUB_TRIGGERING_ACTOR",
            "GITHUB_RUN_ATTEMPT",
            "GITHUB_REPOSITORY",
            "GITHUB_REF",
            "GITHUB_EVENT_NAME",
            "GITHUB_SHA",
            "GITHUB_WORKFLOW_SHA",
            "GITHUB_WORKFLOW_REF",
            "RUNNER_ENVIRONMENT",
            "RUNNER_OS",
            "RUNNER_ARCH",
        ):
            bad = good | {key: "unexpected"}
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.admit(bad, SOURCE)

    def test_expiry_scope_and_individual_gap_acceptance_are_required(self):
        good = identity()
        for change in (
            {"API_AUTHORIZATION_EXPIRES": "2000-01-01T00:00:00Z"},
            {"API_AUTHORIZATION_EXPIRES": "2099-01-01T00:00:00Z"},
            {"API_AUTHORIZATION_EXPIRES": "not-a-date"},
            {"API_ACCEPT_GAPS": "REPRO-01,REPRO-02"},
            {"API_PUBLICATION_SCOPE": "production"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                c.admit(good | change, SOURCE)

    def test_checked_in_policy_is_intentionally_unconfigured(self):
        with self.assertRaisesRegex(ValueError, "PACKAGE_NOT_APPROVED"):
            c.policy(ROOT)

    def test_policy_requires_private_package_pin_key_review_and_expiry(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "infra/publication").mkdir(parents=True)
            path = repo / "infra/publication/api-candidate-policy.json"
            good = settings()
            path.write_text(json.dumps(good))
            self.assertEqual(c.policy(repo)["package_id"], 123)
            for field, value in (
                ("visibility", "public"),
                ("recipient", None),
                ("access_review_sha256", None),
                ("access_review_expires_utc", "2000-01-01T00:00:00Z"),
                ("registry", "ghcr.io/other/api"),
            ):
                path.write_text(json.dumps(good | {field: value}))
                with self.subTest(field=field), self.assertRaises((ValueError, TypeError)):
                    c.policy(repo)

    def test_green_ci_requires_exact_push_and_all_five_jobs(self):
        good = {
            "id": 123,
            "head_sha": SOURCE,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
        }
        jobs = {
            "total_count": 5,
            "jobs": [{"name": name, "conclusion": "success"} for name in c.CHECKS],
        }
        branch = {"commit": {"sha": SOURCE}}
        with patch.object(c, "api", side_effect=[branch, {"workflow_runs": [good]}, jobs]):
            self.assertEqual(c.green_ci(SOURCE, SENTINEL), 123)
        for changed in (
            good | {"head_sha": "b" * 40},
            good | {"event": "pull_request"},
            good | {"conclusion": "failure"},
        ):
            with (
                patch.object(c, "api", side_effect=[branch, {"workflow_runs": [changed]}]),
                self.assertRaises(ValueError),
            ):
                c.green_ci(SOURCE, SENTINEL)
        jobs["jobs"][0]["conclusion"] = "skipped"
        with (
            patch.object(c, "api", side_effect=[branch, {"workflow_runs": [good]}, jobs]),
            self.assertRaises(ValueError),
        ):
            c.green_ci(SOURCE, SENTINEL)

    def test_private_package_exact_owner_id_and_link_required(self):
        good = {
            "id": 123,
            "name": "zippy-api",
            "package_type": "container",
            "visibility": "private",
            "owner": {"id": 200721521, "login": "Gopi-git-bit"},
            "repository": {"id": 1349197102, "full_name": c.REPOSITORY},
        }
        with patch.object(c, "api", return_value=good):
            self.assertEqual(c.package_check(settings(), SENTINEL)["visibility"], "private")
        for change in (
            {"visibility": "public"},
            {"id": 456},
            {"repository": {"id": 99, "full_name": c.REPOSITORY}},
            {"owner": {"id": 99, "login": "Gopi-git-bit"}},
        ):
            with patch.object(c, "api", return_value=good | change), self.assertRaises(ValueError):
                c.package_check(settings(), SENTINEL)

    def test_archive_configuration_and_actual_layer_hashes(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "image.tar"
            image_id, _, _ = image(path)
            self.assertEqual(c.image_archive(path, image_id)["configured_user"], "10001:10001")
            with self.assertRaises(ValueError):
                c.image_archive(path, "sha256:" + "b" * 64)
            with tarfile.open(path, "r:") as archive:
                values = {m.name: archive.extractfile(m).read() for m in archive}
            values["layer.tar"] = b"tampered layer"
            pack(path, values)
            with self.assertRaises(ValueError):
                c.image_archive(path, image_id)

    def test_transfer_tar_rejects_traversal_links_duplicates_and_unknown_members(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bundle.tar"
            target = Path(raw) / "out"
            target.mkdir()
            for values, extra in (
                ({"../escape": b"x"}, {}),
                ({"x": b"x"}, {"special": "link"}),
                ({"x": b"x"}, {"duplicate": "x"}),
                ({"x": b"x", "unexpected": b"y"}, {}),
            ):
                pack(path, values, **extra)
                with self.subTest(values=values, extra=extra), self.assertRaises(ValueError):
                    c.unpack(path, target, {"x"})
                self.assertEqual(list(target.iterdir()), [])

    def test_high_critical_secrets_and_scan_image_mismatch_stop(self):
        good = scan("sha256:" + "b" * 64)
        builder.security(good, sbom(), "sha256:" + "b" * 64)
        for field in ("Vulnerabilities", "Secrets"):
            for level in ("HIGH", "CRITICAL"):
                bad = copy.deepcopy(good)
                bad["Results"][0][field] = [{"Severity": level}]
                with self.subTest(field=field, level=level), self.assertRaises(ValueError):
                    builder.security(bad, sbom(), "sha256:" + "b" * 64)
        with self.assertRaises(ValueError):
            builder.security(good, sbom(), "sha256:" + "c" * 64)

    def test_scanner_database_expiry_or_stale_identity_stops(self):
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw)
            (cache / "db").mkdir()
            (cache / "db/trivy.db").write_bytes(b"synthetic db")
            now = datetime.now(UTC)
            good = {
                "Version": 2,
                "UpdatedAt": (now - timedelta(hours=1)).isoformat(),
                "NextUpdate": (now + timedelta(hours=5)).isoformat(),
            }
            path = cache / "db/metadata.json"
            path.write_text(json.dumps(good))
            self.assertTrue(builder.database(cache)["trivy_db_sha256"].startswith("sha256:"))
            path.write_text(
                json.dumps(good | {"NextUpdate": (now - timedelta(hours=1)).isoformat()})
            )
            with self.assertRaises(ValueError):
                builder.database(cache)

    def test_child_environment_and_external_errors_do_not_leak_tokens(self):
        with patch.dict(os.environ, {"GH_PUBLISH_TOKEN": SENTINEL, "HTTP_PROXY": SENTINEL}):
            env = c.clean_env(Path("/private"), Path("/tools"))
            self.assertNotIn(SENTINEL, json.dumps(env))
            with patch.object(
                c.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=1, stdout=SENTINEL, stderr=SENTINEL),
            ):
                with self.assertRaisesRegex(ValueError, "TOOL_FAILED") as error:
                    c.command(["crane", "auth", "login"], env, stdin=SENTINEL)
                self.assertNotIn(SENTINEL, str(error.exception))

    def test_remote_manifest_and_config_and_layers_are_digest_bound(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "image.tar"
            image_id, manifest, config = image(path)
            expected = "sha256:" + hashlib.sha256(manifest.encode()).hexdigest()
            details = c.image_archive(path, image_id)
            self.assertEqual(
                publisher.registry_evidence(manifest, config, expected, details)[
                    "remote_layer_validation"
                ],
                "PASSED",
            )
            for bad_manifest, bad_config in ((manifest + " ", config), (manifest, config + " ")):
                with self.assertRaises(ValueError):
                    publisher.registry_evidence(bad_manifest, bad_config, expected, details)

    def test_workflow_permissions_trigger_artifact_and_secret_boundaries(self):
        text = (ROOT / ".github/workflows/api-candidate.yml").read_text()
        data = yaml.safe_load(text)
        self.assertEqual(set(data.get("on", data.get(True))), {"workflow_dispatch"})
        self.assertEqual(data["permissions"], {})
        prepare, publish = (data["jobs"][name] for name in ("prepare", "publish"))
        self.assertEqual(prepare["permissions"], {"contents": "read", "actions": "read"})
        self.assertEqual(
            publish["permissions"], {"contents": "read", "actions": "read", "packages": "write"}
        )
        self.assertEqual(publish["environment"], "Candidate-Publication")
        self.assertNotIn("secrets.", json.dumps(prepare))
        self.assertNotIn("Production", text)
        self.assertNotIn("DEEPSEEK", text)
        self.assertNotIn("OPENROUTER", text)
        self.assertIn("github.actor_id == '200721521'", prepare["if"])
        self.assertIn("github.run_attempt == 1", prepare["if"])
        for job in (prepare, publish):
            self.assertLessEqual(job["timeout-minutes"], 25)
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"@[a-f0-9]{40}$")
                if "upload-artifact" in step.get("uses", ""):
                    self.assertNotIn(".tar", step["with"]["path"])
                    self.assertEqual(step["with"]["retention-days"], 1)


class PipelineHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / "infra/publication").mkdir(parents=True)
        self.settings = settings()
        c.write_json(self.repo / "infra/publication/api-candidate-policy.json", self.settings)
        self.env = identity() | {
            "RUNNER_TEMP": str(self.root),
            "GITHUB_OUTPUT": str(self.root / "outputs"),
            "GH_READ_TOKEN": SENTINEL,
            "GH_PUBLISH_TOKEN": SENTINEL,
            "CANDIDATE_AGE_IDENTITY": SENTINEL,
            "API_PRIVATE_RESULT": str(self.root / "result.age"),
        }
        self.calls = []
        self.scan_failure = False
        self.push_failure = False
        self.wrong_remote_digest = False
        self.existing_tag = False
        self.artifact_changes = {}
        self.image_id, self.manifest, self.config = image(self.root / "fixture.tar")
        self.manifest_digest = "sha256:" + hashlib.sha256(self.manifest.encode()).hexdigest()

    def tools(self, settings, path, names):
        path.mkdir()

    def build(self, repo, source, env, report, *, workflow, retain):
        self.assertEqual(workflow, c.WORKFLOW)
        report.update(
            status="BUILD_ONLY_PASSED",
            run_identity=c.admit(env, source)["identity"],
            context={"source_sha": source},
            local_image_id=self.image_id,
            configured_image_user="10001:10001",
            cleanup={"new_local_image_removed": True},
        )

        def save(args, timeout):
            self.assertEqual(args[:4], ["docker", "image", "save", "--output"])
            Path(args[4]).write_bytes((self.root / "fixture.tar").read_bytes())
            return ""

        retain(self.image_id, self.root, save)

    def command(self, args, env, timeout=120, stdin=None):
        self.calls.append(args)
        self.assertNotIn(SENTINEL, json.dumps(env))
        self.assertNotIn(SENTINEL, json.dumps(args))
        tool = Path(args[0]).name
        if tool == "git":
            return SOURCE if args[-1] == "HEAD" else ""
        if tool == "age":
            source = Path(args[-1])
            target = Path(args[args.index("--output") + 1])
            if "--decrypt" in args:
                target.write_bytes(source.read_bytes()[4:])
            else:
                target.write_bytes(b"FAKE" + source.read_bytes())
            return ""
        if tool == "trivy":
            self.assertEqual(args[args.index("--config") + 1], "")
            self.assertIn("--disable-telemetry", args)
            self.assertIn("--offline-scan", args)
            self.assertIn("--skip-version-check", args)
            if "cyclonedx" not in args:
                self.assertEqual(args[args.index("--image-config-scanners") + 1], "secret")
            if self.scan_failure:
                raise ValueError("TOOL_FAILED")
            cache = Path(args[args.index("--cache-dir") + 1])
            if not (cache / "db").exists():
                (cache / "db").mkdir(parents=True)
                (cache / "db/trivy.db").write_bytes(b"synthetic db")
                c.write_json(
                    cache / "db/metadata.json",
                    {
                        "Version": 2,
                        "UpdatedAt": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                        "NextUpdate": (datetime.now(UTC) + timedelta(hours=5)).isoformat(),
                    },
                )
            output = Path(args[args.index("--output") + 1])
            c.write_json(output, sbom() if "cyclonedx" in args else scan(self.image_id))
            return ""
        if args[1] == "digest":
            if self.wrong_remote_digest and "--tarball" not in args:
                return "sha256:" + "0" * 64
            return self.manifest_digest
        if args[1] == "ls":
            return "candidate-" + SOURCE + "-123456" if self.existing_tag else "older-candidate"
        if args[1] == "manifest":
            return self.manifest
        if args[1] == "config":
            return self.config
        if args[1] == "push" and self.push_failure:
            raise subprocess.TimeoutExpired("crane", 180)
        return ""

    def prepare(self):
        output = self.root / "export"
        real_loader = builder.c.load_script

        # Admission uses run_api_build.admit, so override the fake module's admission too.
        fake_module = SimpleNamespace(build=self.build, admit=real_loader("run_api_build").admit)
        with (
            patch.object(
                builder.c,
                "load_script",
                side_effect=lambda name: (
                    fake_module if name == "run_api_build" else real_loader(name)
                ),
            ),
            patch.object(builder.c, "green_ci", return_value=789),
            patch.object(builder.c, "install_tools", side_effect=self.tools),
            patch.object(builder.c, "command", side_effect=self.command),
        ):
            result = {}
            builder.prepare(self.repo, SOURCE, self.env, output, result)
        for line in Path(self.env["GITHUB_OUTPUT"]).read_text().splitlines():
            key, value = line.split("=", 1)
            self.env["API_" + key.upper()] = value
        self.env.update(API_ARTIFACT_ID="42", API_ARTIFACT_DIGEST="sha256:" + "e" * 64)
        return output, result

    def artifact_api(self, path, token):
        return {
            "id": 42,
            "expired": False,
            "name": "encrypted-api-candidate-123456",
            "digest": "sha256:" + "e" * 64,
            "size_in_bytes": 10240,
            "workflow_run": {"id": 123456, "head_sha": SOURCE, "repository_id": 1349197102},
        } | self.artifact_changes

    def publish(self, output, result):
        with (
            patch.object(publisher.c, "green_ci", return_value=789),
            patch.object(publisher.c, "api", side_effect=self.artifact_api),
            patch.object(
                publisher.c, "package_check", return_value={"id": 123, "visibility": "private"}
            ),
            patch.object(publisher.c, "install_tools", side_effect=self.tools),
            patch.object(publisher.c, "command", side_effect=self.command),
        ):
            publisher.publish(self.repo, SOURCE, self.env, output, result)

    def test_complete_mocked_candidate_pipeline_exact_artifact_one_push_no_runtime(self):
        output, prepared = self.prepare()
        self.assertEqual(prepared["status"], "ENCRYPTED_CANDIDATE_PREPARED")
        self.assertEqual({p.name for p in output.iterdir()}, {"candidate.age", "transfer.json"})
        self.calls.clear()
        result = {}
        self.publish(output, result)
        self.assertEqual(result["status"], "PRIVATE_CANDIDATE_PUBLISHED")
        self.assertEqual(result["push_attempts"], 1)
        self.assertEqual(sum(args[1] == "push" for args in self.calls), 1)
        self.assertTrue(Path(self.env["API_PRIVATE_RESULT"]).read_bytes().startswith(b"FAKE"))
        self.assertFalse(
            any(Path(args[0]).name in ("docker", "python", "pip", "uvicorn") for args in self.calls)
        )
        self.assertTrue(any(args[1:3] == ["validate", "--remote"] for args in self.calls))
        self.assertFalse(list(self.root.glob("api-publish-*")))
        self.assertFalse(list(self.root.glob("api-candidate-*")))

    def test_transfer_tamper_stops_before_tool_install_login_or_push(self):
        output, _ = self.prepare()
        (output / "candidate.age").write_bytes(b"tampered")
        self.calls.clear()
        with self.assertRaises(ValueError):
            self.publish(output, {})
        self.assertTrue(all(args[0] == "git" for args in self.calls))

    def test_other_run_expired_or_wrong_digest_artifact_refused_before_login(self):
        output, _ = self.prepare()
        for change in (
            {"expired": True},
            {"digest": "sha256:" + "0" * 64},
            {"workflow_run": {"id": 99, "head_sha": SOURCE, "repository_id": 1349197102}},
        ):
            self.calls.clear()
            self.artifact_changes = change
            with self.assertRaises(ValueError):
                self.publish(output, {})
            self.assertTrue(all(args[0] == "git" for args in self.calls))

    def test_policy_or_gap_changes_cannot_reuse_encrypted_candidate(self):
        output, _ = self.prepare()
        path = self.repo / "infra/publication/api-candidate-policy.json"
        changed = copy.deepcopy(self.settings)
        changed["gaps"]["REPRO-01"] = "changed after build"
        path.write_text(json.dumps(changed))
        self.calls.clear()
        with self.assertRaises(ValueError):
            self.publish(output, {})
        self.assertFalse(any(args[1] in ("auth", "push") for args in self.calls))

    def test_existing_tag_refused_and_timeout_never_replayed(self):
        output, _ = self.prepare()
        self.existing_tag = True
        with self.assertRaises(ValueError):
            self.publish(output, {})
        self.assertFalse(any(args[1] == "push" for args in self.calls))
        self.existing_tag = False
        self.push_failure = True
        self.calls.clear()
        result = {}
        with self.assertRaises(subprocess.TimeoutExpired):
            self.publish(output, result)
        self.assertEqual(result["publication_state"], "PUSH_ATTEMPTED_REMOTE_STATE_UNKNOWN")
        self.assertEqual(sum(args[1] == "push" for args in self.calls), 1)

    def test_scan_failure_exports_no_plaintext_or_cipher(self):
        self.scan_failure = True
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list((self.root / "export").iterdir()), [])
        self.assertFalse(list(self.root.glob("api-candidate-*")))

    def test_readback_mismatch_keeps_unknown_push_audit_and_never_replays(self):
        output, _ = self.prepare()
        self.wrong_remote_digest = True
        self.calls.clear()
        result = {}
        with self.assertRaisesRegex(ValueError, "REGISTRY_DIGEST_MISMATCH"):
            self.publish(output, result)
        self.assertEqual(result["publication_state"], "PUSH_ATTEMPTED_REMOTE_STATE_UNKNOWN")
        self.assertEqual(result["expected_manifest_digest"], self.manifest_digest)
        self.assertEqual(sum(args[1] == "push" for args in self.calls), 1)
        self.assertFalse(Path(self.env["API_PRIVATE_RESULT"]).exists())


if __name__ == "__main__":
    unittest.main()
