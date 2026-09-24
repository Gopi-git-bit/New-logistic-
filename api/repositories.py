"""Transactional repositories for M3 order and transition commands."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.errors import CheckViolation, SerializationFailure, UniqueViolation
from psycopg.types.json import Jsonb

from .models.core import (
    OrderAccepted,
    OrderCreate,
    TransitionRequest,
    TransitionResponse,
)
from .pricing import PriceQuote


class ConflictError(Exception):
    pass


class ForbiddenError(Exception):
    pass


@dataclass(frozen=True)
class RequestIdentity:
    platform_id: UUID
    account_id: UUID
    customer_profile_id: UUID | None
    roles: frozenset[str]


def canonical_fingerprint(order: OrderCreate) -> str:
    payload = order.model_dump(mode="json")
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class CoreRepository:
    def resolve_identity(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        external_subject: str,
    ) -> RequestIdentity:
        row = connection.execute(
            """
            SELECT account.account_id, account.status, customer.customer_profile_id,
                   coalesce(array_agg(membership.role_code) FILTER (WHERE membership.role_code IS NOT NULL), '{}') AS roles
              FROM zippy.accounts account
              LEFT JOIN zippy.customer_profiles customer
                ON customer.platform_id = account.platform_id AND customer.account_id = account.account_id
              LEFT JOIN zippy.account_role_memberships membership
                ON membership.platform_id = account.platform_id
               AND membership.account_id = account.account_id
               AND membership.valid_from <= clock_timestamp()
               AND (membership.valid_until IS NULL OR membership.valid_until > clock_timestamp())
             WHERE account.platform_id = %s AND account.external_subject = %s
             GROUP BY account.account_id, account.status, customer.customer_profile_id
            """,
            (platform_id, external_subject),
        ).fetchone()
        if row is None or row["status"] != "active":
            raise ForbiddenError("Actor is not authorized")
        roles = frozenset(row["roles"])
        if not roles:
            raise ForbiddenError("Actor is not authorized")
        connection.execute(
            "SELECT set_config('zippy.account_id', %s, true)", (str(row["account_id"]),)
        )
        return RequestIdentity(
            platform_id, row["account_id"], row["customer_profile_id"], roles
        )

    def create_order(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order: OrderCreate,
        quote: PriceQuote,
        idempotency_key: str,
        correlation_id: UUID,
        fingerprint: str,
        task_max_attempts: int,
    ) -> OrderAccepted:
        if "customer" not in identity.roles or identity.customer_profile_id is None:
            raise ForbiddenError("Actor is not authorized to create orders")
        scope = f"POST:/api/v1/orders:{identity.account_id}"
        inserted = connection.execute(
            """
            INSERT INTO zippy.idempotency_records (
                platform_id, operation_scope, idempotency_key, request_hash_sha256,
                status, correlation_id, expires_at
            ) VALUES (%s, %s, %s, %s, 'processing', %s, clock_timestamp() + interval '24 hours')
            ON CONFLICT (platform_id, operation_scope, idempotency_key) DO NOTHING
            RETURNING idempotency_record_id
            """,
            (identity.platform_id, scope, idempotency_key, fingerprint, correlation_id),
        ).fetchone()
        if inserted is None:
            existing = connection.execute(
                """
                SELECT request_hash_sha256, status, response_reference, correlation_id
                  FROM zippy.idempotency_records
                 WHERE platform_id = %s AND operation_scope = %s AND idempotency_key = %s
                 FOR UPDATE
                """,
                (identity.platform_id, scope, idempotency_key),
            ).fetchone()
            if existing is None:
                raise ConflictError("The original request is unavailable")
            if existing["request_hash_sha256"] != fingerprint:
                raise ConflictError(
                    "Idempotency key was already used with a different request"
                )
            if existing["status"] != "succeeded" or not existing["response_reference"]:
                raise ConflictError("The original request is still in progress")
            order_id = UUID(existing["response_reference"])
            replay = connection.execute(
                """
                SELECT task.durable_task_id, orders.created_at
                  FROM zippy.durable_tasks task
                  JOIN zippy.orders orders
                    ON orders.platform_id = task.platform_id AND orders.order_id = task.aggregate_id
                 WHERE task.platform_id = %s AND task.aggregate_id = %s
                   AND task.task_type = 'order_intake' AND task.idempotency_key = %s
                """,
                (identity.platform_id, order_id, idempotency_key),
            ).fetchone()
            if replay is None:
                raise ConflictError("The original request is unavailable")
            return OrderAccepted(
                order_id=order_id,
                workflow_id=replay["durable_task_id"],
                status="pending",
                correlation_id=existing["correlation_id"],
                accepted_at=replay["created_at"],
                idempotency_replay=True,
            )

        quote_row = connection.execute(
            """
            INSERT INTO zippy.quotes (
                platform_id, customer_profile_id, policy_version, input_hash_sha256,
                input_evidence, amount, currency_code, expires_at, created_by_account_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, clock_timestamp() + interval '1 hour', %s)
            ON CONFLICT (platform_id, customer_profile_id, policy_version, input_hash_sha256)
            DO NOTHING
            RETURNING quote_id
            """,
            (
                identity.platform_id,
                identity.customer_profile_id,
                quote.policy_version,
                quote.input_hash,
                Jsonb(quote.evidence),
                quote.amount,
                quote.currency,
                identity.account_id,
            ),
        ).fetchone()
        if quote_row is None:
            quote_row = connection.execute(
                """
                SELECT quote_id
                  FROM zippy.quotes
                 WHERE platform_id = %s AND customer_profile_id = %s
                   AND policy_version = %s AND input_hash_sha256 = %s
                """,
                (
                    identity.platform_id,
                    identity.customer_profile_id,
                    quote.policy_version,
                    quote.input_hash,
                ),
            ).fetchone()
        if quote_row is None:
            raise RuntimeError("quote persistence failed")
        order_id = uuid4()
        workflow_id = uuid4()
        accepted_row = connection.execute(
            """
            INSERT INTO zippy.orders (
                order_id, platform_id, booking_customer_profile_id, quote_id, status,
                cargo_description, cargo_weight_kg, special_handling_code,
                created_by_account_id, correlation_id
            ) VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s)
            RETURNING created_at
            """,
            (
                order_id,
                identity.platform_id,
                identity.customer_profile_id,
                quote_row["quote_id"],
                order.cargo_description,
                order.cargo_weight_kg,
                order.special_handling_code,
                identity.account_id,
                correlation_id,
            ),
        ).fetchone()
        if accepted_row is None:
            raise RuntimeError("order persistence failed")
        accepted_at = accepted_row["created_at"]
        # ORD-INV-003: capture the dispatch body-type requirement once, here,
        # through this authenticated server-side intake path only. It is
        # never accepted again later (e.g. at offer-acceptance time).
        connection.execute(
            """
            INSERT INTO zippy.dispatch_requirements (
                platform_id, order_id, required_body_type, created_by_account_id, correlation_id
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                identity.platform_id,
                order_id,
                order.service.body_type,
                identity.account_id,
                correlation_id,
            ),
        )
        for sequence, kind, stop in (
            (1, "pickup", order.pickup),
            (2, "delivery", order.delivery),
        ):
            connection.execute(
                """
                INSERT INTO zippy.order_stops (
                    platform_id, order_id, stop_sequence, stop_kind, address_text,
                    latitude, longitude, accuracy_meters, source, created_by_account_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'api', %s)
                """,
                (
                    identity.platform_id,
                    order_id,
                    sequence,
                    kind,
                    stop.address,
                    stop.latitude,
                    stop.longitude,
                    stop.accuracy_meters,
                    identity.account_id,
                ),
            )
        connection.execute(
            "INSERT INTO zippy.transaction_participants (platform_id, order_id, participant_role, customer_profile_id) VALUES (%s, %s, 'customer', %s)",
            (identity.platform_id, order_id, identity.customer_profile_id),
        )
        connection.execute(
            """
            INSERT INTO zippy.service_commitments (
                platform_id, order_id, commitment_type, committed_at, policy_version
            ) VALUES (%s, %s, 'pickup', %s, %s)
            """,
            (
                identity.platform_id,
                order_id,
                order.requested_pickup_at,
                quote.policy_version,
            ),
        )
        connection.execute(
            """
            INSERT INTO zippy.durable_tasks (
                durable_task_id, platform_id, task_type, aggregate_type, aggregate_id,
                payload_reference, idempotency_key, max_attempts, correlation_id
            ) VALUES (%s, %s, 'order_intake', 'order', %s, %s, %s, %s, %s)
            """,
            (
                workflow_id,
                identity.platform_id,
                order_id,
                f"order:{order_id}",
                idempotency_key,
                task_max_attempts,
                correlation_id,
            ),
        )
        event_payload = {
            "order_id": str(order_id),
            "workflow_id": str(workflow_id),
            "status": "pending",
        }
        connection.execute(
            """
            INSERT INTO zippy.operational_events (
                platform_id, aggregate_type, aggregate_id, aggregate_version, event_type,
                event_data, actor_account_id, correlation_id
            ) VALUES (%s, 'order', %s, 1, 'order.accepted', %s, %s, %s)
            """,
            (
                identity.platform_id,
                order_id,
                Jsonb(event_payload),
                identity.account_id,
                correlation_id,
            ),
        )
        connection.execute(
            """
            INSERT INTO zippy.event_outbox (
                platform_id, aggregate_type, aggregate_id, aggregate_version, event_type,
                destination, payload, idempotency_key, correlation_id
            ) VALUES (%s, 'order', %s, 1, 'order.accepted', 'internal', %s, %s, %s)
            """,
            (
                identity.platform_id,
                order_id,
                Jsonb(event_payload),
                f"order.accepted:{order_id}",
                correlation_id,
            ),
        )
        connection.execute(
            """
            UPDATE zippy.idempotency_records
               SET status = 'succeeded', response_code = 202, response_reference = %s,
                   completed_at = clock_timestamp()
             WHERE platform_id = %s AND operation_scope = %s AND idempotency_key = %s
            """,
            (str(order_id), identity.platform_id, scope, idempotency_key),
        )
        return OrderAccepted(
            order_id=order_id,
            workflow_id=workflow_id,
            status="pending",
            correlation_id=correlation_id,
            accepted_at=accepted_at,
            idempotency_replay=False,
        )

    def transition_order(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order_id: UUID,
        command: TransitionRequest,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> TransitionResponse:
        fingerprint = hashlib.sha256(
            command.model_dump_json().encode("utf-8")
        ).hexdigest()
        prior = connection.execute(
            """
            SELECT record.request_hash_sha256, record.correlation_id, orders.status, orders.version
              FROM zippy.idempotency_records record
              JOIN zippy.orders orders
                ON orders.platform_id = record.platform_id
               AND orders.order_id = record.response_reference::uuid
             WHERE record.platform_id = %s
               AND record.operation_scope = %s
               AND record.idempotency_key = %s
               AND record.status = 'succeeded'
            """,
            (identity.platform_id, f"order_transition:{order_id}", idempotency_key),
        ).fetchone()
        if prior is not None:
            if prior["request_hash_sha256"] != fingerprint:
                raise ConflictError(
                    "Idempotency key was already used with a different request"
                )
            return TransitionResponse(
                order_id=order_id,
                status=prior["status"],
                version=prior["version"],
                correlation_id=prior["correlation_id"],
            )
        current = connection.execute(
            """
            SELECT orders.status, orders.version
              FROM zippy.orders orders
              JOIN zippy.transaction_participants participant
                ON participant.platform_id = orders.platform_id AND participant.order_id = orders.order_id
              LEFT JOIN zippy.customer_profiles customer
                ON customer.platform_id = participant.platform_id AND customer.customer_profile_id = participant.customer_profile_id
             WHERE orders.platform_id = %s AND orders.order_id = %s
               AND (customer.account_id = %s OR 'admin' = ANY(%s))
             FOR UPDATE OF orders
            """,
            (identity.platform_id, order_id, identity.account_id, list(identity.roles)),
        ).fetchone()
        if current is None:
            raise ForbiddenError("Order is not available")
        if (
            current["status"] != command.expected_status
            or current["version"] != command.expected_version
        ):
            raise ConflictError("Order state changed before this request")
        try:
            transition_row = connection.execute(
                "SELECT zippy.transition_order(%s, %s, %s, %s, %s, %s, %s, %s, %s) AS status",
                (
                    identity.platform_id,
                    order_id,
                    command.expected_status,
                    command.next_status,
                    identity.account_id,
                    command.reason,
                    idempotency_key,
                    fingerprint,
                    correlation_id,
                ),
            ).fetchone()
            if transition_row is None:
                raise RuntimeError("transition returned no status")
            status = transition_row["status"]
        except (CheckViolation, SerializationFailure, UniqueViolation) as exc:
            raise ConflictError("Order transition was rejected") from exc
        return TransitionResponse(
            order_id=order_id,
            status=status,
            version=current["version"] + 1,
            correlation_id=correlation_id,
        )


def retry_at(attempt_count: int, base_seconds: int, max_seconds: int) -> datetime:
    delay = min(base_seconds * (2 ** max(attempt_count - 1, 0)), max_seconds)
    return datetime.now(UTC) + timedelta(seconds=delay)
