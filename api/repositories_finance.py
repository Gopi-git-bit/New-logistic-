"""Transactional finance repository for the M4 operations-finance boundary.

Covers canonical webhook evidence, operational payment projections, the POD
settlement gate, the manual refund workflow, and draft-only Odoo references.
All methods run inside Database.transaction (platform RLS context is set).
Zippy PostgreSQL owns operational truth; Odoo owns accounting truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from .gateway import (
    EVENT_PROJECTION_STATUS,
    MAX_AMOUNT_MINOR_UNITS,
    RECONCILE_ONLY_EVENTS,
    GatewayEvent,
    major_units_to_minor,
    minor_units_to_major,
)
from .repositories import ConflictError, ForbiddenError, RequestIdentity


@dataclass(frozen=True)
class ReceiptOutcome:
    receipt_id: UUID
    duplicate: bool
    outcome: str
    correlation_id: UUID
    projection_status: str | None = None


@dataclass(frozen=True)
class SettlementEligibility:
    order_id: UUID
    eligible: bool
    settlement_projection_id: UUID | None
    reason: str


def _sha256_json(payload: dict[str, Any]) -> str:
    import hashlib

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class FinanceRepository:
    # ------------------------------------------------------------ webhook ingest
    def ingest_gateway_event(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        event: GatewayEvent,
        correlation_id: UUID,
        task_max_attempts: int,
    ) -> ReceiptOutcome:
        """Persist the verified receipt, then project inside one transaction.

        The receipt is written before any projection. A duplicate provider
        event is a stable no-op: the prior transaction committed atomically,
        so an existing receipt means the full pipeline already succeeded.
        """
        reference = json.dumps(
            {
                "event_type": event.event_type,
                "provider_reference_id": event.provider_reference_id,
                "payment_id": event.payment_id,
                "refund_id": event.refund_id,
                "amount_minor_units": event.amount_minor_units,
                "currency": event.currency,
                "notes": event.notes,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        row = connection.execute(
            """
            INSERT INTO zippy.webhook_receipts (
                platform_id, provider, provider_event_id, signature_verified,
                payload_hash_sha256, payload_reference, processing_status,
                attempt_count, correlation_id
            ) VALUES (%s, %s, %s, true, %s, %s, 'processing', 1, %s)
            ON CONFLICT (platform_id, provider, provider_event_id) DO NOTHING
            RETURNING webhook_receipt_id
            """,
            (
                platform_id,
                event.provider,
                event.provider_event_id,
                event.evidence_hash,
                reference,
                correlation_id,
            ),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                """
                SELECT webhook_receipt_id, correlation_id
                  FROM zippy.webhook_receipts
                 WHERE platform_id = %s AND provider = %s AND provider_event_id = %s
                 FOR UPDATE
                """,
                (platform_id, event.provider, event.provider_event_id),
            ).fetchone()
            if existing is None:
                raise RuntimeError("receipt persistence failed")
            return ReceiptOutcome(
                receipt_id=existing["webhook_receipt_id"],
                duplicate=True,
                outcome="duplicate",
                correlation_id=existing["correlation_id"],
            )

        receipt_id = row["webhook_receipt_id"]
        outcome, projection_status = self._project_event(
            connection, platform_id, receipt_id, event, correlation_id, task_max_attempts
        )
        connection.execute(
            """
            UPDATE zippy.webhook_receipts
               SET processing_status = 'succeeded', processed_at = clock_timestamp()
             WHERE platform_id = %s AND webhook_receipt_id = %s
            """,
            (platform_id, receipt_id),
        )
        return ReceiptOutcome(
            receipt_id=receipt_id,
            duplicate=False,
            outcome=outcome,
            correlation_id=correlation_id,
            projection_status=projection_status,
        )

    def _project_event(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        receipt_id: UUID,
        event: GatewayEvent,
        correlation_id: UUID,
        task_max_attempts: int,
    ) -> tuple[str, str | None]:
        if event.event_type not in EVENT_PROJECTION_STATUS and event.event_type not in RECONCILE_ONLY_EVENTS:
            self._record_event(connection, platform_id, receipt_id, "gateway.unsupported", {
                "event_type": event.event_type,
            }, correlation_id)
            return "unsupported", None
        if event.event_type in RECONCILE_ONLY_EVENTS:
            return self._reconcile_refund(
                connection, platform_id, receipt_id, event, correlation_id
            )
        return self._project_payment(
            connection, platform_id, receipt_id, event, correlation_id, task_max_attempts
        )

    def _project_payment(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        receipt_id: UUID,
        event: GatewayEvent,
        correlation_id: UUID,
        task_max_attempts: int,
    ) -> tuple[str, str | None]:
        projection_status = EVENT_PROJECTION_STATUS[event.event_type]
        mapping = self._resolve_payment_mapping(connection, platform_id, event.provider_reference_id)
        if mapping is None or event.amount_minor_units is None or event.currency is None:
            self._raise_exception(
                connection, platform_id, "GATEWAY_EVENT_UNMATCHED", "medium",
                "webhook_receipt", receipt_id,
                "supported event without an authoritative payment mapping or monetary data",
                correlation_id,
            )
            return "recorded_only", None
        if (
            mapping["expected_amount_minor_units"] != event.amount_minor_units
            or mapping["expected_currency_code"] != event.currency
        ):
            self._raise_exception(
                connection, platform_id, "GATEWAY_EVENT_AMOUNT_MISMATCH", "high",
                "webhook_receipt", receipt_id,
                "webhook amount/currency does not match the authoritative payment mapping",
                correlation_id,
            )
            return "recorded_only", None

        order_id = mapping["order_id"]
        amount_major = minor_units_to_major(event.amount_minor_units)
        gateway_event_id = self._record_gateway_event(
            connection, platform_id, receipt_id, event, order_id, correlation_id,
            amount_major, event.currency,
        )
        connection.execute(
            """
            INSERT INTO zippy.payment_projections (
                platform_id, order_id, gateway_event_id, operational_status,
                amount, currency_code, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id, order_id, gateway_event_id, operational_status) DO NOTHING
            """,
            (
                platform_id,
                order_id,
                gateway_event_id,
                projection_status,
                amount_major,
                event.currency,
                correlation_id,
            ),
        )
        if event.event_type == "payment.captured":
            self._enqueue_odoo_draft(
                connection, platform_id, order_id, mapping["created_by_account_id"],
                amount_major, event.currency, correlation_id, task_max_attempts,
            )
        self._record_event(connection, platform_id, receipt_id, "gateway.projected", {
            "event_type": event.event_type,
            "order_id": str(order_id),
            "operational_status": projection_status,
        }, correlation_id)
        self._record_outbox(connection, platform_id, receipt_id, event, {
            "event_type": event.event_type,
            "order_id": str(order_id),
            "operational_status": projection_status,
        }, correlation_id)
        return "projected", projection_status

    # ------------------------------------------------------------ payment intent mapping
    def prepare_payment_intent(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        order_id: UUID,
        provider_reference_id: str,
        expected_amount_minor_units: int,
        expected_currency_code: str,
        correlation_id: UUID,
    ) -> tuple[UUID, bool]:
        """Record the authoritative provider-reference mapping for an order.

        This is the only path that may bind a Razorpay provider reference to
        a Zippy order for webhook resolution. It represents the approved
        server-side payment-intent/order preparation step (called only after
        the provider order/intent already exists) or its synthetic test
        fixture; the public webhook route never calls this method. Tenant
        scoping and provider+external-identifier uniqueness are enforced by
        `zippy.external_references`'s existing platform-scoped unique
        constraint; no new uniqueness schema is required.
        """
        if isinstance(expected_amount_minor_units, bool) or not isinstance(
            expected_amount_minor_units, int
        ):
            raise TypeError("expected amount must be an integer number of minor units")
        if not (0 < expected_amount_minor_units <= MAX_AMOUNT_MINOR_UNITS):
            raise ValueError("expected amount is outside the safe minor-unit range")
        if not isinstance(expected_currency_code, str) or len(expected_currency_code) != 3:
            raise ValueError("expected currency code must be a 3-letter ISO 4217 code")

        # Pre-check the order-scoped uniqueness constraint explicitly: the
        # INSERT below only arbitrates conflicts on (system, model,
        # external_id), so a second, different provider reference for the
        # same order would otherwise raise an uncaught IntegrityError instead
        # of a clean, catchable conflict.
        existing_for_order = connection.execute(
            """
            SELECT external_id FROM zippy.external_references
             WHERE platform_id = %s AND local_entity_type = 'order' AND local_entity_id = %s
               AND external_system = 'razorpay' AND external_model = 'payment_order'
            """,
            (platform_id, order_id),
        ).fetchone()
        if existing_for_order is not None and existing_for_order["external_id"] != provider_reference_id:
            raise ConflictError("order already has a different Razorpay payment-order reference")

        reference = connection.execute(
            """
            INSERT INTO zippy.external_references (
                platform_id, local_entity_type, local_entity_id, external_system,
                external_model, external_id, sync_status, correlation_id
            ) VALUES (%s, 'order', %s, 'razorpay', 'payment_order', %s, 'pending', %s)
            ON CONFLICT (platform_id, external_system, external_model, external_id) DO NOTHING
            RETURNING external_reference_id
            """,
            (platform_id, order_id, provider_reference_id, correlation_id),
        ).fetchone()
        if reference is None:
            existing = connection.execute(
                """
                SELECT external_reference_id, local_entity_id FROM zippy.external_references
                 WHERE platform_id = %s AND external_system = 'razorpay'
                   AND external_model = 'payment_order' AND external_id = %s
                """,
                (platform_id, provider_reference_id),
            ).fetchone()
            if existing is None:
                raise RuntimeError("payment intent reference persistence failed")
            if existing["local_entity_id"] != order_id:
                raise ConflictError("provider reference is already bound to a different order")
            intent = connection.execute(
                """
                SELECT payment_intent_id, expected_amount_minor_units, expected_currency_code
                  FROM zippy.payment_intents
                 WHERE platform_id = %s AND external_reference_id = %s
                """,
                (platform_id, existing["external_reference_id"]),
            ).fetchone()
            if intent is None:
                raise RuntimeError("payment intent persistence failed")
            if (
                intent["expected_amount_minor_units"] != expected_amount_minor_units
                or intent["expected_currency_code"] != expected_currency_code
            ):
                raise ConflictError(
                    "provider reference already bound to a different expected amount or currency"
                )
            return UUID(str(intent["payment_intent_id"])), True

        inserted = connection.execute(
            """
            INSERT INTO zippy.payment_intents (
                platform_id, order_id, external_reference_id,
                expected_amount_minor_units, expected_currency_code, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING payment_intent_id
            """,
            (
                platform_id,
                order_id,
                reference["external_reference_id"],
                expected_amount_minor_units,
                expected_currency_code,
                correlation_id,
            ),
        ).fetchone()
        if inserted is None:
            raise RuntimeError("payment intent persistence failed")
        return UUID(str(inserted["payment_intent_id"])), False

    def _resolve_payment_mapping(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        provider_reference_id: str | None,
    ) -> dict[str, Any] | None:
        """Resolve the trusted order for a provider reference, tenant-scoped.

        Absent, cross-tenant (RLS/platform_id filtered), or never-registered
        references return None; the caller records evidence without
        projecting. `notes.zippy_order_id` never participates in this query.
        """
        if not provider_reference_id:
            return None
        return connection.execute(
            """
            SELECT intent.order_id, intent.expected_amount_minor_units,
                   intent.expected_currency_code, order_record.created_by_account_id
              FROM zippy.external_references reference
              JOIN zippy.payment_intents intent
                ON intent.platform_id = reference.platform_id
               AND intent.external_reference_id = reference.external_reference_id
              JOIN zippy.orders order_record
                ON order_record.platform_id = intent.platform_id
               AND order_record.order_id = intent.order_id
             WHERE reference.platform_id = %s
               AND reference.external_system = 'razorpay'
               AND reference.external_model = 'payment_order'
               AND reference.external_id = %s
            """,
            (platform_id, provider_reference_id),
        ).fetchone()

    def _reconcile_refund(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        receipt_id: UUID,
        event: GatewayEvent,
        correlation_id: UUID,
    ) -> tuple[str, str | None]:
        """reconcile-only: never creates a refund request, decision, or execution."""
        match = None
        if event.refund_id:
            match = connection.execute(
                """
                SELECT reference.external_reference_id, execution.refund_execution_id,
                       request.refund_request_id, request.order_id, request.amount,
                       request.currency_code
                  FROM zippy.external_references reference
                  JOIN zippy.refund_executions execution
                    ON execution.platform_id = reference.platform_id
                   AND execution.external_reference_id = reference.external_reference_id
                  JOIN zippy.refund_requests request
                    ON request.platform_id = execution.platform_id
                   AND request.refund_request_id = execution.refund_request_id
                 WHERE reference.platform_id = %s
                   AND reference.external_system = 'razorpay'
                   AND reference.external_model = 'refund'
                   AND reference.external_id = %s
                """,
                (platform_id, event.refund_id),
            ).fetchone()
        if match is None:
            self._raise_exception(
                connection, platform_id, "REFUND_EVENT_UNMATCHED", "high",
                "webhook_receipt", receipt_id,
                "refund.processed without an approved executed refund",
                correlation_id,
            )
            self._record_event(connection, platform_id, receipt_id,
                               "gateway.refund_unmatched", {}, correlation_id)
            return "recorded_only", None

        # The manually approved refund's own amount/currency are authoritative
        # and bound the projection; a webhook amount/currency mismatch is
        # reconciliation evidence only and never widens the trusted amount.
        expected_minor_units = major_units_to_minor(Decimal(match["amount"]))
        if (
            event.amount_minor_units is None
            or event.currency is None
            or event.amount_minor_units != expected_minor_units
            or event.currency != match["currency_code"]
        ):
            self._raise_exception(
                connection, platform_id, "REFUND_EVENT_AMOUNT_MISMATCH", "high",
                "webhook_receipt", receipt_id,
                "refund.processed amount/currency does not match the approved refund execution",
                correlation_id,
            )
            return "recorded_only", None

        gateway_event_id = self._record_gateway_event(
            connection, platform_id, receipt_id, event, match["order_id"], correlation_id,
            match["amount"], match["currency_code"],
        )
        connection.execute(
            """
            INSERT INTO zippy.payment_projections (
                platform_id, order_id, gateway_event_id, operational_status,
                amount, currency_code, correlation_id
            ) VALUES (%s, %s, %s, 'reversed', %s, %s, %s)
            ON CONFLICT (platform_id, order_id, gateway_event_id, operational_status) DO NOTHING
            """,
            (
                platform_id,
                match["order_id"],
                gateway_event_id,
                match["amount"],
                match["currency_code"],
                correlation_id,
            ),
        )
        connection.execute(
            """
            UPDATE zippy.external_references
               SET sync_status = 'synchronized', updated_at = clock_timestamp()
             WHERE platform_id = %s AND external_reference_id = %s
            """,
            (platform_id, match["external_reference_id"]),
        )
        self._record_event(connection, platform_id, receipt_id, "gateway.refund_reconciled", {
            "refund_request_id": str(match["refund_request_id"]),
        }, correlation_id)
        return "reconciled", "reversed"

    # ------------------------------------------------------------ receipt repair
    def reprocess_receipt(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        receipt_id: UUID,
        correlation_id: UUID,
        task_max_attempts: int,
    ) -> str:
        """Idempotent re-drive used by reconciliation sweeps after the fact."""
        row = connection.execute(
            """
            SELECT payload_reference
              FROM zippy.webhook_receipts
             WHERE platform_id = %s AND webhook_receipt_id = %s
             FOR UPDATE
            """,
            (platform_id, receipt_id),
        ).fetchone()
        if row is None:
            raise ConflictError("receipt not found")
        reference = json.loads(row["payload_reference"])
        event = GatewayEvent(
            provider="razorpay",
            provider_event_id="",
            event_type=reference["event_type"],
            provider_reference_id=reference.get("provider_reference_id"),
            payment_id=reference.get("payment_id"),
            refund_id=reference.get("refund_id"),
            amount_minor_units=reference.get("amount_minor_units"),
            currency=reference.get("currency"),
            notes=reference.get("notes") or {},
            evidence_hash="0" * 64,
        )
        outcome, _ = self._project_event(
            connection, platform_id, receipt_id, event, correlation_id, task_max_attempts
        )
        return outcome

    def sweep_stale_receipts(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        older_than_seconds: int,
        task_max_attempts: int,
        correlation_id: UUID,
    ) -> int:
        """Enqueue reconciliation tasks for receipts that never completed."""
        rows = connection.execute(
            """
            SELECT receipt.webhook_receipt_id
              FROM zippy.webhook_receipts receipt
             WHERE receipt.platform_id = %s
               AND receipt.received_at <= clock_timestamp() - make_interval(secs => %s)
               AND (
                    receipt.processing_status IN ('pending', 'processing', 'failed')
                    OR NOT EXISTS (
                        SELECT 1 FROM zippy.gateway_events gateway_event
                         WHERE gateway_event.platform_id = receipt.platform_id
                           AND gateway_event.webhook_receipt_id = receipt.webhook_receipt_id
                    )
               )
             ORDER BY receipt.received_at
             LIMIT 100
            """,
            (platform_id, older_than_seconds),
        ).fetchall()
        enqueued = 0
        for row in rows:
            inserted = connection.execute(
                """
                INSERT INTO zippy.durable_tasks (
                    durable_task_id, platform_id, task_type, aggregate_type,
                    aggregate_id, payload_reference, idempotency_key,
                    max_attempts, correlation_id
                ) VALUES (%s, %s, 'gateway_reconcile', 'webhook_receipt', %s, %s, %s, %s, %s)
                ON CONFLICT (platform_id, task_type, idempotency_key) DO NOTHING
                """,
                (
                    uuid4(),
                    platform_id,
                    row["webhook_receipt_id"],
                    f"webhook_receipt:{row['webhook_receipt_id']}",
                    f"reconcile:receipt:{row['webhook_receipt_id']}",
                    task_max_attempts,
                    correlation_id,
                ),
            ).rowcount
            enqueued += inserted
        return enqueued

    # ------------------------------------------------------------ POD + settlement
    def submit_pod(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order_id: UUID,
        object_key: str,
        content_type: str,
        byte_size: int,
        checksum_sha256: str,
        correlation_id: UUID,
    ) -> tuple[UUID, str, bool]:
        role = self._order_actor_role(connection, identity, order_id)
        if role not in ("admin", "vendor"):
            raise ForbiddenError("Actor is not authorized to submit POD evidence")
        trip = connection.execute(
            "SELECT trip_id FROM zippy.trips WHERE platform_id = %s AND order_id = %s",
            (identity.platform_id, order_id),
        ).fetchone()
        if trip is None:
            raise ConflictError("order has no trip for POD attachment")
        inserted = connection.execute(
            """
            INSERT INTO zippy.pod_documents (
                platform_id, order_id, trip_id, uploaded_by_account_id,
                object_key, content_type, byte_size, checksum_sha256
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id, object_key) DO NOTHING
            RETURNING pod_document_id, verification_status
            """,
            (
                identity.platform_id,
                order_id,
                trip["trip_id"],
                identity.account_id,
                object_key,
                content_type,
                byte_size,
                checksum_sha256,
            ),
        ).fetchone()
        if inserted is not None:
            return inserted["pod_document_id"], inserted["verification_status"], False
        existing = connection.execute(
            """
            SELECT pod_document_id, verification_status
              FROM zippy.pod_documents
             WHERE platform_id = %s AND object_key = %s
            """,
            (identity.platform_id, object_key),
        ).fetchone()
        if existing is None:
            raise ConflictError("POD document conflict could not be resolved")
        return existing["pod_document_id"], existing["verification_status"], True

    def decide_pod(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        pod_document_id: UUID,
        decision: str,
        reason: str,
        correlation_id: UUID,
        task_max_attempts: int,
    ) -> tuple[str, UUID | None]:
        if "admin" not in identity.roles:
            raise ForbiddenError("POD verification requires an admin actor")
        updated = connection.execute(
            """
            UPDATE zippy.pod_documents
               SET verification_status = %s,
                   verified_by_account_id = %s,
                   verified_at = clock_timestamp()
             WHERE platform_id = %s AND pod_document_id = %s
               AND verification_status IN ('pending', 'manual_review')
             RETURNING order_id
            """,
            (decision, identity.account_id, identity.platform_id, pod_document_id),
        ).fetchone()
        if updated is None:
            current = connection.execute(
                """
                SELECT verification_status FROM zippy.pod_documents
                 WHERE platform_id = %s AND pod_document_id = %s
                """,
                (identity.platform_id, pod_document_id),
            ).fetchone()
            if current is None:
                raise ConflictError("POD document not found")
            raise ConflictError(f"POD already decided: {current['verification_status']}")
        order_id = updated["order_id"]
        self._record_event(connection, identity.platform_id, pod_document_id,
                           f"pod.{decision}", {"reason": reason}, correlation_id,
                           actor_account_id=identity.account_id)
        if decision != "accepted":
            return decision, None
        connection.execute(
            """
            INSERT INTO zippy.durable_tasks (
                durable_task_id, platform_id, task_type, aggregate_type,
                aggregate_id, payload_reference, idempotency_key,
                max_attempts, correlation_id
            ) VALUES (%s, %s, 'pod_gate_evaluate', 'order', %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id, task_type, idempotency_key) DO NOTHING
            """,
            (
                uuid4(),
                identity.platform_id,
                order_id,
                f"order:{order_id}",
                f"pod-gate:{pod_document_id}",
                task_max_attempts,
                correlation_id,
            ),
        )
        return decision, self._ensure_settlement_projection(
            connection, identity.platform_id, order_id, identity.account_id, correlation_id
        ).settlement_projection_id

    def evaluate_settlement(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order_id: UUID,
        correlation_id: UUID,
    ) -> SettlementEligibility:
        self._order_actor_role(connection, identity, order_id)
        return self._ensure_settlement_projection(
            connection, identity.platform_id, order_id, identity.account_id, correlation_id
        )

    def _ensure_settlement_projection(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        order_id: UUID,
        actor_account_id: UUID | None,
        correlation_id: UUID,
    ) -> SettlementEligibility:
        """Projection-only eligibility. No money moves; Odoo stays authoritative."""
        connection.execute(
            "SELECT order_id FROM zippy.orders WHERE platform_id = %s AND order_id = %s FOR UPDATE",
            (platform_id, order_id),
        )
        existing = connection.execute(
            """
            SELECT settlement_projection_id FROM zippy.settlement_projections
             WHERE platform_id = %s AND order_id = %s
             ORDER BY created_at LIMIT 1
            """,
            (platform_id, order_id),
        ).fetchone()
        if existing is not None:
            return SettlementEligibility(
                order_id, True, existing["settlement_projection_id"], "already_evaluated"
            )
        accepted = connection.execute(
            """
            SELECT count(*) AS accepted_count FROM zippy.pod_documents
             WHERE platform_id = %s AND order_id = %s AND verification_status = 'accepted'
            """,
            (platform_id, order_id),
        ).fetchone()
        if accepted is None or accepted["accepted_count"] == 0:
            return SettlementEligibility(order_id, False, None, "pod_not_accepted")
        created = connection.execute(
            """
            INSERT INTO zippy.settlement_projections (
                platform_id, order_id, financial_request_id, operational_status,
                correlation_id
            ) VALUES (%s, %s, NULL, 'not_requested', %s)
            RETURNING settlement_projection_id
            """,
            (platform_id, order_id, correlation_id),
        ).fetchone()
        if created is None:
            raise RuntimeError("settlement projection persistence failed")
        self._record_event(connection, platform_id, order_id,
                           "settlement.eligibility_evaluated",
                           {"result": "eligible"}, correlation_id,
                           actor_account_id=actor_account_id)
        return SettlementEligibility(
            order_id, True, created["settlement_projection_id"], "eligible"
        )

    # ------------------------------------------------------------ manual refunds
    def request_refund(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order_id: UUID,
        amount: Decimal,
        currency_code: str,
        target_reference: str,
        reason: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[UUID, str, bool]:
        role = self._order_actor_role(connection, identity, order_id)
        if role not in ("admin", "customer"):
            raise ForbiddenError("Actor is not authorized to request a refund")
        inserted = connection.execute(
            """
            INSERT INTO zippy.refund_requests (
                platform_id, order_id, requester_account_id, amount, currency_code,
                target_reference, reason, idempotency_key, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id, idempotency_key) DO NOTHING
            RETURNING refund_request_id, status
            """,
            (
                identity.platform_id,
                order_id,
                identity.account_id,
                amount,
                currency_code,
                target_reference,
                reason,
                idempotency_key,
                correlation_id,
            ),
        ).fetchone()
        if inserted is not None:
            self._record_event(connection, identity.platform_id, order_id,
                               "refund.requested", {"reason": reason}, correlation_id,
                               actor_account_id=identity.account_id)
            return inserted["refund_request_id"], inserted["status"], False
        existing = connection.execute(
            """
            SELECT refund_request_id, status, order_id, requester_account_id,
                   amount, currency_code, target_reference
              FROM zippy.refund_requests
             WHERE platform_id = %s AND idempotency_key = %s
             FOR UPDATE
            """,
            (identity.platform_id, idempotency_key),
        ).fetchone()
        if existing is None:
            raise ConflictError("refund request conflict could not be resolved")
        fingerprint = (
            existing["order_id"] == order_id
            and existing["requester_account_id"] == identity.account_id
            and Decimal(existing["amount"]) == amount
            and existing["currency_code"] == currency_code
            and existing["target_reference"] == target_reference
        )
        if not fingerprint:
            raise ConflictError("Idempotency key was already used with a different request")
        return existing["refund_request_id"], existing["status"], True

    def decide_refund(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        refund_request_id: UUID,
        decision: str,
        reason: str,
        correlation_id: UUID,
    ) -> tuple[UUID, str]:
        if "admin" not in identity.roles:
            raise ForbiddenError("refund decisions require an admin actor")
        request = connection.execute(
            """
            SELECT status, requester_account_id FROM zippy.refund_requests
             WHERE platform_id = %s AND refund_request_id = %s
             FOR UPDATE
            """,
            (identity.platform_id, refund_request_id),
        ).fetchone()
        if request is None:
            raise ConflictError("refund request not found")
        if request["requester_account_id"] == identity.account_id:
            raise ForbiddenError("refund requester cannot approve own request")
        if request["status"] != "requested":
            raise ConflictError(f"refund already decided: {request['status']}")
        inserted = connection.execute(
            """
            INSERT INTO zippy.refund_decisions (
                platform_id, refund_request_id, approver_account_id, decision,
                reason, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING refund_decision_id
            """,
            (
                identity.platform_id,
                refund_request_id,
                identity.account_id,
                decision,
                reason,
                correlation_id,
            ),
        ).fetchone()
        if inserted is None:
            raise RuntimeError("refund decision persistence failed")
        connection.execute(
            """
            UPDATE zippy.refund_requests SET status = %s
             WHERE platform_id = %s AND refund_request_id = %s
            """,
            (decision, identity.platform_id, refund_request_id),
        )
        self._record_event(connection, identity.platform_id, refund_request_id,
                           f"refund.{decision}", {"reason": reason}, correlation_id,
                           actor_account_id=identity.account_id)
        return inserted["refund_decision_id"], decision

    def record_refund_execution(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        refund_request_id: UUID,
        gateway_refund_id: str,
        evidence_hash_sha256: str,
        executed_at: datetime,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[UUID, str]:
        """Record execution evidence for a manually approved refund.

        The database trigger enforces an approved decision by a different
        account with exact amount/currency/target binding. No provider call.
        """
        if "admin" not in identity.roles:
            raise ForbiddenError("refund execution evidence requires an admin actor")
        request = connection.execute(
            """
            SELECT order_id, amount, currency_code, target_reference, status
              FROM zippy.refund_requests
             WHERE platform_id = %s AND refund_request_id = %s
             FOR UPDATE
            """,
            (identity.platform_id, refund_request_id),
        ).fetchone()
        if request is None:
            raise ConflictError("refund request not found")
        if request["status"] == "executed":
            # Idempotent replay path: only the original execution may return.
            replay = connection.execute(
                """
                SELECT refund_execution_id, refund_request_id
                  FROM zippy.refund_executions
                 WHERE platform_id = %s AND idempotency_key = %s
                """,
                (identity.platform_id, idempotency_key),
            ).fetchone()
            if replay is not None and replay["refund_request_id"] == refund_request_id:
                return replay["refund_execution_id"], "executed"
            raise ConflictError("refund already executed with a different request")
        if request["status"] != "approved":
            raise ConflictError("refund execution requires an approved manual decision")
        decision = connection.execute(
            """
            SELECT refund_decision_id FROM zippy.refund_decisions
             WHERE platform_id = %s AND refund_request_id = %s
            """,
            (identity.platform_id, refund_request_id),
        ).fetchone()
        if decision is None:
            raise ConflictError("refund execution requires an approved manual decision")

        reference = connection.execute(
            """
            INSERT INTO zippy.external_references (
                platform_id, local_entity_type, local_entity_id, external_system,
                external_model, external_id, sync_status, correlation_id
            ) VALUES (%s, 'refund_request', %s, 'razorpay', 'refund', %s, 'pending', %s)
            ON CONFLICT (platform_id, external_system, external_model, external_id) DO NOTHING
            RETURNING external_reference_id
            """,
            (
                identity.platform_id,
                refund_request_id,
                gateway_refund_id,
                correlation_id,
            ),
        ).fetchone()
        if reference is None:
            reference = connection.execute(
                """
                SELECT external_reference_id, local_entity_id
                  FROM zippy.external_references
                 WHERE platform_id = %s AND external_system = 'razorpay'
                   AND external_model = 'refund' AND external_id = %s
                """,
                (identity.platform_id, gateway_refund_id),
            ).fetchone()
            if reference is None:
                raise RuntimeError("external reference persistence failed")
            if reference["local_entity_id"] != refund_request_id:
                raise ConflictError("gateway refund id is already bound to another request")

        inserted = connection.execute(
            """
            INSERT INTO zippy.refund_executions (
                platform_id, refund_request_id, refund_decision_id,
                external_reference_id, amount, currency_code, target_reference,
                idempotency_key, evidence_hash_sha256, executed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id, idempotency_key) DO NOTHING
            RETURNING refund_execution_id
            """,
            (
                identity.platform_id,
                refund_request_id,
                decision["refund_decision_id"],
                reference["external_reference_id"],
                request["amount"],
                request["currency_code"],
                request["target_reference"],
                idempotency_key,
                evidence_hash_sha256,
                executed_at,
            ),
        ).fetchone()
        if inserted is None:
            existing = connection.execute(
                """
                SELECT refund_execution_id, refund_request_id
                  FROM zippy.refund_executions
                 WHERE platform_id = %s AND idempotency_key = %s
                """,
                (identity.platform_id, idempotency_key),
            ).fetchone()
            if existing is None or existing["refund_request_id"] != refund_request_id:
                raise ConflictError("Idempotency key was already used with a different request")
            return existing["refund_execution_id"], "executed"
        connection.execute(
            """
            UPDATE zippy.refund_requests SET status = 'executed'
             WHERE platform_id = %s AND refund_request_id = %s
            """,
            (identity.platform_id, refund_request_id),
        )
        self._record_event(connection, identity.platform_id, refund_request_id,
                           "refund.execution_recorded",
                           {"evidence_hash_sha256": evidence_hash_sha256}, correlation_id,
                           actor_account_id=identity.account_id)
        return inserted["refund_execution_id"], "executed"

    # ------------------------------------------------------------ Odoo references
    def lock_financial_request(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        financial_request_id: UUID,
    ) -> dict[str, Any] | None:
        return connection.execute(
            """
            SELECT request.financial_request_id, request.order_id, request.request_type,
                   request.amount, request.currency_code, request.status,
                   account.email_normalized
              FROM zippy.financial_requests request
              JOIN zippy.orders order_record
                ON order_record.platform_id = request.platform_id
               AND order_record.order_id = request.order_id
              JOIN zippy.customer_profiles customer
                ON customer.platform_id = order_record.platform_id
               AND customer.customer_profile_id = order_record.booking_customer_profile_id
              JOIN zippy.accounts account
                ON account.platform_id = customer.platform_id
               AND account.account_id = customer.account_id
             WHERE request.platform_id = %s AND request.financial_request_id = %s
             FOR UPDATE OF request
            """,
            (platform_id, financial_request_id),
        ).fetchone()

    def record_partner_reference(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        order_id: UUID,
        partner_id: int,
        correlation_id: UUID,
    ) -> UUID:
        row = connection.execute(
            """
            INSERT INTO zippy.external_references (
                platform_id, local_entity_type, local_entity_id, external_system,
                external_model, external_id, sync_status, correlation_id
            ) VALUES (%s, 'order', %s, 'odoo', 'res.partner', %s, 'synchronized', %s)
            ON CONFLICT (platform_id, local_entity_type, local_entity_id,
                         external_system, external_model) DO NOTHING
            RETURNING external_reference_id
            """,
            (platform_id, order_id, str(partner_id), correlation_id),
        ).fetchone()
        if row is not None:
            return UUID(str(row["external_reference_id"]))
        existing = connection.execute(
            """
            SELECT external_reference_id, external_id FROM zippy.external_references
             WHERE platform_id = %s AND local_entity_type = 'order'
               AND local_entity_id = %s AND external_system = 'odoo'
               AND external_model = 'res.partner'
            """,
            (platform_id, order_id),
        ).fetchone()
        if existing is None:
            raise RuntimeError("partner reference persistence failed")
        if existing["external_id"] != str(partner_id):
            raise ConflictError("order already references a different Odoo partner")
        return UUID(str(existing["external_reference_id"]))

    def record_move_reference(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        financial_request_id: UUID,
        move_id: int,
        correlation_id: UUID,
    ) -> UUID:
        row = connection.execute(
            """
            INSERT INTO zippy.external_references (
                platform_id, local_entity_type, local_entity_id, external_system,
                external_model, external_id, sync_status, correlation_id
            ) VALUES (%s, 'financial_request', %s, 'odoo', 'account.move', %s, 'synchronized', %s)
            ON CONFLICT (platform_id, local_entity_type, local_entity_id,
                         external_system, external_model) DO NOTHING
            RETURNING external_reference_id
            """,
            (platform_id, financial_request_id, str(move_id), correlation_id),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                """
                SELECT external_reference_id, external_id FROM zippy.external_references
                 WHERE platform_id = %s AND local_entity_type = 'financial_request'
                   AND local_entity_id = %s AND external_system = 'odoo'
                   AND external_model = 'account.move'
                """,
                (platform_id, financial_request_id),
            ).fetchone()
            if existing is None:
                raise RuntimeError("move reference persistence failed")
            if existing["external_id"] != str(move_id):
                raise ConflictError("financial request already references a different Odoo move")
            reference_id = UUID(str(existing["external_reference_id"]))
        else:
            reference_id = UUID(str(row["external_reference_id"]))
        connection.execute(
            """
            UPDATE zippy.financial_requests
               SET status = 'acknowledged', updated_at = clock_timestamp()
             WHERE platform_id = %s AND financial_request_id = %s
               AND status IN ('requested', 'sent')
            """,
            (platform_id, financial_request_id),
        )
        return reference_id

    # ------------------------------------------------------------ shared helpers
    def _record_gateway_event(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        receipt_id: UUID,
        event: GatewayEvent,
        order_id: UUID,
        correlation_id: UUID,
        amount: Decimal,
        currency: str,
    ) -> UUID:
        row = connection.execute(
            """
            INSERT INTO zippy.gateway_events (
                platform_id, webhook_receipt_id, order_id, gateway,
                gateway_event_type, amount, currency_code, evidence_hash_sha256,
                verified_at
            ) VALUES (%s, %s, %s, 'razorpay', %s, %s, %s, %s, clock_timestamp())
            ON CONFLICT (platform_id, webhook_receipt_id) DO NOTHING
            RETURNING gateway_event_id
            """,
            (
                platform_id,
                receipt_id,
                order_id,
                event.event_type,
                amount,
                currency,
                event.evidence_hash,
            ),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                """
                SELECT gateway_event_id FROM zippy.gateway_events
                 WHERE platform_id = %s AND webhook_receipt_id = %s
                """,
                (platform_id, receipt_id),
            ).fetchone()
            if existing is None:
                raise RuntimeError("gateway evidence persistence failed")
            return UUID(str(existing["gateway_event_id"]))
        return UUID(str(row["gateway_event_id"]))

    def _enqueue_odoo_draft(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        order_id: UUID,
        created_by_account_id: UUID,
        amount: Decimal,
        currency: str,
        correlation_id: UUID,
        task_max_attempts: int,
    ) -> None:
        request_key = f"odoo:draft_customer_invoice:{order_id}"
        request_hash = _sha256_json(
            {
                "order_id": str(order_id),
                "request_type": "draft_customer_invoice",
                "amount": str(amount),
                "currency": currency,
            }
        )
        request = connection.execute(
            """
            INSERT INTO zippy.financial_requests (
                platform_id, order_id, request_type, amount, currency_code, status,
                requester_account_id, idempotency_key, request_hash_sha256, correlation_id
            ) VALUES (%s, %s, 'draft_customer_invoice', %s, %s, 'requested', %s, %s, %s, %s)
            ON CONFLICT (platform_id, request_type, idempotency_key) DO NOTHING
            RETURNING financial_request_id
            """,
            (
                platform_id,
                order_id,
                amount,
                currency,
                created_by_account_id,
                request_key,
                request_hash,
                correlation_id,
            ),
        ).fetchone()
        if request is None:
            request = connection.execute(
                """
                SELECT financial_request_id FROM zippy.financial_requests
                 WHERE platform_id = %s AND request_type = 'draft_customer_invoice'
                   AND idempotency_key = %s
                """,
                (platform_id, request_key),
            ).fetchone()
        if request is None:
            raise RuntimeError("financial request persistence failed")
        connection.execute(
            """
            INSERT INTO zippy.durable_tasks (
                durable_task_id, platform_id, task_type, aggregate_type,
                aggregate_id, payload_reference, idempotency_key,
                max_attempts, correlation_id
            ) VALUES (%s, %s, 'odoo_draft_sync', 'financial_request', %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id, task_type, idempotency_key) DO NOTHING
            """,
            (
                uuid4(),
                platform_id,
                request["financial_request_id"],
                f"financial_request:{request['financial_request_id']}",
                request_key,
                task_max_attempts,
                correlation_id,
            ),
        )

    def _order_actor_role(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order_id: UUID,
    ) -> str:
        row = connection.execute(
            """
            SELECT customer_participant.customer_profile_id AS customer_profile_id,
                   vendor_profile.account_id AS vendor_account_id
              FROM zippy.orders order_record
              LEFT JOIN zippy.transaction_participants customer_participant
                ON customer_participant.platform_id = order_record.platform_id
               AND customer_participant.order_id = order_record.order_id
               AND customer_participant.participant_role = 'customer'
              LEFT JOIN zippy.transaction_participants vendor_participant
                ON vendor_participant.platform_id = order_record.platform_id
               AND vendor_participant.order_id = order_record.order_id
               AND vendor_participant.participant_role = 'vendor'
              LEFT JOIN zippy.vendor_profiles vendor_profile
                ON vendor_profile.platform_id = order_record.platform_id
               AND vendor_profile.vendor_profile_id = vendor_participant.vendor_profile_id
             WHERE order_record.platform_id = %s AND order_record.order_id = %s
            """,
            (identity.platform_id, order_id),
        ).fetchone()
        if row is None:
            raise ConflictError("order not found")
        if "admin" in identity.roles:
            return "admin"
        if (
            identity.customer_profile_id is not None
            and row["customer_profile_id"] == identity.customer_profile_id
        ):
            return "customer"
        if row["vendor_account_id"] is not None and row["vendor_account_id"] == identity.account_id:
            return "vendor"
        raise ForbiddenError("Actor is not a participant of this order")

    def _record_event(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        aggregate_id: UUID,
        event_type: str,
        event_data: dict[str, Any],
        correlation_id: UUID,
        actor_account_id: UUID | None = None,
        aggregate_type: str = "webhook_receipt",
    ) -> None:
        connection.execute(
            """
            INSERT INTO zippy.operational_events (
                platform_id, aggregate_type, aggregate_id, aggregate_version,
                event_type, event_data, actor_account_id, correlation_id
            )
            SELECT %s, %s, %s,
                   coalesce((
                       SELECT max(aggregate_version) + 1 FROM zippy.operational_events
                        WHERE platform_id = %s AND aggregate_type = %s AND aggregate_id = %s
                   ), 1),
                   %s, %s, %s, %s
            """,
            (
                platform_id,
                aggregate_type,
                aggregate_id,
                platform_id,
                aggregate_type,
                aggregate_id,
                event_type,
                Jsonb(event_data),
                actor_account_id,
                correlation_id,
            ),
        )

    def _record_outbox(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        receipt_id: UUID,
        event: GatewayEvent,
        payload: dict[str, Any],
        correlation_id: UUID,
    ) -> None:
        connection.execute(
            """
            INSERT INTO zippy.event_outbox (
                platform_id, aggregate_type, aggregate_id, aggregate_version,
                event_type, destination, payload, idempotency_key, correlation_id
            ) VALUES (%s, 'webhook_receipt', %s, 1, %s, 'sse_projection', %s, %s, %s)
            ON CONFLICT (platform_id, destination, idempotency_key) DO NOTHING
            """,
            (
                platform_id,
                receipt_id,
                event.event_type,
                Jsonb(payload),
                f"outbox:{event.provider}:{event.provider_event_id}",
                correlation_id,
            ),
        )

    def _raise_exception(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        code: str,
        severity: str,
        entity_type: str,
        entity_id: UUID,
        reason: str,
        correlation_id: UUID,
    ) -> None:
        connection.execute(
            """
            INSERT INTO zippy.operational_exceptions (
                platform_id, exception_code, severity, entity_type, entity_id,
                reason, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (platform_id, code, severity, entity_type, entity_id, reason, correlation_id),
        )
