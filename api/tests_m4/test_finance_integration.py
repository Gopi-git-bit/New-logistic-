"""Disposable-PostgreSQL M4 integration tests.

Runs only inside the M4 proof harness (ZIPPY_M4_TEST_DATABASE_URL). Synthetic
identities and `.invalid` endpoints only; no external network calls.

Pool lifecycle: a psycopg pool cannot reopen after a TestClient lifespan
closes it, so each client context owns its Database and worker runs use a
separate pool.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from api.config import Settings
from api.database import Database
from api.main import create_app
from api.odoo import OdooDraftAdapter
from api.repositories import ConflictError
from api.repositories_finance import FinanceRepository
from api.tests_m4.conftest import (
    ADMIN,
    ADMIN2,
    CROSS_TENANT_ORDER,
    CROSS_TENANT_PLATFORM_ID,
    CUSTOMER,
    ORDER_A,
    ORDER_B,
    ORDER_C,
    ORDER_D,
    OTHER_CUSTOMER,
    VENDOR,
    WEBHOOK_SECRET,
    auth_headers,
    prepare_payment_intent,
)
from api.worker_finance import (
    FinanceWorker,
    gateway_reconcile_handler,
    odoo_draft_sync_handler,
    pod_gate_handler,
)

DATABASE_URL = os.environ.get("ZIPPY_M4_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="requires the isolated M4 PostgreSQL proof"
)
PLATFORM_ID = "10000000-0000-0000-0000-000000000001"

# Authoritative provider-reference mappings reused across tests. Each order
# gets exactly one Razorpay payment-order reference for its lifetime, so
# every test touching a given order must agree on its provider reference and
# expected amount/currency (registered idempotently via prepare_payment_intent).
PROVIDER_REF_A = "order_syn_a"
PROVIDER_REF_B = "order_syn_b"
INTENT_AMOUNT_A = 10000
INTENT_AMOUNT_B = 25000


def _merged(settings: Settings) -> Settings:
    return replace(
        settings,
        database_url=DATABASE_URL or "",
        retry_base_seconds=0,
        retry_max_seconds=0,
    )


@contextlib.contextmanager
def create_client(settings: Settings):
    """One fresh Database per client lifespan (pools cannot reopen)."""
    database = Database(settings.database_url)
    try:
        with TestClient(
            create_app(settings, database), raise_server_exceptions=False
        ) as client:
            yield client
    finally:
        database.close()


def _sign(raw: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()


def _payment_body(
    event: str,
    event_id: str,
    provider_reference_id: object,
    amount_minor: object = 10000,
    payment_id: str = "pay_syn_1",
    currency: object = "INR",
    notes_order: object = None,
) -> bytes:
    entity: dict[str, object] = {"id": payment_id, "amount": amount_minor, "currency": currency}
    if provider_reference_id is not None:
        entity["order_id"] = provider_reference_id
    if notes_order is not None:
        # untrusted evidence only: must never establish or authorize a link
        entity["notes"] = {"zippy_order_id": str(notes_order)}
    return json.dumps(
        {"id": event_id, "event": event, "payload": {"payment": {"entity": entity}}}
    ).encode()


def _refund_body(event_id: str, refund_id: str, amount_minor: int = 25000) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "event": "refund.processed",
            "payload": {
                "refund": {
                    "entity": {
                        "id": refund_id,
                        "payment_id": "pay_syn_1",
                        "amount": amount_minor,
                        "currency": "INR",
                    }
                }
            },
        }
    ).encode()


def _post_webhook(client, raw: bytes, signature: str | None = None):
    headers = {"content-type": "application/json"}
    if signature is not None:
        headers["X-Razorpay-Signature"] = signature
    return client.post("/api/v1/webhooks/razorpay", content=raw, headers=headers)


def _query(sql: str, parameters: tuple = ()) -> list[dict]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        connection.execute(
            "SELECT set_config('zippy.platform_id', %s, false)", (PLATFORM_ID,)
        )
        return connection.execute(sql, parameters).fetchall()


def _execute(sql: str, parameters: tuple = ()) -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(
            "SELECT set_config('zippy.platform_id', %s, false)", (PLATFORM_ID,)
        )
        connection.execute(sql, parameters)


def _counts(order_id) -> dict:
    rows = _query(
        """
        SELECT
            (SELECT count(*) FROM zippy.webhook_receipts) AS receipts,
            (SELECT count(*) FROM zippy.gateway_events WHERE order_id = %s) AS events,
            (SELECT count(*) FROM zippy.payment_projections WHERE order_id = %s) AS projections,
            (SELECT count(*) FROM zippy.financial_requests WHERE order_id = %s) AS requests,
            (SELECT count(*) FROM zippy.durable_tasks WHERE task_type = 'odoo_draft_sync') AS odoo_tasks
        """,
        (order_id, order_id, order_id),
    )
    return rows[0]


class RecordingTransport:
    """Deterministic fake Odoo transport; records every attempted call."""

    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, str]] = []
        self.fail = fail
        self.next_id = 5000

    def execute_kw(self, model, method, args, kwargs):
        self.calls.append((model, method))
        if self.fail:
            raise ConnectionError("synthetic transport failure")
        if model == "res.partner" and method == "search":
            return []
        self.next_id += 1
        return self.next_id


# ------------------------------------------------------------------ webhook


def test_captured_webhook_projects_and_enqueues(settings: Settings):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body("payment.captured", event_id, PROVIDER_REF_A)
    with create_client(merged) as client:
        response = _post_webhook(client, raw, _sign(raw))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "projected"
    assert body["duplicate"] is False

    receipt = _query(
        "SELECT signature_verified, processing_status FROM zippy.webhook_receipts WHERE provider_event_id = %s",
        (event_id,),
    )[0]
    assert receipt == {"signature_verified": True, "processing_status": "succeeded"}

    counts = _counts(ORDER_A)
    assert counts["events"] == 1
    assert counts["projections"] == 1
    assert counts["requests"] == 1
    assert counts["odoo_tasks"] == 1

    projection = _query(
        "SELECT operational_status, amount, currency_code FROM zippy.payment_projections WHERE order_id = %s",
        (ORDER_A,),
    )[0]
    assert projection == {
        "operational_status": "evidence_verified",
        "amount": 100.00,
        "currency_code": "INR",
    }
    outbox = _query(
        "SELECT count(*) AS n FROM zippy.event_outbox WHERE destination = 'sse_projection'"
    )[0]
    assert outbox["n"] >= 1


def test_duplicate_webhook_is_stable_noop(settings: Settings):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body("payment.authorized", event_id, PROVIDER_REF_A)
    with create_client(merged) as client:
        first = _post_webhook(client, raw, _sign(raw))
        second = _post_webhook(client, raw, _sign(raw))
    assert first.json()["outcome"] == "projected"
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["receipt_id"] == first.json()["receipt_id"]
    projection = _query(
        "SELECT count(*) AS n FROM zippy.payment_projections WHERE order_id = %s AND operational_status = 'pending'",
        (ORDER_A,),
    )[0]
    assert projection["n"] == 1


def test_invalid_signature_rejected_without_evidence(settings: Settings):
    merged = _merged(settings)
    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body("payment.captured", event_id, PROVIDER_REF_A)
    tampered_signature = "0" * 64
    with create_client(merged) as client:
        response = _post_webhook(client, raw, tampered_signature)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"
    assert WEBHOOK_SECRET not in response.text
    assert tampered_signature not in response.text
    receipts = _query(
        "SELECT count(*) AS n FROM zippy.webhook_receipts WHERE provider_event_id = %s",
        (event_id,),
    )[0]
    assert receipts["n"] == 0


def test_missing_secret_signature_and_event_id_fail_closed(settings: Settings):
    merged = _merged(settings)
    raw = _payment_body("payment.captured", f"evt_{uuid4().hex[:12]}", PROVIDER_REF_A)

    unconfigured = replace(merged, razorpay_webhook_secret="")
    with create_client(unconfigured) as client:
        no_secret = _post_webhook(client, raw, _sign(raw))
    assert no_secret.status_code == 503
    assert no_secret.json()["error"]["code"] == "WEBHOOK_NOT_CONFIGURED"

    with create_client(merged) as client:
        unsigned = _post_webhook(client, raw, None)
        no_id_body = json.dumps({"event": "payment.captured"}).encode()
        no_id = _post_webhook(client, no_id_body, _sign(no_id_body))
    assert unsigned.status_code == 401
    assert no_id.status_code == 400
    assert no_id.json()["error"]["code"] == "MALFORMED_EVENT"
    receipts = _query(
        "SELECT count(*) AS n FROM zippy.webhook_receipts WHERE provider_event_id = %s",
        (json.loads(raw)["id"],),
    )[0]
    assert receipts["n"] == 0


def test_authorized_failed_and_unsupported_mappings(settings: Settings):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    authorized_id = f"evt_{uuid4().hex[:12]}"
    failed_id = f"evt_{uuid4().hex[:12]}"
    unsupported_id = f"evt_{uuid4().hex[:12]}"
    with create_client(merged) as client:
        raw = _payment_body("payment.authorized", authorized_id, PROVIDER_REF_A)
        authorized = _post_webhook(client, raw, _sign(raw))
        raw = _payment_body("payment.failed", failed_id, PROVIDER_REF_A)
        failed = _post_webhook(client, raw, _sign(raw))
        raw = json.dumps({"id": unsupported_id, "event": "order.paid"}).encode()
        unsupported = _post_webhook(client, raw, _sign(raw))
    assert authorized.json()["outcome"] == "projected"
    assert failed.json()["outcome"] == "projected"
    assert unsupported.json()["outcome"] == "unsupported"
    statuses = {
        row["operational_status"]
        for row in _query(
            "SELECT operational_status FROM zippy.payment_projections WHERE order_id = %s",
            (ORDER_A,),
        )
    }
    assert {"pending", "failed"} <= statuses
    events = _query(
        "SELECT count(*) AS n FROM zippy.gateway_events WHERE webhook_receipt_id = (SELECT webhook_receipt_id FROM zippy.webhook_receipts WHERE provider_event_id = %s)",
        (unsupported_id,),
    )[0]
    assert events["n"] == 0


def test_missing_payment_mapping_recorded_only_with_exception(settings: Settings):
    merged = _merged(settings)
    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body("payment.captured", event_id, "order_syn_never_registered")
    with create_client(merged) as client:
        response = _post_webhook(client, raw, _sign(raw))
    assert response.json()["outcome"] == "recorded_only"
    exception = _query(
        "SELECT count(*) AS n FROM zippy.operational_exceptions WHERE exception_code = 'GATEWAY_EVENT_UNMATCHED'"
    )[0]
    assert exception["n"] >= 1
    events = _query(
        "SELECT count(*) AS n FROM zippy.gateway_events WHERE webhook_receipt_id = "
        "(SELECT webhook_receipt_id FROM zippy.webhook_receipts WHERE provider_event_id = %s)",
        (event_id,),
    )[0]
    assert events["n"] == 0


def test_notes_only_does_not_link_an_order(settings: Settings):
    """A valid signature plus `notes.zippy_order_id` alone must never link an order."""
    merged = _merged(settings)
    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body(
        "payment.captured", event_id, None, notes_order=ORDER_A
    )
    with create_client(merged) as client:
        response = _post_webhook(client, raw, _sign(raw))
    assert response.json()["outcome"] == "recorded_only"
    events = _query(
        "SELECT count(*) AS n FROM zippy.gateway_events WHERE webhook_receipt_id = "
        "(SELECT webhook_receipt_id FROM zippy.webhook_receipts WHERE provider_event_id = %s)",
        (event_id,),
    )[0]
    assert events["n"] == 0


def test_amount_and_currency_mismatch_do_not_update_trusted_projection(settings: Settings):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    with create_client(merged) as client:
        amount_mismatch_id = f"evt_{uuid4().hex[:12]}"
        raw = _payment_body(
            "payment.captured", amount_mismatch_id, PROVIDER_REF_A,
            amount_minor=INTENT_AMOUNT_A + 1,
        )
        amount_response = _post_webhook(client, raw, _sign(raw))

        currency_mismatch_id = f"evt_{uuid4().hex[:12]}"
        raw = _payment_body(
            "payment.captured", currency_mismatch_id, PROVIDER_REF_A, currency="USD"
        )
        currency_response = _post_webhook(client, raw, _sign(raw))
    assert amount_response.json()["outcome"] == "recorded_only"
    assert currency_response.json()["outcome"] == "recorded_only"
    for event_id in (amount_mismatch_id, currency_mismatch_id):
        events = _query(
            "SELECT count(*) AS n FROM zippy.gateway_events WHERE webhook_receipt_id = "
            "(SELECT webhook_receipt_id FROM zippy.webhook_receipts WHERE provider_event_id = %s)",
            (event_id,),
        )[0]
        assert events["n"] == 0
    exception = _query(
        "SELECT count(*) AS n FROM zippy.operational_exceptions WHERE exception_code = 'GATEWAY_EVENT_AMOUNT_MISMATCH'"
    )[0]
    assert exception["n"] >= 2


@pytest.mark.parametrize("unsafe_amount", [True, False, 10000.5, "10000", -1, 0, 10**13])
def test_unsafe_amount_values_do_not_create_trusted_projection(settings: Settings, unsafe_amount):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body(
        "payment.captured", event_id, PROVIDER_REF_A, amount_minor=unsafe_amount
    )
    with create_client(merged) as client:
        response = _post_webhook(client, raw, _sign(raw))
    assert response.json()["outcome"] == "recorded_only"
    events = _query(
        "SELECT count(*) AS n FROM zippy.gateway_events WHERE webhook_receipt_id = "
        "(SELECT webhook_receipt_id FROM zippy.webhook_receipts WHERE provider_event_id = %s)",
        (event_id,),
    )[0]
    assert events["n"] == 0


def test_conflicting_and_cross_tenant_mappings_are_rejected(settings: Settings):
    merged = _merged(settings)
    repository = FinanceRepository()
    database = Database(merged.database_url)
    database.open()
    try:
        shared_reference = f"order_syn_conflict_{uuid4().hex[:8]}"
        with database.transaction(UUID(PLATFORM_ID)) as connection:
            repository.prepare_payment_intent(
                connection, UUID(PLATFORM_ID), ORDER_C, shared_reference,
                12345, "INR", uuid4(),
            )
        # a different, previously-unmapped order cannot claim an
        # already-bound provider reference
        with pytest.raises(ConflictError), database.transaction(UUID(PLATFORM_ID)) as connection:
            repository.prepare_payment_intent(
                connection, UUID(PLATFORM_ID), ORDER_D, shared_reference,
                12345, "INR", uuid4(),
            )
        # the same order cannot be rebound to a different provider reference
        with pytest.raises(ConflictError), database.transaction(UUID(PLATFORM_ID)) as connection:
            repository.prepare_payment_intent(
                connection, UUID(PLATFORM_ID), ORDER_C, f"{shared_reference}-other",
                12345, "INR", uuid4(),
            )

        # cross-tenant: a mapping registered under a different platform is
        # invisible to this platform's resolution even with the same
        # provider-reference string
        cross_tenant_reference = f"order_syn_cross_tenant_{uuid4().hex[:8]}"
        with database.transaction(CROSS_TENANT_PLATFORM_ID) as connection:
            repository.prepare_payment_intent(
                connection, CROSS_TENANT_PLATFORM_ID, CROSS_TENANT_ORDER,
                cross_tenant_reference, 5000, "INR", uuid4(),
            )
        with database.transaction(UUID(PLATFORM_ID)) as connection:
            mapping = repository._resolve_payment_mapping(
                connection, UUID(PLATFORM_ID), cross_tenant_reference
            )
        assert mapping is None
    finally:
        database.close()

    event_id = f"evt_{uuid4().hex[:12]}"
    raw = _payment_body("payment.captured", event_id, cross_tenant_reference)
    with create_client(merged) as client:
        response = _post_webhook(client, raw, _sign(raw))
    assert response.json()["outcome"] == "recorded_only"


# ------------------------------------------------------------------ refunds


def test_refund_event_cannot_create_or_approve_refund(settings: Settings):
    merged = _merged(settings)
    raw = _refund_body(f"evt_{uuid4().hex[:12]}", "rfnd_unknown_1")
    with create_client(merged) as client:
        response = _post_webhook(client, raw, _sign(raw))
    assert response.status_code == 200
    assert response.json()["outcome"] == "recorded_only"
    counts = _query(
        """
        SELECT
            (SELECT count(*) FROM zippy.refund_requests) AS requests,
            (SELECT count(*) FROM zippy.refund_decisions) AS decisions,
            (SELECT count(*) FROM zippy.refund_executions) AS executions
        """
    )[0]
    assert counts == {"requests": 0, "decisions": 0, "executions": 0}
    exception = _query(
        "SELECT count(*) AS n FROM zippy.operational_exceptions WHERE exception_code = 'REFUND_EVENT_UNMATCHED'"
    )[0]
    assert exception["n"] >= 1


def test_manual_refund_lifecycle_and_reconciliation(settings: Settings):
    merged = _merged(settings)
    key_request = str(uuid4())
    key_execution = str(uuid4())
    with create_client(merged) as client:
        body = {
            "amount": "250.00",
            "currency_code": "INR",
            "target_reference": "pay_syn_refund_target",
            "reason": "customer cancellation before pickup",
        }
        headers = auth_headers(CUSTOMER, **{"Idempotency-Key": key_request})
        created = client.post(f"/api/v1/orders/{ORDER_B}/refunds", json=body, headers=headers)
        assert created.status_code == 200, created.text
        refund_id = created.json()["refund_request_id"]
        assert created.json()["status"] == "requested"

        replay = client.post(f"/api/v1/orders/{ORDER_B}/refunds", json=body, headers=headers)
        assert replay.json()["duplicate"] is True
        assert replay.json()["refund_request_id"] == refund_id

        conflict = client.post(
            f"/api/v1/orders/{ORDER_B}/refunds",
            json={**body, "amount": "251.00"},
            headers=headers,
        )
        assert conflict.status_code == 409

        # self-approval is rejected for an admin requester
        admin_key = str(uuid4())
        admin_request = client.post(
            f"/api/v1/orders/{ORDER_B}/refunds",
            json={**body, "reason": "admin-initiated correction"},
            headers=auth_headers(ADMIN, **{"Idempotency-Key": admin_key}),
        )
        assert admin_request.status_code == 200
        admin_refund_id = admin_request.json()["refund_request_id"]
        self_approval = client.post(
            f"/api/v1/refunds/{admin_refund_id}/decision",
            json={"decision": "approved", "reason": "self approval attempt"},
            headers=auth_headers(ADMIN),
        )
        assert self_approval.status_code == 403

        # execution without an approved decision is rejected
        no_decision = client.post(
            f"/api/v1/refunds/{admin_refund_id}/execution",
            json={
                "gateway_refund_id": "rfnd_syn_88",
                "evidence_hash_sha256": "d" * 64,
                "executed_at": datetime.now(UTC).isoformat(),
            },
            headers=auth_headers(ADMIN2, **{"Idempotency-Key": str(uuid4())}),
        )
        assert no_decision.status_code == 409

        # a different admin approves the customer's refund
        decision = client.post(
            f"/api/v1/refunds/{refund_id}/decision",
            json={"decision": "approved", "reason": "verified manual review"},
            headers=auth_headers(ADMIN2),
        )
        assert decision.status_code == 200, decision.text
        assert decision.json()["status"] == "approved"

        execution = client.post(
            f"/api/v1/refunds/{refund_id}/execution",
            json={
                "gateway_refund_id": "rfnd_syn_77",
                "evidence_hash_sha256": "e" * 64,
                "executed_at": datetime.now(UTC).isoformat(),
            },
            headers=auth_headers(ADMIN, **{"Idempotency-Key": key_execution}),
        )
        assert execution.status_code == 200, execution.text
        assert execution.json()["status"] == "executed"
        execution_id = execution.json()["refund_execution_id"]

        # execution replay is idempotent
        replay_execution = client.post(
            f"/api/v1/refunds/{refund_id}/execution",
            json={
                "gateway_refund_id": "rfnd_syn_77",
                "evidence_hash_sha256": "e" * 64,
                "executed_at": datetime.now(UTC).isoformat(),
            },
            headers=auth_headers(ADMIN, **{"Idempotency-Key": key_execution}),
        )
        assert replay_execution.status_code == 200, replay_execution.text
        assert replay_execution.json()["refund_execution_id"] == execution_id

        # the gateway event now reconciles the approved, executed refund
        refund_event_id = f"evt_{uuid4().hex[:12]}"
        raw = _refund_body(refund_event_id, "rfnd_syn_77")
        reconciled = _post_webhook(client, raw, _sign(raw))
        assert reconciled.json()["outcome"] == "reconciled"

        # provider identifier / duplicate webhook delivery replay is idempotent
        replayed_webhook = _post_webhook(client, raw, _sign(raw))
        assert replayed_webhook.json()["duplicate"] is True
        assert replayed_webhook.json()["receipt_id"] == reconciled.json()["receipt_id"]

    reversed_projection = _query(
        "SELECT count(*) AS n FROM zippy.payment_projections WHERE order_id = %s AND operational_status = 'reversed'",
        (ORDER_B,),
    )[0]
    assert reversed_projection["n"] == 1
    reference = _query(
        "SELECT sync_status FROM zippy.external_references WHERE external_system = 'razorpay' AND external_model = 'refund' AND external_id = 'rfnd_syn_77'"
    )[0]
    assert reference["sync_status"] == "synchronized"


def test_refund_amount_mismatch_stays_evidence_only(settings: Settings):
    """An executed refund's own approved amount is authoritative: a webhook
    reporting a different amount for the same gateway refund id records
    reconciliation evidence but never creates a trusted projection."""
    merged = _merged(settings)
    gateway_refund_id = f"rfnd_syn_mismatch_{uuid4().hex[:8]}"
    with create_client(merged) as client:
        created = client.post(
            f"/api/v1/orders/{ORDER_B}/refunds",
            json={
                "amount": "10.00",
                "currency_code": "INR",
                "target_reference": "pay_syn_mismatch_target",
                "reason": "amount-mismatch regression fixture",
            },
            headers=auth_headers(CUSTOMER, **{"Idempotency-Key": str(uuid4())}),
        )
        assert created.status_code == 200, created.text
        refund_id = created.json()["refund_request_id"]
        decision = client.post(
            f"/api/v1/refunds/{refund_id}/decision",
            json={"decision": "approved", "reason": "verified manual review"},
            headers=auth_headers(ADMIN2),
        )
        assert decision.status_code == 200, decision.text
        execution = client.post(
            f"/api/v1/refunds/{refund_id}/execution",
            json={
                "gateway_refund_id": gateway_refund_id,
                "evidence_hash_sha256": "f" * 64,
                "executed_at": datetime.now(UTC).isoformat(),
            },
            headers=auth_headers(ADMIN, **{"Idempotency-Key": str(uuid4())}),
        )
        assert execution.status_code == 200, execution.text

        # the approved/executed amount is INR 10.00 (1000 minor units); a
        # webhook reporting a different amount for the same refund id must
        # not create a trusted projection.
        raw = _refund_body(f"evt_{uuid4().hex[:12]}", gateway_refund_id, amount_minor=1001)
        mismatched = _post_webhook(client, raw, _sign(raw))
    assert mismatched.json()["outcome"] == "recorded_only"
    exception = _query(
        "SELECT count(*) AS n FROM zippy.operational_exceptions WHERE exception_code = 'REFUND_EVENT_AMOUNT_MISMATCH'"
    )[0]
    assert exception["n"] >= 1
    reversed_projection = _query(
        "SELECT count(*) AS n FROM zippy.payment_projections WHERE order_id = %s "
        "AND operational_status = 'reversed' AND amount = 10.00",
        (ORDER_B,),
    )[0]
    assert reversed_projection["n"] == 0



# ------------------------------------------------------------------ POD gate


def test_pod_gate_blocks_then_permits_settlement_eligibility(settings: Settings):
    merged = _merged(settings)
    object_key = f"m4-test/pod/{uuid4().hex}.jpg"
    with create_client(merged) as client:
        blocked = client.post(
            f"/api/v1/orders/{ORDER_A}/settlement-evaluation",
            headers=auth_headers(ADMIN),
        )
        assert blocked.status_code == 200
        assert blocked.json()["eligible"] is False
        assert blocked.json()["reason"] == "pod_not_accepted"

        pod = client.post(
            f"/api/v1/orders/{ORDER_A}/pod",
            json={
                "object_key": object_key,
                "content_type": "image/jpeg",
                "byte_size": 2048,
                "checksum_sha256": "c" * 64,
            },
            headers=auth_headers(VENDOR),
        )
        assert pod.status_code == 200, pod.text
        pod_id = pod.json()["pod_document_id"]
        assert pod.json()["verification_status"] == "pending"

        duplicate = client.post(
            f"/api/v1/orders/{ORDER_A}/pod",
            json={
                "object_key": object_key,
                "content_type": "image/jpeg",
                "byte_size": 2048,
                "checksum_sha256": "c" * 64,
            },
            headers=auth_headers(VENDOR),
        )
        assert duplicate.json()["duplicate"] is True

        denied = client.post(
            f"/api/v1/pod/{pod_id}/verification",
            json={"decision": "accepted", "reason": "customer cannot verify"},
            headers=auth_headers(CUSTOMER),
        )
        assert denied.status_code == 403

        accepted = client.post(
            f"/api/v1/pod/{pod_id}/verification",
            json={"decision": "accepted", "reason": "documents match delivery"},
            headers=auth_headers(ADMIN),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["verification_status"] == "accepted"
        assert accepted.json()["settlement_projection_id"] is not None

        eligible = client.post(
            f"/api/v1/orders/{ORDER_A}/settlement-evaluation",
            headers=auth_headers(ADMIN),
        )
        assert eligible.json()["eligible"] is True
        assert eligible.json()["reason"] == "already_evaluated"

        # settlement projection is operational only: no financial request,
        # no external reference, no money movement evidence
        projection = _query(
            "SELECT operational_status, financial_request_id, external_reference_id FROM zippy.settlement_projections WHERE order_id = %s",
            (ORDER_A,),
        )[0]
        assert projection["operational_status"] == "not_requested"
        assert projection["financial_request_id"] is None
        assert projection["external_reference_id"] is None

    # database-level gate: no settlement projection without accepted POD
    with pytest.raises(psycopg.Error) as excinfo:
        _execute(
            """
            INSERT INTO zippy.settlement_projections (
                platform_id, order_id, operational_status, correlation_id
            ) VALUES (%s, %s, 'requested', %s)
            """,
            (PLATFORM_ID, str(ORDER_B), str(uuid4())),
        )
    assert excinfo.value.sqlstate == "23514"


def test_authorization_boundaries(settings: Settings):
    merged = _merged(settings)
    with create_client(merged) as client:
        outsider_pod = client.post(
            f"/api/v1/orders/{ORDER_A}/pod",
            json={
                "object_key": f"m4-test/pod/{uuid4().hex}.jpg",
                "content_type": "image/jpeg",
                "byte_size": 128,
                "checksum_sha256": "f" * 64,
            },
            headers=auth_headers(OTHER_CUSTOMER),
        )
        assert outsider_pod.status_code == 403

        vendor_refund = client.post(
            f"/api/v1/orders/{ORDER_A}/refunds",
            json={
                "amount": "10.00",
                "currency_code": "INR",
                "target_reference": "pay_syn_x",
                "reason": "vendor cannot request refunds",
            },
            headers=auth_headers(VENDOR, **{"Idempotency-Key": str(uuid4())}),
        )
        assert vendor_refund.status_code == 403

        blocked_actor = client.post(
            f"/api/v1/orders/{ORDER_A}/settlement-evaluation",
            headers=auth_headers("blocked-subject"),
        )
        assert blocked_actor.status_code == 403


# ------------------------------------------------------------------ workers


def test_odoo_draft_sync_success_failure_and_single_claim(settings: Settings):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    prepare_payment_intent(merged.database_url, ORDER_B, PROVIDER_REF_B, INTENT_AMOUNT_B)
    with create_client(merged) as client:
        raw = _payment_body(
            "payment.captured", f"evt_{uuid4().hex[:12]}", PROVIDER_REF_A, payment_id="pay_syn_odoo"
        )
        response = _post_webhook(client, raw, _sign(raw))
        assert response.json()["outcome"] == "projected"

    worker_database = Database(merged.database_url)
    worker_database.open()
    try:
        transport = RecordingTransport()
        adapter = OdooDraftAdapter(transport)
        worker = FinanceWorker(worker_database, merged)
        handled = worker.run_tasks(
            "m4-odoo-worker", "odoo_draft_sync", odoo_draft_sync_handler(worker_database, merged, adapter)
        )
        assert handled == 1
        called_methods = {method for _, method in transport.calls}
        assert called_methods <= {"search", "create"}
        assert ("res.partner", "search") in transport.calls
        assert ("account.move", "create") in transport.calls
        assert not {"action_post", "action_register_payment", "write", "unlink"} & called_methods

        references = _query(
            """
            SELECT external_model, sync_status FROM zippy.external_references
             WHERE external_system = 'odoo' ORDER BY external_model
            """
        )
        assert [(r["external_model"], r["sync_status"]) for r in references] == [
            ("account.move", "synchronized"),
            ("res.partner", "synchronized"),
        ]
        request = _query(
            "SELECT status FROM zippy.financial_requests WHERE request_type = 'draft_customer_invoice' AND order_id = %s",
            (str(ORDER_A),),
        )[0]
        assert request["status"] == "acknowledged"

        # a second worker run finds no work; no duplicate external effects
        again = worker.run_tasks(
            "m4-odoo-worker-2", "odoo_draft_sync", odoo_draft_sync_handler(worker_database, merged, adapter)
        )
        assert again == 0
        moves = _query(
            "SELECT count(*) AS n FROM zippy.external_references WHERE external_model = 'account.move'"
        )[0]
        assert moves["n"] == 1

        # failure path: dead-letter without accounting mutation
        with create_client(merged) as client:
            raw = _payment_body(
                "payment.captured", f"evt_{uuid4().hex[:12]}", PROVIDER_REF_B,
                amount_minor=INTENT_AMOUNT_B, payment_id="pay_syn_fail",
            )
            response = _post_webhook(client, raw, _sign(raw))
            assert response.json()["outcome"] == "projected"

        failing = OdooDraftAdapter(RecordingTransport(fail=True))
        for _ in range(3):
            worker.run_tasks(
                "m4-odoo-worker", "odoo_draft_sync",
                odoo_draft_sync_handler(worker_database, merged, failing),
            )
        task = _query(
            """
            SELECT status, attempt_count FROM zippy.durable_tasks
             WHERE task_type = 'odoo_draft_sync' AND aggregate_id = (
                 SELECT financial_request_id FROM zippy.financial_requests
                  WHERE order_id = %s AND request_type = 'draft_customer_invoice'
             )
            """,
            (str(ORDER_B),),
        )[0]
        assert task == {"status": "dead_lettered", "attempt_count": 3}
        dead = _query(
            "SELECT count(*) AS n FROM zippy.dead_letter_records WHERE source_kind = 'task'"
        )[0]
        assert dead["n"] >= 1
        failed_request = _query(
            "SELECT status FROM zippy.financial_requests WHERE order_id = %s AND request_type = 'draft_customer_invoice'",
            (str(ORDER_B),),
        )[0]
        assert failed_request["status"] == "requested"
        refs = _query(
            """
            SELECT count(*) AS n FROM zippy.external_references reference
             JOIN zippy.financial_requests request
               ON request.platform_id = reference.platform_id
              AND reference.local_entity_id = request.financial_request_id
             WHERE request.order_id = %s
            """,
            (str(ORDER_B),),
        )[0]
        assert refs["n"] == 0
    finally:
        worker_database.close()


def test_stale_receipt_sweep_and_pod_gate_task(settings: Settings):
    merged = _merged(settings)
    prepare_payment_intent(merged.database_url, ORDER_A, PROVIDER_REF_A, INTENT_AMOUNT_A)
    repository = FinanceRepository()
    receipt_id = uuid4()
    reference = json.dumps(
        {
            "event_type": "payment.authorized",
            "provider_reference_id": PROVIDER_REF_A,
            "payment_id": "pay_syn_stale",
            "refund_id": None,
            "amount_minor_units": INTENT_AMOUNT_A,
            "currency": "INR",
            "notes": {},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    _execute(
        """
        INSERT INTO zippy.webhook_receipts (
            webhook_receipt_id, platform_id, provider, provider_event_id,
            signature_verified, payload_hash_sha256, payload_reference,
            processing_status, attempt_count, correlation_id, received_at
        ) VALUES (%s, %s, 'razorpay', %s,
                  true, %s, %s, 'processing', 1, %s, clock_timestamp() - interval '1 hour')
        """,
        (str(receipt_id), PLATFORM_ID, f"evt_stale_{uuid4().hex[:8]}", "a" * 64, reference, str(uuid4())),
    )
    worker_database = Database(merged.database_url)
    worker_database.open()
    try:
        with worker_database.transaction(merged.platform_id) as connection:
            enqueued = repository.sweep_stale_receipts(
                connection, merged.platform_id, 60, merged.task_max_attempts, uuid4()
            )
        assert enqueued >= 1

        worker = FinanceWorker(worker_database, merged)
        first = worker.run_tasks(
            "m4-sweeper-a", "gateway_reconcile", gateway_reconcile_handler(worker_database, merged)
        )
        second = worker.run_tasks(
            "m4-sweeper-b", "gateway_reconcile", gateway_reconcile_handler(worker_database, merged)
        )
        assert first >= 1
        assert second == 0  # single effective claim under SKIP LOCKED

        projection = _query(
            """
            SELECT count(*) AS n FROM zippy.payment_projections projection
             JOIN zippy.gateway_events gateway_event
               ON gateway_event.platform_id = projection.platform_id
              AND gateway_event.gateway_event_id = projection.gateway_event_id
             WHERE gateway_event.webhook_receipt_id = %s
               AND projection.operational_status = 'pending'
            """,
            (str(receipt_id),),
        )[0]
        assert projection["n"] == 1

        # the POD gate task from the accepted POD now resolves successfully
        handled = worker.run_tasks(
            "m4-pod-gate", "pod_gate_evaluate", pod_gate_handler(worker_database, merged)
        )
        assert handled == 1
        task = _query(
            "SELECT status FROM zippy.durable_tasks WHERE task_type = 'pod_gate_evaluate'"
        )[0]
        assert task["status"] == "succeeded"
    finally:
        worker_database.close()
