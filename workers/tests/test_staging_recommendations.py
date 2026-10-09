"""Mocked HTTP evidence for the isolated adapter and finite synthetic runner."""

import ast
import asyncio
import importlib.util
import json
import socket
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from test_m6_handlers import FakeM6Db

from zippy_workers import recommendation_provider
from zippy_workers.capabilities import UnauthorizedCapability, assert_can_call_external
from zippy_workers.recommendation_provider import (
    CONFIG_NAMES,
    MAX_RESPONSE_BYTES,
    OpenAIRecommendationAgent,
    ProviderCleanupError,
    ProviderSettings,
    StagingConfigurationError,
)
from zippy_workers.recommendations import (
    RecommendationAgent,
    RecommendationCandidate,
    RecommendationRequest,
    recommend_drivers,
)

BASELINE = ("candidate-0", "candidate-1", "candidate-2")
REVERSED = tuple(reversed(BASELINE))
ENVIRONMENT = {
    "OMS_STAGING_ENDPOINT": "https://provider.example/v1/chat/completions",
    "OMS_STAGING_API_KEY": "synthetic-provider-key",
    "OMS_STAGING_MODEL": "owner-selected-exact-model",
    "OMS_STAGING_TIMEOUT_SECONDS": "0.02",
    "OMS_STAGING_MAX_OUTPUT_TOKENS": "128",
}
SETTINGS = ProviderSettings.from_environment(ENVIRONMENT)
RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts/run_oms_recommendation.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("oms_staging_runner", RUNNER_PATH)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
runner = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = runner
RUNNER_SPEC.loader.exec_module(runner)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("staging tests attempted live network I/O")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(autouse=True)
def fake_provider_authorization(monkeypatch):
    """Authorize only the mocked OMS capability; leave the real matrix unchanged."""

    def authorize(agent, service):
        assert (agent, service) == ("order_management", "oms_recommendation_provider")

    monkeypatch.setattr(runner, "assert_can_call_external", authorize)


class TrackedTransport(httpx.MockTransport):
    closed = False

    async def aclose(self):
        self.closed = True


class TrackedStream(httpx.AsyncByteStream):
    def __init__(self, body=b"", *, hang=False):
        self.body = body
        self.hang = hang
        self.closed = False
        self.cancelled = False

    async def __aiter__(self):
        try:
            if self.hang:
                await asyncio.Future()
            yield self.body
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aclose(self):
        self.closed = True


def envelope(output, **message_fields):
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(output),
                    **message_fields,
                },
            }
        ]
    }


def execute(response):
    requests = []

    def handle(request):
        requests.append(request)
        return response

    transport = TrackedTransport(handle)

    async def scenario():
        report = await runner.run_synthetic(SETTINGS, transport=transport)
        await asyncio.sleep(0)
        assert asyncio.all_tasks() == {asyncio.current_task()}
        return report

    report = asyncio.run(scenario())
    assert transport.closed
    assert len(requests) == report.requests_started == 1
    assert report.baseline_ids == BASELINE
    assert not report.telemetry_enabled
    return report, requests


def test_valid_response_is_minimized_and_does_not_resort_or_mutate():
    db = FakeM6Db()
    before_db = deepcopy(vars(db))
    before_matches = runner.SYNTHETIC_MATCHES
    report, requests = execute(httpx.Response(200, json=envelope({"candidate_ids": REVERSED})))
    assert report.advisory.source == "agent"
    assert report.advisory.reason_code == "RECOMMENDED"
    assert report.advisory.candidate_ids == REVERSED
    assert report.provider_outcome == "RESPONSE_RECEIVED"
    assert vars(db) == before_db
    assert runner.SYNTHETIC_MATCHES == before_matches
    payload = json.loads(requests[0].content)
    assert set(payload) == {"model", "max_tokens", "response_format", "messages"}
    assert payload["model"] == ENVIRONMENT["OMS_STAGING_MODEL"]
    assert payload["max_tokens"] == 128
    assert json.loads(payload["messages"][1]["content"]) == [
        {"candidate_id": "candidate-0", "distance_m": 30, "score": 7},
        {"candidate_id": "candidate-1", "distance_m": 10, "score": 9},
        {"candidate_id": "candidate-2", "distance_m": 20, "score": 8},
    ]
    assert requests[0].headers["X-Agent-ID"] == "order_management"
    assert requests[0].headers["X-Correlation-ID"]
    assert requests[0].headers["X-Request-Timestamp"]
    assert "Idempotency-Key" not in requests[0].headers


@pytest.mark.parametrize(
    "output",
    [
        None,
        "not an object",
        [],
        {"candidate_ids": []},
        {"candidate_ids": ["candidate-0", "candidate-0", "candidate-2"]},
        {"candidate_ids": ["candidate-0", "candidate-1"]},
        {"candidate_ids": ["candidate-0", "candidate-1", "outsider"]},
        {"candidate_ids": ["candidate-0", "candidate-1", "candidate-2", "candidate-3"]},
        {"candidate_ids": [0, 1, 2]},
        {"candidate_ids": BASELINE, "assign_driver": True},
        {"candidate_ids": BASELINE, "refund_approved": True},
        {"candidate_ids": BASELINE, "settlement_status": "released"},
    ],
)
def test_invalid_ranking_has_explicit_unchanged_fallback(output):
    report, _ = execute(httpx.Response(200, json=envelope(output)))
    assert report.advisory.source == "deterministic"
    assert report.advisory.reason_code == "MALFORMED_OUTPUT"
    assert report.advisory.candidate_ids == BASELINE


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"choices": [], "choices": []}',
        json.dumps({"choices": []}).encode(),
        json.dumps({"choices": [{}, {}]}).encode(),
        json.dumps(envelope({"candidate_ids": BASELINE}, tool_calls=[{}])).encode(),
        json.dumps(envelope({"candidate_ids": BASELINE}, refusal="refused")).encode(),
        json.dumps(
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        ).encode(),
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "not json"},
                    }
                ]
            }
        ).encode(),
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"candidate_ids": [], "candidate_ids": []}',
                        },
                    }
                ]
            }
        ).encode(),
    ],
)
def test_invalid_provider_envelope_is_explicit_and_closes_stream(body):
    stream = TrackedStream(body)
    report, _ = execute(httpx.Response(200, stream=stream))
    assert report.advisory.source == "deterministic"
    assert report.advisory.reason_code == "AGENT_FAILURE"
    assert report.advisory.candidate_ids == BASELINE
    assert report.provider_outcome == "MALFORMED_RESPONSE"
    assert stream.closed


def test_response_bytes_are_bounded():
    stream = TrackedStream(b"x" * (MAX_RESPONSE_BYTES + 1))
    report, _ = execute(httpx.Response(200, stream=stream))
    assert report.advisory.candidate_ids == BASELINE
    assert report.advisory.reason_code == "AGENT_FAILURE"
    assert report.provider_outcome == "RESPONSE_TOO_LARGE"
    assert stream.closed


@pytest.mark.parametrize("status", [301, 302, 401, 403, 500, 503])
def test_http_failures_do_not_retry_redirect_or_expose_body(status):
    report, requests = execute(
        httpx.Response(
            status,
            headers={"Location": "https://outsider.example/"},
            text="sensitive provider diagnostic",
        )
    )
    assert len(requests) == 1
    assert report.advisory.candidate_ids == BASELINE
    assert report.advisory.reason_code == "AGENT_UNAVAILABLE"
    assert report.provider_outcome == "HTTP_REJECTED"
    assert "sensitive" not in repr(report)


@pytest.mark.parametrize("retry_after", ["60", "Fri, 09 Oct 2026 12:00:00 GMT", "invalid"])
def test_rate_limit_stops_without_retry_or_retry_after_sleep(retry_after):
    report, _ = execute(httpx.Response(429, headers={"Retry-After": retry_after}, text="private"))
    assert report.provider_outcome == "RATE_LIMITED"
    assert report.advisory.reason_code == "AGENT_UNAVAILABLE"
    assert report.advisory.candidate_ids == BASELINE


@pytest.mark.parametrize(
    "error,reason,outcome",
    [
        (httpx.ConnectError("private diagnostic"), "AGENT_UNAVAILABLE", "UNAVAILABLE"),
        (httpx.ReadTimeout("private diagnostic"), "AGENT_TIMEOUT", "TIMEOUT"),
    ],
)
def test_transport_failure_is_sanitized_and_closed(error, reason, outcome):
    def handle(request):
        raise error

    transport = TrackedTransport(handle)
    report = asyncio.run(runner.run_synthetic(SETTINGS, transport=transport))
    assert report.advisory.reason_code == reason
    assert report.advisory.candidate_ids == BASELINE
    assert report.provider_outcome == outcome
    assert transport.closed
    assert "private" not in repr(report)


def test_total_deadline_cancels_hanging_stream_and_leaves_no_tasks():
    stream = TrackedStream(hang=True)
    transport = TrackedTransport(lambda request: httpx.Response(200, stream=stream))

    async def scenario():
        started = asyncio.get_running_loop().time()
        report = await asyncio.wait_for(
            runner.run_synthetic(SETTINGS, transport=transport), timeout=0.2
        )
        assert asyncio.get_running_loop().time() - started < 0.2
        assert report.advisory.reason_code == "AGENT_TIMEOUT"
        assert report.advisory.candidate_ids == BASELINE
        assert stream.closed and stream.cancelled and transport.closed
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_caller_cancellation_closes_provider_without_background_requests():
    started = asyncio.Event()
    cancelled = False

    async def handle(request):
        nonlocal cancelled
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled = True

    transport = TrackedTransport(handle)

    async def scenario():
        task = asyncio.create_task(runner.run_synthetic(SETTINGS, transport=transport))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled and transport.closed
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_cleanup_failure_is_explicit_not_a_successful_report():
    class BrokenClose(TrackedTransport):
        async def aclose(self):
            raise httpx.ConnectError("private cleanup diagnostic")

    transport = BrokenClose(
        lambda request: httpx.Response(200, json=envelope({"candidate_ids": BASELINE}))
    )
    with pytest.raises(ProviderCleanupError, match="PROVIDER_CLEANUP_FAILURE"):
        asyncio.run(runner.run_synthetic(SETTINGS, transport=transport))


def test_cleanup_timeout_is_bounded_and_explicit():
    class HangingClose(TrackedTransport):
        async def aclose(self):
            await asyncio.Future()

    transport = HangingClose(
        lambda request: httpx.Response(200, json=envelope({"candidate_ids": BASELINE}))
    )
    with pytest.raises(ProviderCleanupError, match="PROVIDER_CLEANUP_FAILURE"):
        asyncio.run(
            asyncio.wait_for(runner.run_synthetic(SETTINGS, transport=transport), timeout=0.2)
        )


def test_successful_cleanup_is_idempotent_after_run_deadline():
    class CountingClose(TrackedTransport):
        closes = 0

        async def aclose(self):
            self.closes += 1
            await super().aclose()

    stream = TrackedStream(json.dumps(envelope({"candidate_ids": BASELINE})).encode())
    transport = CountingClose(lambda request: httpx.Response(200, stream=stream))
    agent = OpenAIRecommendationAgent(SETTINGS, transport=transport)

    async def scenario():
        await recommend_drivers([{}, {}, {}], agent, timeout_seconds=0.1)
        await agent.aclose()
        assert agent.is_closed and stream.closed and transport.closed
        agent._deadline = asyncio.get_running_loop().time() - 1
        await agent.aclose()
        await agent.aclose()
        assert transport.closes == 1
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_failed_cleanup_stays_explicit_despite_httpx_closed_flag():
    class BrokenClose(TrackedTransport):
        async def aclose(self):
            raise httpx.ConnectError("private cleanup diagnostic")

    agent = OpenAIRecommendationAgent(SETTINGS, transport=BrokenClose(lambda request: None))

    async def scenario():
        with pytest.raises(ProviderCleanupError, match="PROVIDER_CLEANUP_FAILURE"):
            await agent.aclose()
        assert agent.is_closed
        with pytest.raises(ProviderCleanupError, match="PROVIDER_CLEANUP_FAILURE"):
            await agent.aclose()
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_adapter_conforms_to_protocol_and_cannot_make_a_second_request():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=envelope({"candidate_ids": BASELINE}))

    transport = TrackedTransport(handle)
    concrete = OpenAIRecommendationAgent(SETTINGS, transport=transport)
    agent: RecommendationAgent = concrete
    candidates = [{}, {}, {}]

    async def scenario():
        first = await recommend_drivers(candidates, agent, timeout_seconds=0.1)
        second = await recommend_drivers(candidates, agent, timeout_seconds=0.1)
        await concrete.aclose()
        assert first.reason_code == "RECOMMENDED"
        assert second.reason_code == "AGENT_FAILURE"
        assert second.candidate_ids == BASELINE

    asyncio.run(scenario())
    assert len(calls) == 1 and concrete.is_closed


def test_input_bytes_are_bounded_before_http(monkeypatch):
    transport = TrackedTransport(lambda request: pytest.fail("oversized request sent"))
    agent = OpenAIRecommendationAgent(SETTINGS, transport=transport)
    request = RecommendationRequest(
        tuple(RecommendationCandidate(f"candidate-{index}", 10, 1) for index in range(100))
    )
    monkeypatch.setattr(
        recommendation_provider.json,
        "dumps",
        lambda *args, **kwargs: pytest.fail("oversized input reached serialization"),
    )

    async def scenario():
        try:
            with pytest.raises(ValueError, match="PROVIDER_INPUT_LIMIT"):
                await agent.rank(request)
        finally:
            await agent.aclose()

    asyncio.run(scenario())
    assert agent.requests_started == 0 and transport.closed


def test_oversized_chunk_is_rejected_before_copying_into_response_buffer(monkeypatch):
    class BoundedBuffer(bytearray):
        def extend(self, data):
            assert len(self) + len(data) <= MAX_RESPONSE_BYTES
            super().extend(data)

    monkeypatch.setattr(recommendation_provider, "bytearray", BoundedBuffer, raising=False)
    stream = TrackedStream(b"x" * (MAX_RESPONSE_BYTES * 4))
    report, _ = execute(httpx.Response(200, stream=stream))
    assert report.provider_outcome == "RESPONSE_TOO_LARGE"
    assert report.advisory.candidate_ids == BASELINE and stream.closed


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "br", "zstd"])
def test_compressed_response_is_refused_without_decoding_or_reading(encoding):
    class UnreadStream(TrackedStream):
        async def __aiter__(self):
            pytest.fail("compressed response was consumed")
            yield b""

    stream = UnreadStream()
    report, requests = execute(
        httpx.Response(200, headers={"Content-Encoding": encoding}, stream=stream)
    )
    assert requests[0].headers["Accept-Encoding"] == "identity"
    assert report.provider_outcome == "MALFORMED_RESPONSE"
    assert report.advisory.candidate_ids == BASELINE and stream.closed


@pytest.mark.parametrize("length", [str(MAX_RESPONSE_BYTES + 1), "9" * 100])
def test_content_length_limit_rejects_before_body_read(length):
    class UnreadStream(TrackedStream):
        async def __aiter__(self):
            pytest.fail("oversized response was consumed")
            yield b""

    stream = UnreadStream()
    report, _ = execute(httpx.Response(200, headers={"Content-Length": length}, stream=stream))
    assert report.provider_outcome == "RESPONSE_TOO_LARGE"
    assert report.advisory.candidate_ids == BASELINE and stream.closed


def test_one_run_deadline_includes_response_and_transport_cleanup():
    class SlowStream(TrackedStream):
        async def aclose(self):
            await asyncio.sleep(0.05)
            self.closed = True

    stream = SlowStream(json.dumps(envelope({"candidate_ids": REVERSED})).encode())

    async def handle(request):
        await asyncio.sleep(0.016)
        return httpx.Response(200, stream=stream)

    class SlowClose(TrackedTransport):
        async def aclose(self):
            await asyncio.sleep(0.05)
            self.closed = True

    transport = SlowClose(handle)
    settings = replace(SETTINGS, timeout_seconds=0.08)

    async def scenario():
        started = asyncio.get_running_loop().time()
        report = await runner.run_synthetic(settings, transport=transport)
        assert asyncio.get_running_loop().time() - started < 0.1
        assert report.advisory.candidate_ids == REVERSED
        assert stream.closed and transport.closed
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_stalled_request_cancellation_does_not_prevent_client_close():
    closed = asyncio.Event()

    class DrainAfterClose(TrackedStream):
        async def __aiter__(self):
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                await closed.wait()
                raise
            yield b""

    stream = DrainAfterClose()

    class ReleaseOnClose(TrackedTransport):
        async def aclose(self):
            self.closed = True
            closed.set()

    transport = ReleaseOnClose(lambda request: httpx.Response(200, stream=stream))

    async def scenario():
        report = await asyncio.wait_for(
            runner.run_synthetic(SETTINGS, transport=transport), timeout=0.2
        )
        assert report.advisory.reason_code == "AGENT_TIMEOUT"
        assert report.advisory.candidate_ids == BASELINE
        assert stream.closed and transport.closed
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_cancellation_during_cleanup_finishes_closing_without_pending_tasks():
    closing = asyncio.Event()

    class SlowClose(TrackedTransport):
        async def aclose(self):
            closing.set()
            await asyncio.sleep(0.005)
            self.closed = True

    transport = SlowClose(
        lambda request: httpx.Response(200, json=envelope({"candidate_ids": BASELINE}))
    )

    async def scenario():
        task = asyncio.create_task(runner.run_synthetic(SETTINGS, transport=transport))
        await closing.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.closed
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "candidate",
    [
        RecommendationCandidate("private-driver-id", 10, 1),
        RecommendationCandidate("candidate-0", float("nan"), 1),
        RecommendationCandidate("candidate-0", 10, float("inf")),
        RecommendationCandidate("candidate-0", True, 1),
        RecommendationCandidate("candidate-0", 10**1000, 1),
    ],
)
def test_direct_adapter_rejects_nonopaque_or_unsafe_inputs_before_http(candidate):
    calls = []
    transport = TrackedTransport(lambda request: calls.append(request))
    agent = OpenAIRecommendationAgent(SETTINGS, transport=transport)

    async def scenario():
        try:
            with pytest.raises(ValueError, match="PROVIDER_INPUT"):
                await agent.rank(RecommendationRequest((candidate,)))
        finally:
            await agent.aclose()

    asyncio.run(scenario())
    assert calls == [] and agent.requests_started == 0 and transport.closed


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_configuration_has_no_endpoint_credential_model_or_limit_defaults(name):
    environment = {key: value for key, value in ENVIRONMENT.items() if key != name}
    with pytest.raises(StagingConfigurationError, match=f"MISSING_{name}"):
        ProviderSettings.from_environment(environment)


@pytest.mark.parametrize(
    "name,value",
    [
        ("OMS_STAGING_ENDPOINT", "http://provider.example/chat"),
        ("OMS_STAGING_ENDPOINT", "https://secret@provider.example/chat"),
        ("OMS_STAGING_ENDPOINT", "https://provider.example/chat?token=secret"),
        ("OMS_STAGING_ENDPOINT", "https://provider.example/chat#secret"),
        ("OMS_STAGING_ENDPOINT", "https://provider.example"),
        ("OMS_STAGING_MODEL", ""),
        ("OMS_STAGING_MODEL", " model "),
        ("OMS_STAGING_MODEL", "m" * 257),
        ("OMS_STAGING_API_KEY", "secret\nvalue"),
        ("OMS_STAGING_TIMEOUT_SECONDS", "nan"),
        ("OMS_STAGING_TIMEOUT_SECONDS", "inf"),
        ("OMS_STAGING_TIMEOUT_SECONDS", "0"),
        ("OMS_STAGING_TIMEOUT_SECONDS", "11"),
        ("OMS_STAGING_MAX_OUTPUT_TOKENS", "0"),
        ("OMS_STAGING_MAX_OUTPUT_TOKENS", "257"),
        ("OMS_STAGING_MAX_OUTPUT_TOKENS", "1.5"),
    ],
)
def test_invalid_configuration_errors_never_display_values(name, value):
    with pytest.raises(StagingConfigurationError) as error:
        ProviderSettings.from_environment({**ENVIRONMENT, name: value})
    assert "secret" not in str(error.value)
    assert value != str(error.value)


@pytest.mark.parametrize(
    "name",
    [
        "DATABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "RAZORPAY_KEY_SECRET",
        "STRIPE_SECRET_KEY",
        "PAPERCLIP_ENVELOPE_SIGNING_KEY",
        "ODOO_PASSWORD",
        "HERMES_API_KEY",
        "LANGFUSE_SECRET_KEY",
        "OPENROUTER_API_KEY",
        "CUSTOM_ASSIGNMENT_CREDENTIAL",
        "HTTP_PROXY",
        "SSL_CERT_FILE",
    ],
)
def test_cli_refuses_any_nonallowlisted_environment_without_loading_credentials(name, capsys):
    status = runner.main(
        ["--run-synthetic-shadow"],
        environment={**ENVIRONMENT, name: "private-value"},
    )
    assert status == 1
    output = capsys.readouterr().out
    assert json.loads(output) == {"status": "ERROR", "reason_code": "ISOLATION_VIOLATION"}
    assert "private-value" not in output


def test_settings_representation_is_redacted():
    assert "synthetic-provider-key" not in repr(SETTINGS)
    assert ENVIRONMENT["OMS_STAGING_ENDPOINT"] not in repr(SETTINGS)
    assert ENVIRONMENT["OMS_STAGING_MODEL"] not in repr(SETTINGS)
    assert "another-secret" not in repr(replace(SETTINGS, api_key=SecretStr("another-secret")))


def test_cli_requires_explicit_invocation_before_configuration_or_http(capsys):
    with pytest.raises(SystemExit) as error:
        runner.main([], environment=ENVIRONMENT)
    assert error.value.code == 2
    assert "--run-synthetic-shadow" in capsys.readouterr().err


def test_real_cli_process_rejects_operational_environment_before_http():
    root = Path(__file__).resolve().parents[2]
    environment = {
        **ENVIRONMENT,
        "PYTHONPATH": str(root / "workers/src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "SUPABASE_SERVICE_ROLE_KEY": "synthetic-forbidden-key",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(root / "workers/scripts/run_oms_recommendation.py"),
            "--run-synthetic-shadow",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["reason_code"] == "ISOLATION_VIOLATION"
    assert "synthetic-forbidden-key" not in result.stdout + result.stderr
    assert "synthetic-provider-key" not in result.stdout + result.stderr


def test_cli_output_contains_only_advisory_refs_and_safe_outcomes(monkeypatch, capsys):
    concrete = runner.OpenAIRecommendationAgent
    transport = TrackedTransport(
        lambda request: httpx.Response(200, json=envelope({"candidate_ids": REVERSED}))
    )
    monkeypatch.setattr(
        runner,
        "OpenAIRecommendationAgent",
        lambda settings, **kwargs: concrete(settings, transport=transport),
    )
    assert runner.main(["--run-synthetic-shadow"], environment=ENVIRONMENT) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["status"] == "SHADOW_ONLY"
    assert report["baseline_ids"] == list(BASELINE)
    assert report["advisory"]["candidate_ids"] == list(REVERSED)
    assert report["requests_started"] == 1 and not report["telemetry_enabled"]
    for value in ENVIRONMENT.values():
        assert value not in output
    assert transport.closed


def test_cli_cleanup_error_has_nonzero_exit_and_no_provider_diagnostic(monkeypatch, capsys):
    async def fail(settings):
        raise ProviderCleanupError("PROVIDER_CLEANUP_FAILURE")

    monkeypatch.setattr(runner, "run_synthetic", fail)
    assert runner.main(["--run-synthetic-shadow"], environment=ENVIRONMENT) == 1
    assert json.loads(capsys.readouterr().out)["reason_code"] == "PROVIDER_CLEANUP_FAILURE"


def test_missing_read_capability_denies_before_provider_creation(monkeypatch):
    monkeypatch.setattr(runner, "has_capability", lambda *args: False)
    with pytest.raises(UnauthorizedCapability, match="OMS_STAGING_CAPABILITY_DENIED"):
        asyncio.run(runner.run_synthetic(SETTINGS))


def test_real_matrix_denies_provider_before_client_creation(monkeypatch, capsys):
    monkeypatch.setattr(runner, "assert_can_call_external", assert_can_call_external)

    def forbidden(*args, **kwargs):
        pytest.fail("unauthorized provider client was constructed")

    monkeypatch.setattr(runner, "OpenAIRecommendationAgent", forbidden)
    assert runner.main(["--run-synthetic-shadow"], environment=ENVIRONMENT) == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "ERROR",
        "reason_code": "OMS_STAGING_PROVIDER_NOT_AUTHORIZED",
    }


def test_real_cli_valid_configuration_still_cannot_authorize_provider():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--run-synthetic-shadow"],
        env={**ENVIRONMENT, "PYTHONPATH": str(root / "workers/src"), "LANG": "C.UTF-8"},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "status": "ERROR",
        "reason_code": "OMS_STAGING_PROVIDER_NOT_AUTHORIZED",
    }
    assert "synthetic-provider-key" not in result.stdout + result.stderr


def test_runner_and_adapter_have_no_operational_ports_or_active_registration():
    root = Path(__file__).resolve().parents[2]
    runner_path = root / "workers/scripts/run_oms_recommendation.py"
    adapter_path = root / "workers/src/zippy_workers/recommendation_provider.py"
    for path in (runner_path, adapter_path):
        tree = ast.parse(path.read_text())
        imports = {
            node.module if isinstance(node, ast.ImportFrom) else alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not any(
            forbidden in module
            for module in imports
            for forbidden in ("database", "supabase", "handlers", "kernel", "tracing", "paperclip")
        )
    for folder in (root / "api", root / "workers/src/zippy_workers"):
        for path in folder.rglob("*.py"):
            if path == adapter_path or any(part.startswith("tests") for part in path.parts):
                continue
            assert "recommendation_provider" not in path.read_text(), path
            assert "run_oms_recommendation" not in path.read_text(), path
