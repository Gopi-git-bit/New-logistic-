"""M6-A telemetry contract — data classification for observability export.

Defines which fields are permitted, restricted, or prohibited in telemetry
events. Redaction must fail closed: if a field cannot be classified, the
entire telemetry event is dropped (business operation continues).

D-31 boundary: repository-tracked contracts only; no live export.
"""

from __future__ import annotations

import enum
from typing import Any


class FieldClassification(enum.Enum):
    PERMITTED = "permitted"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


PERMITTED_FIELDS: frozenset[str] = frozenset(
    {
        "trace_id",
        "span_id",
        "parent_span_id",
        "correlation_id",
        "service_name",
        "operation_name",
        "agent_name",
        "task_type",
        "event_type",
        "model_alias",
        "provider_alias",
        "timestamp",
        "start_time",
        "end_time",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_cents",
        "confidence",
        "status_code",
        "success",
        "error_code",
        "error_class",
        "policy_outcome",
        "guardian_decision",
        "guardian_reason",
        "task_state",
        "retry_count",
        "sample_rate",
        "environment",
        "pseudonymous_tenant_id",
        "pseudonymous_actor_id",
        "pseudonymous_workflow_id",
    }
)

PROHIBITED_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "database_url",
        "supabase_service_role_key",
        "razorpay_key_id",
        "razorpay_key_secret",
        "razorpay_webhook_secret",
        "odoo_api_key",
        "paperclip_api_key",
        "hermes_api_key",
        "langfuse_public_key",
        "langfuse_secret_key",
        "smtp_password",
        "encryption_secret",
        "webhook_secret",
        "service_role_key",
        "jwt",
        "access_token",
        "refresh_token",
        "customer_name",
        "customer_email",
        "customer_phone",
        "driver_name",
        "driver_email",
        "driver_phone",
        "consignee_name",
        "consignee_email",
        "consignee_phone",
        "pickup_address",
        "delivery_address",
        "address",
        "email",
        "phone",
        "payment_amount",
        "total_amount",
        "advance_amount",
        "refund_amount",
        "settlement_amount",
        "transaction_id",
        "razorpay_payment_id",
        "razorpay_order_id",
        "stripe_id",
        "bank_details",
        "invoice_id",
        "sale_order_id",
        "odoo_partner_id",
        "ledger_entry",
        "tax_record",
        "raw_prompt",
        "raw_response",
        "system_prompt",
        "prompt_body",
        "response_body",
        "input_text",
        "output_text",
        "cargo_description",
        "cargo_details",
        "special_instructions",
        "order_notes",
    }
)

RESTRICTED_FIELDS: frozenset[str] = frozenset(
    {
        "order_id",
        "trip_id",
        "vehicle_id",
        "driver_id",
        "user_id",
        "tenant_id",
        "actor_id",
        "workflow_id",
        "grant_id",
        "decision_id",
        "notification_id",
        "document_id",
        "exception_message",
        "stack_trace",
        "error_message",
        "policy_checksum",
        "payload_hash",
        "denial_reason",
    }
)


def classify_field(field_name: str) -> FieldClassification:
    lower = field_name.lower().strip()
    if lower in PERMITTED_FIELDS:
        return FieldClassification.PERMITTED
    if lower in PROHIBITED_FIELDS:
        return FieldClassification.PROHIBITED
    if lower in RESTRICTED_FIELDS:
        return FieldClassification.RESTRICTED
    return FieldClassification.PROHIBITED


def is_safe_for_telemetry(field_name: str) -> bool:
    return classify_field(field_name) == FieldClassification.PERMITTED


def validate_event_fields(event: dict[str, Any]) -> tuple[bool, list[str]]:
    violations: list[str] = []
    for key in event:
        cls = classify_field(key)
        if cls != FieldClassification.PERMITTED:
            violations.append(f"{key}:{cls.value}")
    return (len(violations) == 0, violations)
