"""Zippy Logistics — API Security Tests."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 1. Configuration validation
# ---------------------------------------------------------------------------
class TestConfigurationValidation:
    """Test that config validation catches missing secrets."""

    def test_missing_database_url_fails(self):
        with patch.dict(os.environ, {
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
        }, clear=True):
            from api.config import load_settings, validate_required
            settings = load_settings()
            missing = validate_required(settings)
            assert "DATABASE_URL" in missing

    def test_optional_langfuse_missing_ok(self):
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
            from api.config import load_settings, validate_required
            settings = load_settings()
            missing = validate_required(settings)
            assert "LANGFUSE_PUBLIC_KEY" not in missing

    def test_optional_honcho_missing_ok(self):
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
            from api.config import load_settings, validate_required
            settings = load_settings()
            missing = validate_required(settings)
            assert "HONCHO_API_KEY" not in missing


# ---------------------------------------------------------------------------
# 2. Secret redaction
# ---------------------------------------------------------------------------
class TestSecretRedaction:
    """Test that secrets are redacted from logs."""

    def test_redact_key(self):
        from api.redaction import _is_sensitive_key
        assert _is_sensitive_key("RAZORPAY_KEY_SECRET")
        assert _is_sensitive_key("SUPABASE_SERVICE_ROLE_KEY")
        assert _is_sensitive_key("API_KEY")
        assert not _is_sensitive_key("order_id")

    def test_redact_dict(self):
        from api.redaction import redact_dict
        data = {"api_key": "sk_live_12345", "order_id": "abc"}
        result = redact_dict(data)
        assert result["api_key"] != "sk_live_12345"
        assert result["order_id"] == "abc"


# ---------------------------------------------------------------------------
# 3. POD lifecycle
# ---------------------------------------------------------------------------
class TestPODLifecycle:
    """Test POD verification lifecycle transitions."""

    def test_uploaded_to_pending(self):
        from api.pod_lifecycle import PODStatus, can_transition
        assert can_transition(PODStatus.UPLOADED, PODStatus.VERIFICATION_PENDING)

    def test_pending_to_verified(self):
        from api.pod_lifecycle import PODStatus, can_transition
        assert can_transition(PODStatus.VERIFICATION_PENDING, PODStatus.VERIFIED)

    def test_verified_to_confirmed(self):
        from api.pod_lifecycle import PODStatus, can_transition
        assert can_transition(PODStatus.VERIFIED, PODStatus.DELIVERY_CONFIRMED)

    def test_confirmed_to_settlement(self):
        from api.pod_lifecycle import PODStatus, can_transition
        assert can_transition(PODStatus.DELIVERY_CONFIRMED, PODStatus.SETTLEMENT_ELIGIBLE)

    def test_cannot_skip_lifecycle(self):
        from api.pod_lifecycle import PODStatus, can_transition
        assert not can_transition(PODStatus.UPLOADED, PODStatus.VERIFIED)
        assert not can_transition(PODStatus.UPLOADED, PODStatus.SETTLEMENT_ELIGIBLE)


# ---------------------------------------------------------------------------
# 4. Paperclip governance
# ---------------------------------------------------------------------------
class TestPaperclipGovernance:
    """Test Paperclip governance enforcement."""

    def test_reject_on_error(self):
        from api.services.paperclip import PaperclipClient, Decision
        client = PaperclipClient("http://invalid:9999", "key", timeout_s=1.0)
        from api.services.paperclip import Proposal
        proposal = Proposal(tool="test", arguments={}, agent="test")
        decision = client.evaluate(proposal)
        assert decision.decision == Decision.REJECT
        client.close()

    def test_hermes_allowlist(self):
        from api.services.hermes import HermesClient, ExecutionStatus, ALLOWLISTED_TOOLS
        assert "create_sale_order" in ALLOWLISTED_TOOLS
        assert "find_partner" in ALLOWLISTED_TOOLS
        assert "arbitrary_tool" not in ALLOWLISTED_TOOLS


# ---------------------------------------------------------------------------
# 5. Health endpoint
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    """Test health endpoint."""

    def test_health_returns_ok(self):
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
