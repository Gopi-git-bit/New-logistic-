"""One-request OpenAI-compatible adapter; no runtime registration or environment loading."""

from __future__ import annotations

import asyncio
import json
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import SecretStr

from .recommendations import RecommendationRequest

CONFIG_NAMES = (
    "OMS_STAGING_ENDPOINT",
    "OMS_STAGING_API_KEY",
    "OMS_STAGING_MODEL",
    "OMS_STAGING_TIMEOUT_SECONDS",
    "OMS_STAGING_MAX_OUTPUT_TOKENS",
)
SAFE_ENV_NAMES = frozenset(
    {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "LANG", "LC_ALL", "SYSTEMROOT"}
)
MAX_RESPONSE_BYTES = 16_384
MAX_CANDIDATES = 16


class StagingConfigurationError(ValueError):
    pass


class ProviderResponseError(ValueError):
    pass


class ProviderCleanupError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderSettings:
    endpoint: str = field(repr=False)
    api_key: SecretStr = field(repr=False)
    model: str = field(repr=False)
    timeout_seconds: float
    max_output_tokens: int

    def __post_init__(self) -> None:
        if len(self.endpoint) > 2048:
            raise StagingConfigurationError("INVALID_OMS_STAGING_ENDPOINT")
        try:
            url = httpx.URL(self.endpoint)
        except httpx.InvalidURL:
            raise StagingConfigurationError("INVALID_OMS_STAGING_ENDPOINT") from None
        if (
            url.scheme != "https"
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or url.path == "/"
        ):
            raise StagingConfigurationError("INVALID_OMS_STAGING_ENDPOINT")
        for name, value in (
            ("MODEL", self.model),
            ("API_KEY", self.api_key.get_secret_value()),
        ):
            if (
                not value
                or len(value) > (256 if name == "MODEL" else 2048)
                or value != value.strip()
                or any(ord(c) < 33 or ord(c) > 126 for c in value)
            ):
                raise StagingConfigurationError(f"INVALID_OMS_STAGING_{name}")
        if (
            type(self.timeout_seconds) not in (float, int)
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 10
        ):
            raise StagingConfigurationError("INVALID_OMS_STAGING_TIMEOUT_SECONDS")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 256:
            raise StagingConfigurationError("INVALID_OMS_STAGING_MAX_OUTPUT_TOKENS")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> ProviderSettings:
        if set(environment) - set(CONFIG_NAMES) - SAFE_ENV_NAMES:
            raise StagingConfigurationError("ISOLATION_VIOLATION")
        for name in CONFIG_NAMES:
            if not environment.get(name):
                raise StagingConfigurationError(f"MISSING_{name}")
        try:
            timeout = float(environment["OMS_STAGING_TIMEOUT_SECONDS"])
            tokens = int(environment["OMS_STAGING_MAX_OUTPUT_TOKENS"])
        except ValueError:
            raise StagingConfigurationError("INVALID_OMS_STAGING_LIMITS") from None
        return cls(
            environment["OMS_STAGING_ENDPOINT"],
            SecretStr(environment["OMS_STAGING_API_KEY"]),
            environment["OMS_STAGING_MODEL"],
            timeout,
            tokens,
        )


ProviderOutcome = Literal[
    "NOT_CALLED",
    "RESPONSE_RECEIVED",
    "MALFORMED_RESPONSE",
    "RESPONSE_TOO_LARGE",
    "RATE_LIMITED",
    "HTTP_REJECTED",
    "UNAVAILABLE",
    "TIMEOUT",
    "CANCELLED",
]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE")
        result[key] = value
    return result


def _decode_json(data: str | bytes) -> object:
    try:
        value: object = json.loads(data, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError):
        raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE") from None
    return value


def _ranking_content(body: bytes) -> object:
    envelope = _decode_json(body)
    if not isinstance(envelope, dict):
        raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE")
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE")
    choice = choices[0]
    message = choice.get("message")
    if (
        choice.get("finish_reason") != "stop"
        or not isinstance(message, dict)
        or message.get("role") != "assistant"
        or message.get("tool_calls")
        or message.get("function_call")
        or message.get("refusal")
        or not isinstance(message.get("content"), str)
    ):
        raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE")
    return _decode_json(message["content"])


class OpenAIRecommendationAgent:
    def __init__(
        self,
        settings: ProviderSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.requests_started = 0
        self.outcome: ProviderOutcome = "NOT_CALLED"
        self._active: asyncio.Task[object] | None = None
        self._response: httpx.Response | None = None
        self._deadline: float | None = None
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        )

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    async def rank(self, request: RecommendationRequest) -> object:
        if self.requests_started or self.is_closed:
            raise RuntimeError("PROVIDER_REQUEST_LIMIT")
        if len(request.candidates) > MAX_CANDIDATES:
            raise ValueError("PROVIDER_INPUT_LIMIT")
        self._deadline = asyncio.get_running_loop().time() + self.settings.timeout_seconds
        if tuple(candidate.candidate_id for candidate in request.candidates) != tuple(
            f"candidate-{index}" for index in range(len(request.candidates))
        ):
            raise ValueError("PROVIDER_INPUT_REFERENCES")
        for candidate in request.candidates:
            for feature in (candidate.distance_m, candidate.score):
                if feature is not None:
                    try:
                        valid = type(feature) in (int, float) and math.isfinite(feature)
                    except OverflowError:
                        valid = False
                    if not valid:
                        raise ValueError("PROVIDER_INPUT_FEATURES")
        payload = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only a JSON object with candidate_ids: a complete permutation "
                        "of the supplied candidate references. Rank using only distance_m "
                        "and score. Do not call tools or propose mutations."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        [
                            {
                                "candidate_id": candidate.candidate_id,
                                "distance_m": (
                                    float(candidate.distance_m)
                                    if candidate.distance_m is not None
                                    else None
                                ),
                                "score": (
                                    float(candidate.score) if candidate.score is not None else None
                                ),
                            }
                            for candidate in request.candidates
                        ],
                        allow_nan=False,
                    ),
                },
            ],
        }
        body = json.dumps(payload, allow_nan=False).encode()
        if len(body) > 4096:
            raise ValueError("PROVIDER_INPUT_LIMIT")
        self.requests_started += 1
        self._active = asyncio.current_task()
        try:
            # Reserve half the single run budget for cancellation and resource cleanup.
            async with asyncio.timeout_at(self._deadline - self.settings.timeout_seconds / 2):
                http_request = self._client.build_request(
                    "POST",
                    self.settings.endpoint,
                    content=body,
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                        "X-Correlation-ID": str(uuid.uuid4()),
                        "X-Agent-ID": "order_management",
                        "X-Request-Timestamp": datetime.now(UTC).isoformat(),
                    },
                )
                response = await self._client.send(http_request, stream=True)
                self._response = response
                if response.status_code == 429:
                    self.outcome = "RATE_LIMITED"
                    # No retry or sleep: the finite run stops, including with Retry-After.
                    raise ConnectionError("PROVIDER_RATE_LIMITED")
                if response.status_code != 200:
                    self.outcome = "HTTP_REJECTED"
                    raise ConnectionError("PROVIDER_HTTP_REJECTED")
                if response.headers.get("Content-Encoding", "").strip().lower() not in (
                    "",
                    "identity",
                ):
                    raise ProviderResponseError("PROVIDER_UNSUPPORTED_ENCODING")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if not length.isascii() or not length.isdigit():
                        raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE")
                    if len(length) > 10 or int(length) > MAX_RESPONSE_BYTES:
                        self.outcome = "RESPONSE_TOO_LARGE"
                        raise ProviderResponseError("PROVIDER_RESPONSE_TOO_LARGE")
                data = bytearray()
                # Raw iteration avoids HTTPX's decoder/chunker buffering before our cap.
                if not isinstance(response.stream, httpx.AsyncByteStream):
                    raise ProviderResponseError("PROVIDER_MALFORMED_RESPONSE")
                async for chunk in response.stream:
                    if len(chunk) > MAX_RESPONSE_BYTES - len(data):
                        self.outcome = "RESPONSE_TOO_LARGE"
                        raise ProviderResponseError("PROVIDER_RESPONSE_TOO_LARGE")
                    data.extend(chunk)
                output = _ranking_content(bytes(data))
                self.outcome = "RESPONSE_RECEIVED"
                return output
        except (TimeoutError, httpx.TimeoutException):
            self.outcome = "TIMEOUT"
            raise TimeoutError("PROVIDER_TIMEOUT") from None
        except httpx.RequestError:
            self.outcome = "UNAVAILABLE"
            raise ConnectionError("PROVIDER_UNAVAILABLE") from None
        except ProviderResponseError:
            if self.outcome != "RESPONSE_TOO_LARGE":
                self.outcome = "MALFORMED_RESPONSE"
            raise
        except asyncio.CancelledError:
            self.outcome = "CANCELLED"
            raise
        finally:
            self._active = None

    async def aclose(self) -> None:
        deadline = self._deadline
        if deadline is None:
            deadline = asyncio.get_running_loop().time() + self.settings.timeout_seconds
        operations = [self._client.aclose()]
        if self._response is not None:
            operations.append(self._response.aclose())
        close_count = len(operations)
        if self._active is not None:
            task = self._active
            task.cancel()

            # Closing the client must not depend on a stalled request draining first.
            async def drain() -> None:
                await asyncio.gather(task, return_exceptions=True)

            operations.append(drain())
        try:
            async with asyncio.timeout_at(deadline):
                results = await asyncio.gather(*operations, return_exceptions=True)
        except TimeoutError:
            raise ProviderCleanupError("PROVIDER_CLEANUP_FAILURE") from None
        if any(isinstance(result, BaseException) for result in results[:close_count]):
            raise ProviderCleanupError("PROVIDER_CLEANUP_FAILURE") from None
