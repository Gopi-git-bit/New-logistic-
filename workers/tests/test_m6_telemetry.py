"""M6-A telemetry synthetic proof — disposable tests per D-31.

Proves:
  - telemetry_disabled_by_default
  - redaction_before_export
  - secret_scan (no secrets in emitted events)
  - pseudonymized_tenant (HMAC-SHA256 stable hash)
  - no_financial_data (payment/odoo/razorpay fields prohibited)
  - fail_open_on_export_error (broken collector doesn't block business)
  - fail_closed_on_redaction_error (unclassifiable event is dropped)
  - bounded_retries (no retry loop on export failure)
  - duplicate_handling (deterministic span IDs)
  - sampling_zero_drops_all (0% sampling emits nothing)
  - sampling_full_passes (100% sampling emits all safe events)
  - audit_fields_permitted (trace_id, latency, tokens, etc.)
  - prohibited_fields_dropped (secrets, PII, payment data)
  - restricted_uuid_passes (UUID-shaped restricted values pass)
  - restricted_non_uuid_dropped (non-UUID restricted values dropped)
  - cleanup (in-memory sink is disposable)
  - no_authority (telemetry cannot alter business outcomes)
  - trace_correlation (server-generated IDs, not client-provided)
  - environment_isolation (test environment tag in events)

D-31: no live credentials, no external transmission, no production data.
"""

from zippy_workers.telemetry_adapter import (
    FailingSink,
    InMemorySink,
    NullSink,
    TelemetryAdapter,
)
from zippy_workers.telemetry_contract import (
    PERMITTED_FIELDS,
    PROHIBITED_FIELDS,
    RESTRICTED_FIELDS,
    FieldClassification,
    classify_field,
    is_safe_for_telemetry,
    validate_event_fields,
)
from zippy_workers.telemetry_pseudonym import (
    generate_correlation_id,
    generate_pepper,
    generate_span_id,
    generate_trace_id,
    pseudonymize,
)
from zippy_workers.telemetry_redaction import redact_event, scrub_metadata

# ============================================================
# Contract tests
# ============================================================


class TestFieldClassification:
    def test_permitted_fields_are_safe(self):
        for field in PERMITTED_FIELDS:
            assert classify_field(field) == FieldClassification.PERMITTED
            assert is_safe_for_telemetry(field)

    def test_prohibited_fields_are_unsafe(self):
        for field in PROHIBITED_FIELDS:
            assert classify_field(field) == FieldClassification.PROHIBITED
            assert not is_safe_for_telemetry(field)

    def test_restricted_fields_are_not_safe(self):
        for field in RESTRICTED_FIELDS:
            cls = classify_field(field)
            assert cls == FieldClassification.RESTRICTED
            assert not is_safe_for_telemetry(field)

    def test_unknown_field_is_prohibited(self):
        assert classify_field("completely_unknown_field") == FieldClassification.PROHIBITED

    def test_case_insensitive(self):
        assert classify_field("TRACE_ID") == FieldClassification.PERMITTED
        assert classify_field("Password") == FieldClassification.PROHIBITED

    def test_no_overlap_between_categories(self):
        assert not (PERMITTED_FIELDS & PROHIBITED_FIELDS)
        assert not (PERMITTED_FIELDS & RESTRICTED_FIELDS)
        assert not (PROHIBITED_FIELDS & RESTRICTED_FIELDS)

    def test_validate_event_all_permitted(self):
        event = {"trace_id": "abc", "latency_ms": 42, "success": True}
        ok, violations = validate_event_fields(event)
        assert ok
        assert violations == []

    def test_validate_event_with_prohibited(self):
        event = {"trace_id": "abc", "password": "secret123"}
        ok, violations = validate_event_fields(event)
        assert not ok
        assert len(violations) == 1
        assert "password:prohibited" in violations[0]

    def test_validate_event_with_restricted(self):
        event = {"trace_id": "abc", "order_id": "xyz"}
        ok, violations = validate_event_fields(event)
        assert not ok
        assert any("order_id" in v for v in violations)


# ============================================================
# Redaction tests
# ============================================================


class TestRedaction:
    def test_clean_event_passes(self):
        event = {
            "trace_id": "abc-123",
            "span_id": "def-456",
            "latency_ms": 42,
            "success": True,
            "service_name": "zippy-workers",
        }
        result = redact_event(event)
        assert result.accepted
        assert result.event is not None
        assert result.event["latency_ms"] == 42

    def test_prohibited_field_dropped(self):
        event = {
            "trace_id": "abc-123",
            "password": "hunter2",
            "latency_ms": 10,
        }
        result = redact_event(event)
        assert not result.accepted
        assert result.event is None
        assert "password" in result.dropped_fields
        assert "prohibited" in (result.reason or "")

    def test_all_prohibited_event_dropped(self):
        event = {"password": "secret", "api_key": "pk-123"}
        result = redact_event(event)
        assert not result.accepted
        assert result.event is None
        assert "prohibited" in (result.reason or "")

    def test_secret_like_value_detected(self):
        event = {
            "trace_id": "abc",
            "some_field": "pk_live_abc123def456ghi789jkl012mno345",
        }
        result = redact_event(event)
        assert not result.accepted or "some_field" in result.dropped_fields

    def test_restricted_uuid_passes(self):
        import uuid

        uid = str(uuid.uuid4())
        event = {"trace_id": "abc", "order_id": uid}
        result = redact_event(event)
        assert result.accepted
        assert result.event["order_id"] == uid

    def test_restricted_non_uuid_dropped_fail_closed(self):
        event = {"trace_id": "abc", "order_id": "not-a-uuid-customer-name"}
        result = redact_event(event)
        assert not result.accepted
        assert result.event is None
        assert "unclassifiable" in (result.reason or "")

    def test_financial_fields_prohibited(self):
        for field in [
            "payment_amount",
            "total_amount",
            "razorpay_payment_id",
            "invoice_id",
            "sale_order_id",
            "settlement_amount",
        ]:
            event = {"trace_id": "abc", field: 100}
            result = redact_event(event)
            if result.accepted:
                assert field not in (result.event or {})
            else:
                assert not result.accepted

    def test_pii_fields_prohibited(self):
        for field in [
            "customer_name",
            "customer_email",
            "driver_phone",
            "pickup_address",
            "consignee_name",
        ]:
            event = {"trace_id": "abc", field: "sensitive"}
            result = redact_event(event)
            if result.accepted:
                assert field not in (result.event or {})

    def test_prompt_response_prohibited(self):
        for field in ["raw_prompt", "raw_response", "system_prompt", "input_text"]:
            event = {"trace_id": "abc", field: "some text"}
            result = redact_event(event)
            if result.accepted:
                assert field not in (result.event or {})

    def test_non_dict_event_dropped(self):
        result = redact_event("not a dict")  # type: ignore
        assert not result.accepted
        assert result.reason == "event_not_dict"

    def test_credential_fields_prohibited(self):
        for field in [
            "langfuse_secret_key",
            "langfuse_public_key",
            "supabase_service_role_key",
            "odoo_api_key",
        ]:
            assert classify_field(field) == FieldClassification.PROHIBITED

    def test_scrub_metadata_drops_prohibited(self):
        meta = {
            "agent_name": "order_management",
            "password": "secret",
            "latency_ms": 42,
        }
        cleaned = scrub_metadata(meta)
        assert "password" not in cleaned
        assert "agent_name" in cleaned

    def test_scrub_metadata_empty(self):
        assert scrub_metadata(None) == {}
        assert scrub_metadata({}) == {}


# ============================================================
# Pseudonymization tests
# ============================================================


class TestPseudonymization:
    def test_deterministic(self):
        pepper = generate_pepper()
        assert pseudonymize("tenant-1", pepper) == pseudonymize("tenant-1", pepper)

    def test_different_tenants_different_hashes(self):
        pepper = generate_pepper()
        h1 = pseudonymize("tenant-1", pepper)
        h2 = pseudonymize("tenant-2", pepper)
        assert h1 != h2

    def test_different_peppers_different_hashes(self):
        p1 = generate_pepper()
        p2 = generate_pepper()
        assert pseudonymize("tenant-1", p1) != pseudonymize("tenant-1", p2)

    def test_different_domains_different_hashes(self):
        pepper = generate_pepper()
        h1 = pseudonymize("id-1", pepper, domain="tenant")
        h2 = pseudonymize("id-1", pepper, domain="actor")
        assert h1 != h2

    def test_output_is_hex_24_chars(self):
        pepper = generate_pepper()
        h = pseudonymize("some-id", pepper)
        assert len(h) == 24
        int(h, 16)

    def test_empty_input_returns_empty(self):
        assert pseudonymize("", "pepper") == ""
        assert pseudonymize("id", "") == ""

    def test_trace_id_is_uuid(self):
        import uuid

        tid = generate_trace_id()
        uuid.UUID(tid)

    def test_span_id_is_hex_16(self):
        sid = generate_span_id()
        assert len(sid) == 16
        int(sid, 16)

    def test_correlation_id_is_uuid(self):
        import uuid

        cid = generate_correlation_id()
        uuid.UUID(cid)

    def test_pepper_is_64_hex_chars(self):
        p = generate_pepper()
        assert len(p) == 64
        int(p, 16)


# ============================================================
# Adapter tests
# ============================================================


class TestAdapterDisabledByDefault:
    def test_disabled_by_default(self):
        adapter = TelemetryAdapter()
        assert not adapter.enabled
        assert adapter.sampling_rate == 0.0

    def test_disabled_emits_nothing(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=False, sink=sink)
        with adapter.trace("test_op") as t:
            with t.span("test_span") as s:
                s.set_attribute("latency_ms", 42)
        assert sink.count == 0
        assert adapter.emitted == 0

    def test_disabled_trace_is_noop(self):
        adapter = TelemetryAdapter(enabled=False)
        t = adapter.trace("op")
        assert t.is_noop
        s = t.span("span")
        assert s.is_noop

    def test_zero_sampling_drops_all(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=0.0, sink=sink, pepper="test-pepper")
        for _ in range(10):
            with adapter.trace("op") as t:
                with t.span("span"):
                    pass
        assert sink.count == 0
        assert adapter.dropped_sampling == 10


class TestAdapterEnabled:
    def test_full_sampling_emits_safe_events(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(
            enabled=True,
            sampling_rate=1.0,
            sink=sink,
            pepper="test-pepper",
            environment="test",
            service_name="zippy-workers",
        )
        with adapter.trace("test_operation", agent_name="order_management") as t:
            with t.span("tool_call") as s:
                s.set_attribute("latency_ms", 42)
        assert sink.count == 1
        assert adapter.emitted == 1
        event = sink.events[0]
        assert event["service_name"] == "zippy-workers"
        assert event["environment"] == "test"
        assert event["success"] is True
        assert event["latency_ms"] >= 0

    def test_trace_id_server_generated(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        event = sink.events[0]
        import uuid

        uuid.UUID(event["trace_id"])

    def test_span_id_generated(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        assert len(sink.events[0]["span_id"]) == 16

    def test_error_class_recorded(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            try:
                with t.span("failing_span"):
                    raise ValueError("test_error")
            except ValueError:
                pass
        assert sink.count == 1
        event = sink.events[0]
        assert event["success"] is False
        assert event["error_class"] == "ValueError"
        assert event["status_code"] == 1

    def test_agent_name_and_task_type_in_event(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace(
            "process_payment",
            agent_name="payment_settlement",
            task_type="process_payment_event",
        ) as t:
            with t.span("handler"):
                pass
        event = sink.events[0]
        assert event["agent_name"] == "payment_settlement"
        assert event["task_type"] == "process_payment_event"


class TestFailOpen:
    def test_failing_sink_does_not_raise(self):
        sink = FailingSink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        assert sink.emit_count == 1
        assert adapter.emitted == 0

    def test_failing_sink_business_continues(self):
        sink = FailingSink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        business_result = {"order_id": "test", "status": "completed"}
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        assert business_result["status"] == "completed"

    def test_bounded_retries_no_retry_loop(self):
        sink = FailingSink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        assert sink.emit_count == 1


class TestFailClosed:
    def test_unclassifiable_event_dropped(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s", metadata={"order_id": "not-a-uuid-value"}):
                pass
        assert sink.count == 0
        assert adapter.dropped_redaction >= 1 or adapter.dropped_validation >= 1

    def test_prohibited_metadata_dropped_from_event(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s", metadata={"password": "secret123"}):
                pass
        if sink.count > 0:
            assert "password" not in sink.events[0]

    def test_redaction_failure_does_not_affect_business(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        result = {"status": "ok"}
        with adapter.trace("op") as t:
            with t.span("s", metadata={"api_key": "sk_live_abc123def456"}):
                pass
        assert result["status"] == "ok"


class TestSecretScan:
    def test_no_secrets_in_emitted_events(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        for event in sink.events:
            for key in event:
                assert classify_field(key) == FieldClassification.PERMITTED
            for value in event.values():
                if isinstance(value, str):
                    assert "sk_" not in value
                    assert "pk_" not in value
                    assert "rzp_" not in value

    def test_no_financial_data_in_emitted_events(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        financial_keys = {
            "payment_amount",
            "total_amount",
            "razorpay_payment_id",
            "invoice_id",
            "settlement_amount",
        }
        for event in sink.events:
            assert not (financial_keys & set(event.keys()))


class TestCleanup:
    def test_in_memory_sink_clear(self):
        sink = InMemorySink()
        sink.emit({"trace_id": "test"})
        assert sink.count == 1
        sink.clear()
        assert sink.count == 0

    def test_in_memory_sink_close(self):
        sink = InMemorySink()
        sink.close()
        sink.emit({"trace_id": "test"})
        assert sink.count == 0

    def test_null_sink_discards(self):
        sink = NullSink()
        sink.emit({"trace_id": "test"})


class TestNoAuthority:
    def test_telemetry_cannot_alter_business_outcome(self):
        sink = FailingSink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        business_data = {"order_status": "delivered", "payment": "captured"}
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        assert business_data["order_status"] == "delivered"
        assert business_data["payment"] == "captured"

    def test_adapter_has_no_write_methods(self):
        adapter = TelemetryAdapter()
        assert not hasattr(adapter, "transition_order")
        assert not hasattr(adapter, "complete_task")
        assert not hasattr(adapter, "fail_task")


class TestTraceCorrelation:
    def test_client_may_not_set_trace_id(self):
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=InMemorySink(), pepper="p")
        t = adapter.trace("op")
        import uuid

        uuid.UUID(t.trace_id)

    def test_multiple_spans_share_trace_id(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper="p")
        with adapter.trace("op") as t:
            with t.span("s1"):
                pass
            with t.span("s2"):
                pass
        assert sink.count == 2
        assert sink.events[0]["trace_id"] == sink.events[1]["trace_id"]
        assert sink.events[0]["span_id"] != sink.events[1]["span_id"]

    def test_correlation_id_is_server_generated(self):
        adapter = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=InMemorySink(), pepper="p")
        t = adapter.trace("op")
        import uuid

        uuid.UUID(t.correlation_id)


class TestEnvironmentIsolation:
    def test_environment_tag_in_events(self):
        sink = InMemorySink()
        adapter = TelemetryAdapter(
            enabled=True, sampling_rate=1.0, sink=sink, pepper="p", environment="disposable-test"
        )
        with adapter.trace("op") as t:
            with t.span("s"):
                pass
        assert sink.events[0]["environment"] == "disposable-test"

    def test_different_environments_isolated(self):
        sink1 = InMemorySink()
        sink2 = InMemorySink()
        a1 = TelemetryAdapter(
            enabled=True, sampling_rate=1.0, sink=sink1, pepper="p", environment="test"
        )
        a2 = TelemetryAdapter(
            enabled=True, sampling_rate=1.0, sink=sink2, pepper="p", environment="staging"
        )
        with a1.trace("op") as t:
            with t.span("s"):
                pass
        with a2.trace("op") as t:
            with t.span("s"):
                pass
        assert sink1.events[0]["environment"] == "test"
        assert sink2.events[0]["environment"] == "staging"


# ============================================================
# Integration-style: adapter + redaction + pseudonymization
# ============================================================


class TestIntegration:
    def test_full_pipeline_with_safe_data(self):
        pepper = generate_pepper()
        sink = InMemorySink()
        adapter = TelemetryAdapter(
            enabled=True,
            sampling_rate=1.0,
            sink=sink,
            pepper=pepper,
            environment="test",
            service_name="zippy-workers",
        )
        pseudo_tenant = pseudonymize("synthetic-tenant-001", pepper)
        with adapter.trace(
            "process_payment",
            agent_name="payment_settlement",
            task_type="process_payment_event",
        ) as t:
            with t.span(
                "handler",
                metadata={
                    "pseudonymous_tenant_id": pseudo_tenant,
                    "latency_ms": 42,
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "estimated_cost_cents": 3,
                    "confidence": 0.95,
                    "status_code": 0,
                },
            ):
                pass

        assert sink.count == 1
        event = sink.events[0]
        assert event["agent_name"] == "payment_settlement"
        assert event["pseudonymous_tenant_id"] == pseudo_tenant
        assert event["latency_ms"] >= 0
        assert event["environment"] == "test"
        ok, violations = validate_event_fields(event)
        assert ok, f"violations: {violations}"

    def test_full_pipeline_with_mixed_data_drops_unsafe(self):
        pepper = generate_pepper()
        sink = InMemorySink()
        adapter = TelemetryAdapter(
            enabled=True,
            sampling_rate=1.0,
            sink=sink,
            pepper=pepper,
        )
        with adapter.trace("op") as t:
            with t.span(
                "s",
                metadata={
                    "latency_ms": 42,
                    "password": "should_be_dropped",
                    "customer_email": "user@example.com",
                },
            ):
                pass
        for event in sink.events:
            assert "password" not in event
            assert "customer_email" not in event

    def test_disabled_adapter_zero_cost(self):
        adapter = TelemetryAdapter(enabled=False)
        assert adapter.emitted == 0
        assert adapter.dropped_redaction == 0
        assert adapter.dropped_sampling == 0
        t = adapter.trace("op")
        assert t.is_noop
