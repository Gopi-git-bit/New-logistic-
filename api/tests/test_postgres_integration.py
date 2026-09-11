from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from api.config import Settings
from api.database import Database
from api.main import create_app
from api.worker import CoreWorker, InProcessTransport

DATABASE_URL = os.environ.get("ZIPPY_M3_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="requires the isolated M3 PostgreSQL proof"
)


def _token(settings: Settings, subject: str) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "aud": "zippy-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.auth_jwt_secret,
        algorithm="HS256",
    )


def _headers(settings: Settings, subject: str, idempotency_key: UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token(settings, subject)}",
        "Idempotency-Key": str(idempotency_key),
        "X-Correlation-ID": str(uuid4()),
    }


def _payload() -> dict[str, object]:
    return {
        "pickup": {
            "address": "Pune",
            "latitude": "18.5204",
            "longitude": "73.8567",
            "accuracy_meters": "5",
        },
        "delivery": {
            "address": "Mumbai",
            "latitude": "19.0760",
            "longitude": "72.8777",
            "accuracy_meters": "7",
        },
        "cargo_description": "M3 integration cartons",
        "cargo_weight_kg": "20.000",
        "distance_km": "150.000",
        "service": {"vehicle_class": "light", "body_type": "closed"},
        "requested_pickup_at": "2030-01-02T10:00:00+05:30",
    }


def _query(settings: Settings, sql: str, parameters: tuple = ()) -> list[dict]:
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        connection.execute(
            "SELECT set_config('zippy.platform_id', %s, false)",
            (str(settings.platform_id),),
        )
        connection.execute(
            "SELECT set_config('zippy.account_id', %s, false)",
            ("a0000000-0000-0000-0000-000000000001",),
        )
        return connection.execute(sql, parameters).fetchall()


def test_order_transition_and_worker_flow(settings: Settings):
    integration_settings = replace(
        settings,
        database_url=DATABASE_URL or "",
        retry_base_seconds=0,
        retry_max_seconds=0,
    )
    database = Database(integration_settings.database_url)
    order_key = uuid4()
    payload = _payload()

    with TestClient(create_app(integration_settings, database)) as client:
        first = client.post(
            "/api/v1/orders",
            json=payload,
            headers=_headers(integration_settings, "customer-subject", order_key),
        )
        assert first.status_code == 202, first.text
        accepted = first.json()
        assert accepted["status"] == "pending"
        assert accepted["idempotency_replay"] is False

        replay = client.post(
            "/api/v1/orders",
            json=payload,
            headers=_headers(integration_settings, "customer-subject", order_key),
        )
        assert replay.status_code == 202, replay.text
        assert replay.json()["order_id"] == accepted["order_id"]
        assert replay.json()["workflow_id"] == accepted["workflow_id"]
        assert replay.json()["idempotency_replay"] is True

        changed = _payload()
        changed["cargo_weight_kg"] = "21.000"
        conflict = client.post(
            "/api/v1/orders",
            json=changed,
            headers=_headers(integration_settings, "customer-subject", order_key),
        )
        assert (conflict.status_code, conflict.json()["error"]["code"]) == (
            409,
            "IDEMPOTENCY_CONFLICT",
        )

        blocked = client.post(
            "/api/v1/orders",
            json=_payload(),
            headers=_headers(integration_settings, "blocked-subject", uuid4()),
        )
        assert (blocked.status_code, blocked.json()["error"]["code"]) == (
            403,
            "FORBIDDEN",
        )

        transition = {
            "expected_status": "pending",
            "expected_version": 1,
            "next_status": "quoted",
            "reason": "quote accepted",
        }
        transition_key = uuid4()
        transitioned = client.post(
            f"/api/v1/orders/{accepted['order_id']}/transitions",
            json=transition,
            headers=_headers(integration_settings, "customer-subject", transition_key),
        )
        assert transitioned.status_code == 200, transitioned.text
        assert (transitioned.json()["status"], transitioned.json()["version"]) == (
            "quoted",
            2,
        )

        transition_replay = client.post(
            f"/api/v1/orders/{accepted['order_id']}/transitions",
            json=transition,
            headers=_headers(integration_settings, "customer-subject", transition_key),
        )
        assert transition_replay.status_code == 200, transition_replay.text
        assert (
            transition_replay.json()["status"],
            transition_replay.json()["version"],
        ) == ("quoted", 2)

        denied = client.post(
            f"/api/v1/orders/{accepted['order_id']}/transitions",
            json={
                "expected_status": "quoted",
                "expected_version": 2,
                "next_status": "confirmed",
                "reason": "unauthorized",
            },
            headers=_headers(integration_settings, "other-customer-subject", uuid4()),
        )
        assert (denied.status_code, denied.json()["error"]["code"]) == (
            403,
            "FORBIDDEN",
        )

        illegal = client.post(
            f"/api/v1/orders/{accepted['order_id']}/transitions",
            json={
                "expected_status": "quoted",
                "expected_version": 2,
                "next_status": "delivered",
                "reason": "illegal jump",
            },
            headers=_headers(integration_settings, "admin-subject", uuid4()),
        )
        assert (illegal.status_code, illegal.json()["error"]["code"]) == (
            409,
            "TRANSITION_CONFLICT",
        )

    order_id = UUID(accepted["order_id"])
    rows = _query(
        integration_settings,
        """
        SELECT
            (SELECT count(*) FROM zippy.orders WHERE order_id = %s) AS orders,
            (SELECT count(*) FROM zippy.order_stops WHERE order_id = %s) AS stops,
            (SELECT count(*) FROM zippy.service_commitments WHERE order_id = %s) AS commitments,
            (SELECT count(*) FROM zippy.durable_tasks WHERE aggregate_id = %s) AS tasks,
            (SELECT count(*) FROM zippy.operational_events WHERE aggregate_id = %s) AS events,
            (SELECT count(*) FROM zippy.event_outbox WHERE aggregate_id = %s) AS outbox,
            (SELECT count(*) FROM zippy.idempotency_records WHERE response_reference = %s) AS idempotency
        """,
        (order_id, order_id, order_id, order_id, order_id, order_id, str(order_id)),
    )[0]
    assert rows == {
        "orders": 1,
        "stops": 2,
        "commitments": 1,
        "tasks": 1,
        "events": 2,
        "outbox": 2,
        "idempotency": 2,
    }

    worker_database = Database(integration_settings.database_url)
    worker_database.open()
    try:
        worker = CoreWorker(worker_database, integration_settings)
        assert worker.run_tasks("m3-success-worker", lambda task: None) == 1
        transport = InProcessTransport()
        assert worker.publish_outbox("m3-outbox-worker", transport) == 2
        assert worker.publish_outbox("m3-outbox-worker", transport) == 0
        assert len(transport.delivered) == 2
    finally:
        worker_database.close()


def test_task_and_outbox_terminal_failures_create_evidence(settings: Settings):
    integration_settings = replace(
        settings,
        database_url=DATABASE_URL or "",
        retry_base_seconds=0,
        retry_max_seconds=0,
    )
    database = Database(integration_settings.database_url)
    database.open()
    task_id = uuid4()
    event_id = uuid4()
    aggregate_id = uuid4()
    correlation_id = uuid4()
    try:
        with database.transaction(integration_settings.platform_id) as connection:
            connection.execute(
                """
                INSERT INTO zippy.durable_tasks (
                    durable_task_id, platform_id, task_type, aggregate_type, aggregate_id,
                    payload_reference, idempotency_key, max_attempts, correlation_id
                ) VALUES (%s, %s, 'order_intake', 'synthetic', %s, 'synthetic', %s, 3, %s)
                """,
                (
                    task_id,
                    integration_settings.platform_id,
                    aggregate_id,
                    str(uuid4()),
                    correlation_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO zippy.event_outbox (
                    outbox_event_id, platform_id, aggregate_type, aggregate_id, aggregate_version,
                    event_type, destination, payload, idempotency_key, max_attempts, correlation_id
                ) VALUES (%s, %s, 'synthetic', %s, 1, 'synthetic.failed', 'internal', '{}', %s, 3, %s)
                """,
                (
                    event_id,
                    integration_settings.platform_id,
                    aggregate_id,
                    str(uuid4()),
                    correlation_id,
                ),
            )

        worker = CoreWorker(database, integration_settings)

        def fail(_record):
            raise RuntimeError("synthetic failure details must not escape")

        for _ in range(3):
            assert worker.run_tasks("m3-failure-worker", fail) == 1
            assert (
                worker.publish_outbox(
                    "m3-failure-worker",
                    type("FailingTransport", (), {"deliver": staticmethod(fail)})(),
                )
                == 1
            )

        terminal = _query(
            integration_settings,
            """
            SELECT
                (SELECT status FROM zippy.durable_tasks WHERE durable_task_id = %s) AS task_status,
                (SELECT attempt_count FROM zippy.durable_tasks WHERE durable_task_id = %s) AS task_attempts,
                (SELECT status FROM zippy.event_outbox WHERE outbox_event_id = %s) AS outbox_status,
                (SELECT attempt_count FROM zippy.event_outbox WHERE outbox_event_id = %s) AS outbox_attempts,
                (SELECT count(*) FROM zippy.dead_letter_records WHERE source_id IN (%s, %s)) AS dead_letters,
                (SELECT count(*) FROM zippy.operational_exceptions WHERE entity_id IN (%s, %s)) AS exceptions
            """,
            (
                task_id,
                task_id,
                event_id,
                event_id,
                task_id,
                event_id,
                task_id,
                event_id,
            ),
        )[0]
        assert terminal == {
            "task_status": "dead_lettered",
            "task_attempts": 3,
            "outbox_status": "dead_lettered",
            "outbox_attempts": 3,
            "dead_letters": 2,
            "exceptions": 2,
        }

        reasons = _query(
            integration_settings,
            """
            SELECT
                (SELECT string_agg(terminal_reason, ',')
                   FROM zippy.dead_letter_records WHERE source_id IN (%s, %s)) AS letter_reasons,
                (SELECT string_agg(reason, ',')
                   FROM zippy.operational_exceptions WHERE entity_id IN (%s, %s)) AS exception_reasons
            """,
            (task_id, event_id, task_id, event_id),
        )[0]
        assert reasons["letter_reasons"] is not None
        assert reasons["exception_reasons"] is not None
        persisted_reasons = reasons["letter_reasons"] + "," + reasons["exception_reasons"]
        assert "synthetic failure details must not escape" not in persisted_reasons
        # Only exception class names are persisted: RuntimeError from the task
        # handler stub and TypeError from the deliberately mis-signed transport stub.
        assert set(persisted_reasons.split(",")) == {"RuntimeError", "TypeError"}
    finally:
        database.close()
