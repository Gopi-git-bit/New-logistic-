"""M4 durable finance workers: gateway reconciliation, POD gate, Odoo drafts.

Uses the same claim/lease/fail controls as the M3 worker but with explicit
M4 task types. External Odoo calls happen outside the database transaction;
references are recorded idempotently so timeout-after-success cannot create
duplicates. No automatic financial execution exists anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from .config import Settings
from .database import Database
from .odoo import OdooDraftAdapter
from .repositories import retry_at
from .repositories_finance import FinanceRepository

TaskHandler = Callable[[dict[str, Any]], None]


class FinanceWorker:
    """Claim/run/fail loop for M4 task types, mirroring CoreWorker semantics."""

    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    def run_tasks(
        self,
        worker_id: str,
        task_type: str,
        handler: TaskHandler,
        limit: int = 10,
    ) -> int:
        with self.database.transaction(self.settings.platform_id) as connection:
            tasks = connection.execute(
                "SELECT * FROM zippy.claim_durable_tasks(%s, %s, %s, %s, %s)",
                (
                    self.settings.platform_id,
                    task_type,
                    worker_id,
                    self.settings.task_lease_seconds,
                    min(max(limit, 1), 100),
                ),
            ).fetchall()
        for task in tasks:
            try:
                handler(task)
                with self.database.transaction(self.settings.platform_id) as connection:
                    updated = connection.execute(
                        """
                        UPDATE zippy.durable_tasks
                           SET status = 'succeeded', lease_owner = NULL, lease_expires_at = NULL,
                               updated_at = clock_timestamp()
                         WHERE platform_id = %s AND durable_task_id = %s
                           AND status = 'processing' AND lease_owner = %s
                        """,
                        (self.settings.platform_id, task["durable_task_id"], worker_id),
                    ).rowcount
                    if updated != 1:
                        raise RuntimeError("task lease was lost")
            except Exception as exc:  # noqa: BLE001 - handlers enter durable retry
                with self.database.transaction(self.settings.platform_id) as connection:
                    failure_row = connection.execute(
                        "SELECT zippy.fail_durable_task(%s, %s, %s, %s, %s) AS status",
                        (
                            self.settings.platform_id,
                            task["durable_task_id"],
                            worker_id,
                            type(exc).__name__,
                            retry_at(
                                task["attempt_count"],
                                self.settings.retry_base_seconds,
                                self.settings.retry_max_seconds,
                            ),
                        ),
                    ).fetchone()
                    if failure_row is None:
                        raise RuntimeError("task failure returned no status")
                    if failure_row["status"] == "dead_lettered":
                        connection.execute(
                            """
                            INSERT INTO zippy.operational_exceptions (
                                platform_id, exception_code, severity, entity_type, entity_id, reason, correlation_id
                            ) VALUES (%s, 'TASK_TERMINAL_FAILURE', 'high', 'task', %s, %s, %s)
                            """,
                            (
                                self.settings.platform_id,
                                task["durable_task_id"],
                                type(exc).__name__,
                                task["correlation_id"],
                            ),
                        )
        return len(tasks)


def _reference_id(task: dict[str, Any], prefix: str) -> UUID:
    reference = str(task["payload_reference"])
    if not reference.startswith(prefix):
        raise ValueError("unexpected payload reference")
    return UUID(reference.removeprefix(prefix))


def odoo_draft_sync_handler(
    database: Database, settings: Settings, adapter: OdooDraftAdapter
) -> TaskHandler:
    """Process one draft-only financial request against the Odoo transport."""

    repository = FinanceRepository()

    def handle(task: dict[str, Any]) -> None:
        financial_request_id = _reference_id(task, "financial_request:")
        with database.transaction(settings.platform_id) as connection:
            request = repository.lock_financial_request(
                connection, settings.platform_id, financial_request_id
            )
        if request is None:
            return  # already acknowledged or removed; idempotent no-op
        if request["status"] not in ("requested", "sent"):
            return  # timeout-after-success: external side effect already recorded

        email = request["email_normalized"] or f"order-{request['order_id']}@example.invalid"
        name = f"Zippy order {request['order_id']}"
        partner_id = adapter.find_or_create_partner(email=email, name=name)
        reference = f"zippy:{request['request_type']}:{financial_request_id}"
        amount = str(request["amount"]) if request["amount"] is not None else "0"
        currency = request["currency_code"] or "INR"
        if request["request_type"] == "draft_vendor_bill":
            move_id = adapter.create_draft_vendor_bill(partner_id, reference, amount, currency)
        else:
            move_id = adapter.create_draft_customer_invoice(
                partner_id, reference, amount, currency
            )

        with database.transaction(settings.platform_id) as connection:
            repository.record_partner_reference(
                connection, settings.platform_id, request["order_id"], partner_id,
                task["correlation_id"],
            )
            repository.record_move_reference(
                connection, settings.platform_id, financial_request_id, move_id,
                task["correlation_id"],
            )
            repository._record_event(
                connection, settings.platform_id, financial_request_id,
                "odoo.draft_acknowledged", {"request_type": request["request_type"]},
                task["correlation_id"], aggregate_type="financial_request",
            )

    return handle


def gateway_reconcile_handler(database: Database, settings: Settings) -> TaskHandler:
    """Re-drive one receipt's projection idempotently (stale/unmatched sweep)."""

    repository = FinanceRepository()

    def handle(task: dict[str, Any]) -> None:
        receipt_id = _reference_id(task, "webhook_receipt:")
        with database.transaction(settings.platform_id) as connection:
            repository.reprocess_receipt(
                connection,
                settings.platform_id,
                receipt_id,
                task["correlation_id"],
                settings.task_max_attempts,
            )

    return handle


def pod_gate_handler(database: Database, settings: Settings) -> TaskHandler:
    """Evaluate settlement eligibility once accepted POD evidence exists."""

    repository = FinanceRepository()

    def handle(task: dict[str, Any]) -> None:
        order_id = _reference_id(task, "order:")
        with database.transaction(settings.platform_id) as connection:
            result = repository._ensure_settlement_projection(
                connection, settings.platform_id, order_id, None, task["correlation_id"]
            )
        if not result.eligible:
            raise RuntimeError("pod_gate_not_ready")

    return handle


def refund_reconcile_handler(database: Database, settings: Settings) -> TaskHandler:
    """Re-drive a refund.processed receipt; unmatched events stay evidence-only."""

    return gateway_reconcile_handler(database, settings)
