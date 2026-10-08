"""M6-A telemetry adapter — disabled by default, fake in-memory collector.

D-31 boundary: repository-tracked adapter with disabled-by-default state,
fake in-memory collector for synthetic tests, and no live export.

Telemetry delivery fails open: collector unavailability must not block,
change, retry, falsely succeed, or corrupt a business operation.
Redaction fails closed: if an event cannot be proven safe, that telemetry
event is dropped while the underlying business operation continues.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .telemetry_contract import validate_event_fields
from .telemetry_pseudonym import generate_correlation_id, generate_span_id, generate_trace_id
from .telemetry_redaction import RedactionResult, redact_event


class TelemetrySink(Protocol):
    def emit(self, event: dict[str, Any]) -> None: ...


class InMemorySink:
    """Fake collector for synthetic tests. No network calls."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._closed = False

    def emit(self, event: dict[str, Any]) -> None:
        if self._closed:
            return
        self.events.append(event)

    def close(self) -> None:
        self._closed = True

    def clear(self) -> None:
        self.events.clear()

    @property
    def count(self) -> int:
        return len(self.events)


class NullSink:
    """Discards all events. Used when telemetry is disabled."""

    def emit(self, event: dict[str, Any]) -> None:
        pass


class FailingSink:
    """Simulates a broken collector. Used to prove fail-open delivery."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RuntimeError("collector_unavailable")
        self.emit_count = 0

    def emit(self, event: dict[str, Any]) -> None:
        self.emit_count += 1
        raise self._error


@dataclass
class TelemetryAdapter:
    """Disabled-by-default telemetry adapter.

    - enabled=False (default): no events emitted, no side effects.
    - enabled=True with InMemorySink: events captured for testing.
    - enabled=True with real sink: events emitted after redaction (M6-A
      does not authorize real sinks).
    - sampling_rate=0.0: no events pass sampling (default).
    - sampling_rate=1.0: all events pass (synthetic tests only).
    """

    enabled: bool = False
    sampling_rate: float = 0.0
    sink: TelemetrySink = field(default_factory=NullSink)
    pepper: str = ""
    environment: str = "test"
    service_name: str = "zippy-workers"

    _dropped_redaction: int = field(default=0, init=False)
    _dropped_sampling: int = field(default=0, init=False)
    _dropped_validation: int = field(default=0, init=False)
    _emitted: int = field(default=0, init=False)

    @property
    def dropped_redaction(self) -> int:
        return self._dropped_redaction

    @property
    def dropped_sampling(self) -> int:
        return self._dropped_sampling

    @property
    def dropped_validation(self) -> int:
        return self._dropped_validation

    @property
    def emitted(self) -> int:
        return self._emitted

    def trace(
        self,
        operation: str,
        agent_name: str | None = None,
        task_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _TraceContext:
        if not self.enabled:
            return _TraceContext.noop()
        return _TraceContext(
            adapter=self,
            trace_id=generate_trace_id(),
            correlation_id=generate_correlation_id(),
            operation=operation,
            agent_name=agent_name,
            task_type=task_type,
            metadata=metadata,
        )

    def _try_emit(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return

        import random

        if self.sampling_rate < 1.0 and random.random() > self.sampling_rate:
            self._dropped_sampling += 1
            return

        try:
            result: RedactionResult = redact_event(event)
            if not result.accepted:
                self._dropped_redaction += 1
                return
            ok, violations = validate_event_fields(result.event or {})
        except Exception:
            self._dropped_redaction += 1
            return

        if not ok:
            self._dropped_validation += 1
            return

        try:
            self.sink.emit(result.event or {})
            self._emitted += 1
        except Exception:  # noqa: BLE001 — fail open
            pass


@dataclass
class _TraceContext:
    adapter: TelemetryAdapter | None = None
    trace_id: str = ""
    correlation_id: str = ""
    operation: str = ""
    agent_name: str | None = None
    task_type: str | None = None
    metadata: dict[str, Any] | None = None
    _span_count: int = field(default=0, init=False)

    @staticmethod
    def noop() -> _TraceContext:
        return _TraceContext()

    @property
    def is_noop(self) -> bool:
        return self.adapter is None

    def span(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> _SpanContext:
        if self.is_noop:
            return _SpanContext.noop()
        return _SpanContext(
            adapter=self.adapter,
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            span_id=generate_span_id(),
            name=name,
            metadata=metadata,
            operation=self.operation,
            agent_name=self.agent_name,
            task_type=self.task_type,
        )

    def __enter__(self) -> _TraceContext:
        return self

    def __exit__(self, *exc: Any) -> None:
        pass


@dataclass
class _SpanContext:
    adapter: TelemetryAdapter | None = None
    trace_id: str = ""
    correlation_id: str = ""
    span_id: str = ""
    name: str = ""
    metadata: dict[str, Any] | None = None
    operation: str = ""
    agent_name: str | None = None
    task_type: str | None = None
    _start_ns: int = field(default=0, init=False)

    @staticmethod
    def noop() -> _SpanContext:
        return _SpanContext()

    @property
    def is_noop(self) -> bool:
        return self.adapter is None

    def set_attribute(self, key: str, value: Any) -> None:
        if self.is_noop:
            return
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value

    def __enter__(self) -> _SpanContext:
        if not self.is_noop:
            self._start_ns = time.monotonic_ns()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.is_noop or self.adapter is None:
            return

        elapsed_ms = (time.monotonic_ns() - self._start_ns) // 1_000_000

        event: dict[str, Any] = {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "span_id": self.span_id,
            "service_name": self.adapter.service_name,
            "operation_name": self.operation,
            "timestamp": _now_iso(),
            "start_time": self._start_ns,
            "end_time": time.monotonic_ns(),
            "latency_ms": elapsed_ms,
            "environment": self.adapter.environment,
            "success": exc_type is None,
            "status_code": 0 if exc_type is None else 1,
        }

        if self.agent_name:
            event["agent_name"] = self.agent_name
        if self.task_type:
            event["task_type"] = self.task_type
        if self.name:
            event["event_type"] = self.name

        if exc_type is not None:
            event["error_class"] = exc_type.__name__

        if self.metadata:
            for k, v in self.metadata.items():
                if k not in event:
                    event[k] = v

        self.adapter._try_emit(event)


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.UTC).isoformat()
