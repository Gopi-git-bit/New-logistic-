"""Deterministic PostgreSQL task and outbox workers for M3."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from .config import Settings
from .database import Database
from .repositories import retry_at


class EventTransport(Protocol):
    def deliver(self, event_id: UUID, payload: dict[str, Any]) -> None: ...


class InProcessTransport:
    def __init__(self) -> None:
        self.delivered: dict[UUID, dict[str, Any]] = {}

    def deliver(self, event_id: UUID, payload: dict[str, Any]) -> None:
        self.delivered.setdefault(event_id, payload)


class CoreWorker:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    def run_tasks(
        self,
        worker_id: str,
        handler: Callable[[dict[str, Any]], None],
        limit: int = 10,
    ) -> int:
        with self.database.transaction(self.settings.platform_id) as connection:
            tasks = connection.execute(
                "SELECT * FROM zippy.claim_durable_tasks(%s, 'order_intake', %s, %s, %s)",
                (
                    self.settings.platform_id,
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
                    status = failure_row["status"]
                    if status == "dead_lettered":
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

    def publish_outbox(
        self, worker_id: str, transport: EventTransport, limit: int = 10
    ) -> int:
        with self.database.transaction(self.settings.platform_id) as connection:
            events = connection.execute(
                "SELECT * FROM zippy.claim_outbox_events(%s, %s, %s, %s)",
                (
                    self.settings.platform_id,
                    worker_id,
                    min(max(limit, 1), 100),
                    self.settings.task_lease_seconds,
                ),
            ).fetchall()
        for event in events:
            try:
                transport.deliver(event["outbox_event_id"], event["payload"])
                with self.database.transaction(self.settings.platform_id) as connection:
                    completion_row = connection.execute(
                        "SELECT zippy.complete_outbox_event(%s, %s, %s) AS completed",
                        (
                            self.settings.platform_id,
                            event["outbox_event_id"],
                            worker_id,
                        ),
                    ).fetchone()
                    if completion_row is None:
                        raise RuntimeError("outbox completion returned no result")
                    completed = completion_row["completed"]
                    if not completed:
                        raise RuntimeError("outbox lease was lost")
            except Exception as exc:  # noqa: BLE001 - transports enter durable retry
                with self.database.transaction(self.settings.platform_id) as connection:
                    connection.execute(
                        "SELECT zippy.fail_outbox_event(%s, %s, %s, %s, %s)",
                        (
                            self.settings.platform_id,
                            event["outbox_event_id"],
                            worker_id,
                            type(exc).__name__,
                            retry_at(
                                event["attempt_count"],
                                self.settings.retry_base_seconds,
                                self.settings.retry_max_seconds,
                            ),
                        ),
                    )
        return len(events)
