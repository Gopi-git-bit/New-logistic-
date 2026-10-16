"""Offline contracts for the manual staging-secret presence workflow."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/validate-secrets.yml"
SECRET_NAMES = {
    "deepseek": "DEEPSEEK_STAGING_API_KEY",
    "openrouter": "OPENROUTER_STAGING_API_KEY",
}


class TestStagingSecretWorkflow(unittest.TestCase):
    def setUp(self):
        # BaseLoader preserves the Actions 'on' key instead of treating it as YAML 1.1 true.
        self.source = WORKFLOW.read_text()
        self.workflow = yaml.load(self.source, Loader=yaml.BaseLoader)
        self.job = self.workflow["jobs"]["presence"]
        self.steps = self.job["steps"]

    def test_manual_trigger_and_explicit_input_allowlist(self):
        self.assertEqual(set(self.workflow["on"]), {"workflow_dispatch"})
        inputs = self.workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"provider"})
        self.assertEqual(inputs["provider"]["type"], "choice")
        self.assertEqual(inputs["provider"]["required"], "true")
        self.assertEqual(inputs["provider"]["default"], "deepseek")
        self.assertEqual(inputs["provider"]["options"], ["deepseek", "openrouter"])

    def test_job_guard_denies_other_events_repositories_refs_and_actors(self):
        expression = self.job["if"].strip()
        self.assertTrue(expression.startswith("${{") and expression.endswith("}}"))
        clauses = expression[3:-2].split("&&")
        expected = {
            "event_name": "workflow_dispatch",
            "repository": "Gopi-git-bit/New-logistic-",
            "ref": "refs/heads/main",
            "actor_id": "200721521",
            "actor": "Gopi-git-bit",
            "triggering_actor": "Gopi-git-bit",
            "run_attempt": "1",
        }
        actual = {}
        for clause in clauses:
            match = re.fullmatch(r"\s*github\.(\w+)\s*==\s*'([^']+)'\s*", clause)
            self.assertIsNotNone(match)
            key, value = match.groups()
            self.assertNotIn(key, actual)
            actual[key] = value
        self.assertEqual(actual, expected)
        cases = [
            ({}, True),
            ({"event_name": "push"}, False),
            ({"event_name": "pull_request"}, False),
            ({"event_name": "pull_request_target"}, False),
            ({"event_name": "workflow_call"}, False),
            ({"repository": "fork-owner/New-logistic-"}, False),
            ({"ref": "refs/heads/feature"}, False),
            ({"ref": "refs/tags/main"}, False),
            ({"actor_id": "999999"}, False),
            ({"actor_id": ""}, False),
            ({"actor": "another-maintainer"}, False),
            ({"triggering_actor": "another-maintainer"}, False),
            ({"triggering_actor": ""}, False),
            ({"actor": "github-actions[bot]", "actor_id": "41898282"}, False),
            ({"actor": "another-maintainer", "triggering_actor": "Gopi-git-bit"}, False),
            ({"run_attempt": "2"}, False),
            ({"run_attempt": ""}, False),
        ]
        for overrides, allowed in cases:
            with self.subTest(overrides=overrides):
                context = expected | overrides
                self.assertEqual(all(context[k] == v for k, v in actual.items()), allowed)

    def test_least_privilege_and_step_scoped_secret_references(self):
        self.assertEqual(self.workflow["permissions"], {})
        self.assertEqual(set(self.workflow["jobs"]), {"presence"})
        self.assertEqual(self.job.get("permissions", {}), {})
        self.assertNotIn("env", self.workflow)
        self.assertNotIn("env", self.job)
        self.assertEqual(self.job["environment"], "Production")
        self.assertEqual(self.job["runs-on"], "ubuntu-24.04")
        self.assertEqual(self.job["timeout-minutes"], "2")
        self.assertEqual(len(self.steps), 3)
        self.assertEqual(self.steps[0]["env"], {"PROVIDER": "${{ inputs.provider }}"})
        for step, (provider, secret) in zip(self.steps[1:], SECRET_NAMES.items(), strict=True):
            self.assertEqual(step["if"], "${{ inputs.provider == '" + provider + "' }}")
            self.assertEqual(step["env"], {"PROVIDER_KEY": "${{ secrets." + secret + " }}"})
        self.assertEqual(
            set(re.findall(r"secrets\.([A-Z_]+)", self.source)), set(SECRET_NAMES.values())
        )

    def test_no_checkout_dependencies_external_calls_or_expression_injection(self):
        forbidden = r"\b(curl|wget|python\d*|pip\d*|npm|npx|ssh|scp|docker|printenv|source|eval)\b"
        for step in self.steps:
            self.assertNotIn("uses", step)
            self.assertEqual(step["shell"], "bash")
            self.assertNotIn("${{", step["run"])
            self.assertNotIn("$(", step["run"])
            self.assertNotIn("`", step["run"])
            self.assertNotRegex(step["run"], forbidden)
            result = subprocess.run(
                ["/bin/bash", "-n"], input=step["run"], capture_output=True, text=True, timeout=2
            )
            self.assertEqual(result.returncode, 0)

    def test_selection_is_validated_without_shell_interpolation(self):
        for provider, expected in [
            ("deepseek", 0),
            ("openrouter", 0),
            ("", 1),
            ("invalid", 1),
            ("deepseek; exit 0", 1),
        ]:
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as cwd:
                result = subprocess.run(
                    ["/bin/bash", "-c", self.steps[0]["run"]],
                    env={"PATH": "/usr/bin:/bin", "PROVIDER": provider},
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                self.assertEqual(result.returncode, expected)
                self.assertEqual(list(Path(cwd).iterdir()), [])

    def test_each_provider_fails_when_missing_and_never_prints_the_value(self):
        sentinel = "offline-only-presence-sentinel"
        for step, secret in zip(self.steps[1:], SECRET_NAMES.values(), strict=True):
            for present in (False, True):
                with self.subTest(secret=secret, present=present):
                    environment = {"PATH": "/usr/bin:/bin"}
                    if present:
                        environment["PROVIDER_KEY"] = sentinel
                    result = subprocess.run(
                        ["/bin/bash", "-c", step["run"]],
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    self.assertEqual(result.returncode, 0 if present else 1)
                    self.assertNotIn(sentinel, result.stdout + result.stderr)
                    self.assertIn(secret, result.stdout)
                    self.assertIn("unverified" if present else "unavailable", result.stdout)
