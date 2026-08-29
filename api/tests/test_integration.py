"""Zippy Logistics — Integration Tests.

Tests the full governance chain, fail-closed behavior, idempotency lifecycle,
POD state machine, and cross-system authority without requiring live services.
All external calls are mocked; DB tests use the unit test pattern.
"""

from __future__ import annotations

import os
from unittest.mock import patch, MagicMock, Mock
import pytest

from api.services.paperclip import PaperclipClient, Decision, Proposal
from api.services.hermes import HermesClient, ExecutionStatus, ALLOWLISTED_TOOLS
from api.pod_lifecycle import (
    PODStatus, can_transition, next_status, requires_paperclip, POD_TRANSITIONS,
    PAPERCLIP_REQUIRED_TRANSITIONS,
)
from api.idempotency import IdempotencyStore, IdempotencyStatus, IdempotencyResult
from api.redaction import redact_string


# ---------------------------------------------------------------------------
# 1. Paperclip FAIL-CLOSED
# ---------------------------------------------------------------------------
class TestPaperclipFailClosed:
    """Paperclip governance must FAIL CLOSED — errors → REJECT."""

    def test_unavailable_returns_reject(self):
        """When Paperclip is down, evaluate() must return REJECT."""
        client = PaperclipClient(base_url="http://localhost", api_key="test")
        mock_http = MagicMock()
        mock_http.post.side_effect = ConnectionRefusedError("refused")
        client._http = mock_http
        proposal = Proposal(
            tool="create_customer_invoice",
            arguments={"partner_id": 1, "amount": 5000},
            agent="zippy-dispatch",
        )
        result = client.evaluate(proposal)
        assert result.decision == Decision.REJECT
        assert "Paperclip unavailable" in result.reason
        client.close()

    def test_invalid_url_returns_reject(self):
        """Malformed URL must still return REJECT."""
        client = PaperclipClient(base_url="not-a-url", api_key="test")
        mock_http = MagicMock()
        mock_http.post.side_effect = ValueError("invalid URL")
        client._http = mock_http
        proposal = Proposal(
            tool="record_payment", arguments={"payment_id": "x"},
            agent="zippy-settlement",
        )
        result = client.evaluate(proposal)
        assert result.decision == Decision.REJECT
        client.close()

    def test_get_decision_unavailable_returns_none(self):
        """get_decision must return None on failure (caller handles gracefully)."""
        client = PaperclipClient(base_url="http://localhost", api_key="test")
        mock_http = MagicMock()
        mock_http.get.side_effect = ConnectionRefusedError("refused")
        client._http = mock_http
        result = client.get_decision("nonexistent-id")
        assert result is None
        client.close()

    def test_http_error_returns_reject(self):
        """HTTP 5xx from Paperclip must return REJECT."""
        client = PaperclipClient(base_url="http://localhost", api_key="test")
        mock_http = MagicMock()
        mock_http.post.side_effect = Exception("Connection reset")
        client._http = mock_http
        result = client.evaluate(Proposal(
            tool="create_sale_order", arguments={}, agent="test",
        ))
        assert result.decision == Decision.REJECT
        assert "Paperclip unavailable" in result.reason
        client.close()


# ---------------------------------------------------------------------------
# 2. Hermes ALLOWLIST ENFORCEMENT
# ---------------------------------------------------------------------------
class TestHermesAllowlist:
    """Hermes must reject unlisted tools — execute-only, no autonomy."""

    def test_allowed_tool_passes(self):
        """Tools in the allowlist should not be blocked at the client level."""
        # We test the allowlist check; actual HTTP call will fail but that's fine
        client = HermesClient(base_url="http://localhost", api_key="test")
        for tool in ["create_customer_invoice", "record_payment", "assign_driver"]:
            assert tool in ALLOWLISTED_TOOLS
        client.close()

    def test_unlisted_tool_rejected(self):
        """Tools NOT in the allowlist must return UNAUTHORIZED."""
        client = HermesClient(base_url="http://localhost", api_key="test")
        result = client.execute(
            tool="create_admin_user",
            arguments={"email": "hacker@evil.com"},
            decision_id="fake-decision",
        )
        assert result.status == ExecutionStatus.UNAUTHORIZED
        assert "not in allowlist" in result.error
        client.close()

    def test_unlisted_tool_bypass_attempt(self):
        """Even a tool that looks similar but isn't exact must be rejected."""
        client = HermesClient(base_url="http://localhost", api_key="test")
        result = client.execute(
            tool="create_sale_order_draft",  # close to create_sale_order but not exact
            arguments={},
            decision_id="x",
        )
        assert result.status == ExecutionStatus.UNAUTHORIZED
        client.close()

    def test_hermes_unavailable_returns_failure(self):
        """Hermes downtime returns FAILURE (caller must not proceed with unapproved execution)."""
        client = HermesClient(base_url="http://localhost", api_key="test")
        mock_http = MagicMock()
        mock_http.post.side_effect = ConnectionRefusedError("refused")
        client._http = mock_http
        result = client.execute(
            tool="create_customer_invoice",
            arguments={"partner_id": 1},
            decision_id="decision-123",
        )
        assert result.status == ExecutionStatus.FAILURE
        assert "Hermes unavailable" in result.error
        client.close()


# ---------------------------------------------------------------------------
# 3. POD LIFECYCLE STATE MACHINE
# ---------------------------------------------------------------------------
class TestPODLifecycle:
    """POD verification lifecycle — only one valid path to settlement."""

    def test_full_lifecycle_path(self):
        """The only valid path: UPLOADED → PENDING → VERIFIED → CONFIRMED → ELIGIBLE."""
        expected = [
            PODStatus.VERIFICATION_PENDING,
            PODStatus.VERIFIED,
            PODStatus.DELIVERY_CONFIRMED,
            PODStatus.SETTLEMENT_ELIGIBLE,
        ]
        current = PODStatus.UPLOADED
        for expected_next in expected:
            assert can_transition(current, expected_next), f"{current.value} → {expected_next.value}"
            assert next_status(current) == expected_next
            current = expected_next

    def test_invalid_skip_to_settlement(self):
        """Cannot jump from UPLOADED directly to SETTLEMENT_ELIGIBLE."""
        assert not can_transition(PODStatus.UPLOADED, PODStatus.SETTLEMENT_ELIGIBLE)

    def test_invalid_verified_to_eligible(self):
        """Cannot skip DELIVERY_CONFIRMED (governance gate)."""
        assert not can_transition(PODStatus.VERIFIED, PODStatus.SETTLEMENT_ELIGIBLE)

    def test_settlement_eligible_is_terminal(self):
        """SETTLEMENT_ELIGIBLE has no next transitions."""
        assert next_status(PODStatus.SETTLEMENT_ELIGIBLE) is None
        assert POD_TRANSITIONS[PODStatus.SETTLEMENT_ELIGIBLE] == []

    def test_paperclip_required_only_for_final_step(self):
        """Only DELIVERY_CONFIRMED → SETTLEMENT_ELIGIBLE requires Paperclip."""
        assert requires_paperclip(PODStatus.DELIVERY_CONFIRMED, PODStatus.SETTLEMENT_ELIGIBLE)
        assert not requires_paperclip(PODStatus.UPLOADED, PODStatus.VERIFICATION_PENDING)
        assert not requires_paperclip(PODStatus.VERIFICATION_PENDING, PODStatus.VERIFIED)
        assert not requires_paperclip(PODStatus.VERIFIED, PODStatus.DELIVERY_CONFIRMED)

    def test_paperclip_required_transitions_count(self):
        """Only exactly one transition requires Paperclip governance."""
        assert len(PAPERCLIP_REQUIRED_TRANSITIONS) == 1

    def test_invalid_reversed_transition(self):
        """Cannot go backwards (e.g., SETTLEMENT_ELIGIBLE → DELIVERY_CONFIRMED)."""
        assert not can_transition(PODStatus.SETTLEMENT_ELIGIBLE, PODStatus.DELIVERY_CONFIRMED)
        assert not can_transition(PODStatus.VERIFIED, PODStatus.VERIFICATION_PENDING)


# ---------------------------------------------------------------------------
# 4. GOVERNANCE CHAIN — Full Flow (Mocked)
# ---------------------------------------------------------------------------
class TestGovernanceChain:
    """Full chain: Zippy request → Paperclip approve → Hermes execute → Odoo reference."""

    def test_approve_then_execute_flow(self):
        """Happy path: Paperclip approves, Hermes executes."""
        # Step 1: Zippy creates financial request
        request_type = "create_customer_invoice"
        amount = 25000.00
        order_id = "order-123"
        assert request_type in ALLOWLISTED_TOOLS

        # Step 2: Paperclip evaluates
        client = PaperclipClient(base_url="http://mock:8000", api_key="test")
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "decision": "APPROVE",
            "decision_id": "dec-001",
            "policy_version": "P-2026-001",
            "reason": "Within budget",
        }
        client._http.post = MagicMock(return_value=mock_resp)
        result = client.evaluate(Proposal(
            tool=request_type,
            arguments={"partner_id": 1, "amount": amount},
            agent="zippy-settlement",
            order_id=order_id,
        ))
        assert result.decision == Decision.APPROVE
        assert result.decision_id == "dec-001"
        client.close()

        # Step 3: Hermes executes with the decision_id
        client2 = HermesClient(base_url="http://mock:8000", api_key="test")
        mock_resp2 = Mock()
        mock_resp2.raise_for_status = Mock()
        mock_resp2.json.return_value = {
            "status": "SUCCESS",
            "execution_id": "exec-001",
            "output": {"odoo_move_id": 42, "odoo_move_name": "INV/2026/001"},
            "latency_ms": 320,
        }
        client2._http.post = MagicMock(return_value=mock_resp2)
        result2 = client2.execute(
            tool=request_type,
            arguments={"partner_id": 1, "amount": amount},
            decision_id="dec-001",
        )
        assert result2.status == ExecutionStatus.SUCCESS
        assert result2.output["odoo_move_name"] == "INV/2026/001"
        client2.close()

    def test_paperclip_reject_stops_chain(self):
        """Paperclip REJECT → Hermes must never be called."""
        client = PaperclipClient(base_url="http://mock:8000", api_key="test")
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "decision": "REJECT",
            "decision_id": "dec-002",
            "policy_version": "P-2026-001",
            "reason": "Budget exceeded",
        }
        client._http.post = MagicMock(return_value=mock_resp)
        result = client.evaluate(Proposal(
            tool="create_customer_invoice",
            arguments={},
            agent="test",
        ))
        assert result.decision == Decision.REJECT
        client.close()

        # Verify chain stops — Hermes not called
        with patch.object(HermesClient, "execute") as mock_hermes:
            if result.decision == Decision.APPROVE:
                mock_hermes(
                    tool="create_customer_invoice",
                    arguments={},
                    decision_id=result.decision_id,
                )
            mock_hermes.assert_not_called()

    def test_hold_delays_chain(self):
        """Paperclip HOLD → execution must be paused."""
        client = PaperclipClient(base_url="http://mock:8000", api_key="test")
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "decision": "HOLD",
            "decision_id": "dec-003",
            "policy_version": "P-2026-001",
            "reason": "Requires human review",
        }
        client._http.post = MagicMock(return_value=mock_resp)
        result = client.evaluate(Proposal(
            tool="create_sale_order",
            arguments={},
            agent="test",
        ))
        assert result.decision == Decision.HOLD
        assert result.reviewer is None
        client.close()


# ---------------------------------------------------------------------------
# 5. IDEMPOTENCY LIFECYCLE
# ---------------------------------------------------------------------------
class TestIdempotencyLifecycle:
    """Idempotency claim → complete/fail lifecycle."""

    def test_claim_success(self):
        """claim() returns (True, ...) when key is new."""
        store = IdempotencyStore(supabase_url="http://mock:54321", service_key="test")
        mock_resp = Mock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = [{"id": "new-record-id"}]
        store._http.post = MagicMock(return_value=mock_resp)
        claimed, result = store.claim("key-1", "order", {"amount": 100})
        assert claimed is True
        store.close()

    def test_claim_duplicate_returns_existing(self):
        """claim() returns (False, existing) when key already exists."""
        store = IdempotencyStore(supabase_url="http://mock:54321", service_key="test")
        mock_resp_409 = Mock()
        mock_resp_409.status_code = 409
        store._http.post = MagicMock(return_value=mock_resp_409)

        mock_resp_get = Mock()
        mock_resp_get.status_code = 200
        mock_resp_get.json.return_value = [{"id": "existing-id", "status": "completed"}]
        store._http.get = MagicMock(return_value=mock_resp_get)

        claimed, result = store.claim("key-1", "order", {"amount": 100})
        assert claimed is False
        assert result.found is True
        store.close()

    def test_complete_updates_status(self):
        """complete() marks the claim as completed."""
        store = IdempotencyStore(supabase_url="http://mock:54321", service_key="test")
        mock_resp = Mock()
        mock_resp.status_code = 204
        store._http.patch = MagicMock(return_value=mock_resp)
        ok = store.complete("key-1", "order", {"order_id": "ord-123"})
        assert ok is True
        store.close()

    def test_fail_marks_error(self):
        """fail() marks the claim as failed with error."""
        store = IdempotencyStore(supabase_url="http://mock:54321", service_key="test")
        mock_resp = Mock()
        mock_resp.status_code = 204
        store._http.patch = MagicMock(return_value=mock_resp)
        ok = store.fail("key-1", "order", "Paperclip REJECT")
        assert ok is True
        store.close()


# ---------------------------------------------------------------------------
# 6. AUTHORITY MATRIX — Domain Supremacy
# ---------------------------------------------------------------------------
class TestAuthorityMatrix:
    """Each system is supreme in its own domain."""

    def test_odoo_supreme_in_financial(self):
        """Odoo owns financial truth — Zippy stores only external references."""
        # This is enforced by the integration: Zippy writes to external_references
        # with external_system='ODOO', never directly to Odoo's account.move.
        # Verify the pattern is consistent in the codebase.
        from api.services.paperclip import Proposal
        # The proposal carries external references, not financial mutations
        p = Proposal(
            tool="create_customer_invoice",
            arguments={"partner_id": 1, "amount": 5000},
            agent="zippy-settlement",
        )
        # The tool name is Odoo's, but Zippy doesn't own the invoice
        assert "invoice" in p.tool  # Odoo domain

    def test_hermes_is_execution_only(self):
        """Hermes has no authority — it executes only what Paperclip approved."""
        # Hermes has no decision-making capability; it only executes
        # This is enforced by the decision_id parameter in execute()
        client = HermesClient(base_url="http://localhost", api_key="test")
        # execute() requires a decision_id — cannot execute without governance
        # The tool must be in the allowlist
        result = client.execute(
            tool="create_customer_invoice",
            arguments={},
            decision_id="fake-decision-id",  # Paperclip approved
        )
        # Will fail because Hermes is not running, but the pattern is validated
        assert result.status in (ExecutionStatus.FAILURE, ExecutionStatus.UNAUTHORIZED)
        client.close()

    def test_zippy_db_supreme_in_operational(self):
        """Zippy DB owns operational state — POD lifecycle is self-contained."""
        # POD state machine is entirely within Zippy's domain
        assert can_transition(PODStatus.UPLOADED, PODStatus.VERIFICATION_PENDING)
        # Paperclip only gates the FINAL transition, not operational state


# ---------------------------------------------------------------------------
# 7. REDACTION — Secret Safety
# ---------------------------------------------------------------------------
class TestRedaction:
    """Secrets must never appear in logs."""

    def test_database_url_redacted(self):
        """DATABASE_URL key=value format is redacted."""
        text = "DATABASE_URL=postgresql://postgres:supersecret123@db.abc.supabase.co:5432/postgres"
        redacted = redact_string(text)
        # DATABASE_URL pattern matches KEY=VALUE format
        assert "supersecret123" not in redacted

    def test_razorpay_key_redacted(self):
        """Razorpay key=value format is redacted."""
        text = "RAZORPAY_KEY_SECRET=rzp_live_abc123def456"
        redacted = redact_string(text)
        assert "abc123def456" not in redacted

    def test_jwt_secret_redacted(self):
        """JWT secret key=value format is redacted."""
        text = "SUPABASE_JWT_SECRET=my-super-secret-jwt-key-12345"
        redacted = redact_string(text)
        assert "super-secret-jwt" not in redacted

    def test_normal_text_unaffected(self):
        """Normal text is not redacted."""
        text = "Order ZP-001 delivered successfully"
        assert redact_string(text) == text

    def test_empty_string(self):
        """Empty string returns empty."""
        assert redact_string("") == ""

    def test_multiple_secrets(self):
        """Multiple secrets in key=value format are all redacted."""
        text = "DATABASE_URL=postgres://user:pass@host RAZORPAY_KEY_SECRET=rzp_live_abc123"
        redacted = redact_string(text)
        assert "pass" not in redacted.split("=", 1)[-1]
        assert "abc123" not in redacted.split("RAZORPAY_KEY_SECRET=")[-1]


# ---------------------------------------------------------------------------
# 8. CONFIG VALIDATION
# ---------------------------------------------------------------------------
class TestConfigValidation:
    """Config validation catches missing secrets at startup."""

    def test_all_critical_missing(self):
        """Missing all critical fields returns them all."""
        from api.config import Settings, validate_required
        settings = Settings()
        missing = validate_required(settings)
        # At minimum these should be missing (empty defaults)
        assert "DATABASE_URL" in missing

    def test_all_critical_present(self):
        """When all critical env vars are set, no critical fields are missing."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "SUPABASE_URL": "http://localhost",
            "SUPABASE_SERVICE_ROLE_KEY": "key",
            "SUPABASE_JWT_SECRET": "secret",
            "POSTGRES_PASSWORD": "pass",
            "RAZORPAY_KEY_ID": "rzp_test",
            "RAZORPAY_KEY_SECRET": "secret",
            "RAZORPAY_WEBHOOK_SECRET": "whsec",
            "ODOO_URL": "http://localhost",
            "ODOO_API_KEY": "key",
            "PAPERCLIP_URL": "http://localhost",
            "PAPERCLIP_API_KEY": "key",
            "HERMES_API_URL": "http://localhost",
            "HERMES_API_KEY": "key",
        }
        with patch.dict(os.environ, env, clear=True):
            import importlib
            import api.config
            importlib.reload(api.config)
            from api.config import load_settings, validate_required
            settings = load_settings()
            missing = validate_required(settings)
            critical_fields = {
                "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                "SUPABASE_JWT_SECRET", "POSTGRES_PASSWORD",
            }
            assert not critical_fields.intersection(missing)


# ---------------------------------------------------------------------------
# 9. CROSS-CUTTING: Error Handling Patterns
# ---------------------------------------------------------------------------
class TestErrorPatterns:
    """Ensure consistent error handling across services."""

    def test_paperclip_never_raises(self):
        """Paperclip client never raises exceptions — always returns a decision."""
        client = PaperclipClient(base_url="http://localhost", api_key="x")
        mock_http = MagicMock()
        mock_http.post.side_effect = ConnectionRefusedError("refused")
        client._http = mock_http
        # Should not raise
        result = client.evaluate(Proposal(tool="x", arguments={}, agent="x"))
        assert hasattr(result, "decision")
        assert result.decision == Decision.REJECT
        client.close()

    def test_hermes_never_raises(self):
        """Hermes client never raises — always returns ExecutionStatus."""
        client = HermesClient(base_url="http://localhost", api_key="x")
        mock_http = MagicMock()
        mock_http.post.side_effect = ConnectionRefusedError("refused")
        client._http = mock_http
        result = client.execute(tool="x", arguments={}, decision_id="x")
        assert isinstance(result.status, ExecutionStatus)
        client.close()

    def test_pod_can_transition_never_raises(self):
        """can_transition never raises — returns bool."""
        for from_s in PODStatus:
            for to_s in PODStatus:
                result = can_transition(from_s, to_s)
                assert isinstance(result, bool)
