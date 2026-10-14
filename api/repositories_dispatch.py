"""Transactional repository for the M4 deterministic dispatch boundary.

Offer creation validates one caller-named vendor/vehicle/driver candidate
against canonical eligibility data; there is no automatic candidate search,
scoring, ranking, or invented timeout/escalation policy (D-27). Assignment
uses only the existing `zippy.transition_order` RPC for order-state changes
and the pre-existing `dispatch_one_accepted_offer_idx` partial unique index
plus an explicit `orders` row lock to make concurrent acceptance safe.

ORD-INV-003 (body/special-handling compatibility): the required vehicle body
type is read from `zippy.dispatch_requirements`, a row written exactly once
by the authenticated order-intake path (`CoreRepository.create_order`) and
never updatable by the application (see 0006_operations_finance.up.sql). It
is compared with exact, normalized-only equality against the candidate
vehicle's `zippy.vehicle_models.body_type`; no fuzzy or AI matching is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from .repositories import ConflictError, ForbiddenError, RequestIdentity

# Canonical vehicle-document type strings already established by db/zippy/tests/verify.sql
# ('fitness'); 'insurance' follows the same freeform-text convention. No enum
# exists in the schema for these, so this is an explicit application-level
# convention, not a canonical constraint.
FITNESS_DOCUMENT_TYPE = "fitness"
INSURANCE_DOCUMENT_TYPE = "insurance"

# orders.special_handling_code is freeform text with no canonical enum. These
# are the only values this service treats as hazardous; no approved
# specialized hazardous-cargo workflow exists, so they always fail closed.
_HAZARDOUS_HANDLING_CODES = frozenset({"hazardous", "hazmat"})


def _normalize_body_type(value: str) -> str:
    """Same normalization convention as the special-handling check below:
    trim and lower-case only. Never fuzzy/substring matching."""
    return value.strip().lower()



@dataclass(frozen=True)
class DispatchOfferOutcome:
    outcome: Literal["created", "duplicate", "manual_review"]
    dispatch_offer_id: UUID | None
    status: str | None
    reason_code: str | None
    duplicate: bool


@dataclass(frozen=True)
class DispatchAssignmentOutcome:
    dispatch_offer_id: UUID
    trip_id: UUID
    trip_assignment_id: UUID
    order_status: str
    duplicate: bool


class DispatchRepository:
    # ------------------------------------------------------------ offer creation
    def create_dispatch_offer(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        order_id: UUID,
        vendor_profile_id: UUID,
        vehicle_id: UUID,
        driver_profile_id: UUID,
        expires_at: datetime,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> DispatchOfferOutcome:
        if "admin" not in identity.roles:
            raise ForbiddenError("Actor is not authorized to create dispatch offers")
        platform_id = identity.platform_id

        existing = connection.execute(
            """
            SELECT dispatch_offer_id, status, order_id, vendor_profile_id, vehicle_id,
                   driver_profile_id
              FROM zippy.dispatch_offers
             WHERE platform_id = %s AND idempotency_key = %s
            """,
            (platform_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            fingerprint = (
                existing["order_id"] == order_id
                and existing["vendor_profile_id"] == vendor_profile_id
                and existing["vehicle_id"] == vehicle_id
                and existing["driver_profile_id"] == driver_profile_id
            )
            if not fingerprint:
                raise ConflictError("Idempotency key was already used with a different request")
            return DispatchOfferOutcome(
                "duplicate", existing["dispatch_offer_id"], existing["status"], None, True
            )

        facts = connection.execute(
            """
            SELECT order_record.status AS order_status,
                   order_record.cargo_weight_kg,
                   order_record.special_handling_code,
                   vendor_participant.vendor_profile_id AS committed_vendor_profile_id,
                   vendor.vendor_profile_id IS NOT NULL AS vendor_found,
                   vendor.eligibility_status AS vendor_eligibility_status,
                   vehicle.vehicle_id IS NOT NULL AS vehicle_found,
                   vehicle.status AS vehicle_status,
                   vehicle.vendor_profile_id AS vehicle_vendor_profile_id,
                   vehicle_model.capacity_kg,
                   vehicle_model.body_type AS vehicle_body_type,
                   requirement.required_body_type,
                   driver.driver_profile_id IS NOT NULL AS driver_found,
                   driver.eligibility_status AS driver_eligibility_status,
                   EXISTS (
                       SELECT 1 FROM zippy.driver_associations assoc
                        WHERE assoc.platform_id = %s
                          AND assoc.driver_profile_id = %s
                          AND assoc.vendor_profile_id = %s
                          AND assoc.valid_from <= clock_timestamp()
                          AND (assoc.valid_until IS NULL OR assoc.valid_until > clock_timestamp())
                   ) AS driver_vendor_association_valid,
                   EXISTS (
                       SELECT 1 FROM zippy.vehicle_documents doc
                        WHERE doc.platform_id = %s AND doc.vehicle_id = %s
                          AND doc.document_type = %s AND doc.verification_status = 'verified'
                          AND (doc.valid_until IS NULL OR doc.valid_until >= clock_timestamp()::date)
                   ) AS fitness_valid,
                   EXISTS (
                       SELECT 1 FROM zippy.vehicle_documents doc
                        WHERE doc.platform_id = %s AND doc.vehicle_id = %s
                          AND doc.document_type = %s AND doc.verification_status = 'verified'
                          AND (doc.valid_until IS NULL OR doc.valid_until >= clock_timestamp()::date)
                   ) AS insurance_valid,
                   EXISTS (
                       SELECT 1 FROM zippy.trip_assignments assignment
                        WHERE assignment.platform_id = %s AND assignment.vehicle_id = %s
                          AND assignment.released_at IS NULL
                   ) AS vehicle_busy,
                   EXISTS (
                       SELECT 1 FROM zippy.trip_assignments assignment
                        WHERE assignment.platform_id = %s AND assignment.driver_profile_id = %s
                          AND assignment.released_at IS NULL
                   ) AS driver_busy,
                   EXISTS (
                       SELECT 1 FROM zippy.vehicle_models canon
                        WHERE canon.platform_id = %s
                          AND lower(btrim(canon.body_type)) = lower(btrim(requirement.required_body_type))
                   ) AS body_type_known
              FROM zippy.orders order_record
              LEFT JOIN zippy.transaction_participants vendor_participant
                ON vendor_participant.platform_id = order_record.platform_id
               AND vendor_participant.order_id = order_record.order_id
               AND vendor_participant.participant_role = 'vendor'
              LEFT JOIN zippy.vendor_profiles vendor
                ON vendor.platform_id = order_record.platform_id AND vendor.vendor_profile_id = %s
              LEFT JOIN zippy.vehicles vehicle
                ON vehicle.platform_id = order_record.platform_id AND vehicle.vehicle_id = %s
              LEFT JOIN zippy.vehicle_models vehicle_model
                ON vehicle_model.platform_id = vehicle.platform_id
               AND vehicle_model.vehicle_model_id = vehicle.vehicle_model_id
              LEFT JOIN zippy.driver_profiles driver
                ON driver.platform_id = order_record.platform_id AND driver.driver_profile_id = %s
              LEFT JOIN zippy.dispatch_requirements requirement
                ON requirement.platform_id = order_record.platform_id
               AND requirement.order_id = order_record.order_id
             WHERE order_record.platform_id = %s AND order_record.order_id = %s
            """,
            (
                platform_id, driver_profile_id, vendor_profile_id,
                platform_id, vehicle_id, FITNESS_DOCUMENT_TYPE,
                platform_id, vehicle_id, INSURANCE_DOCUMENT_TYPE,
                platform_id, vehicle_id,
                platform_id, driver_profile_id,
                platform_id,
                vendor_profile_id, vehicle_id, driver_profile_id,
                platform_id, order_id,
            ),
        ).fetchone()
        if facts is None:
            raise ConflictError("order not found")
        if not facts["vendor_found"]:
            raise ConflictError("vendor is not a member of this platform")
        if not facts["vehicle_found"]:
            raise ConflictError("vehicle is not a member of this platform")
        if not facts["driver_found"]:
            raise ConflictError("driver is not a member of this platform")
        if facts["committed_vendor_profile_id"] != vendor_profile_id:
            raise ConflictError("vendor is not the order's committed vendor participant")
        if facts["vehicle_vendor_profile_id"] != vendor_profile_id:
            raise ConflictError("vehicle does not belong to the named vendor")

        if facts["order_status"] != "confirmed":
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "ORDER_NOT_DISPATCH_ELIGIBLE",
                f"order status {facts['order_status']} is not dispatch-eligible",
            )

        special_handling = facts["special_handling_code"]
        if special_handling:
            normalized = special_handling.strip().lower()
            if normalized in _HAZARDOUS_HANDLING_CODES:
                return self._ineligible(
                    connection, platform_id, order_id, correlation_id,
                    "HAZARDOUS_CARGO_NO_WORKFLOW",
                    "hazardous cargo has no approved specialized dispatch workflow",
                )
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "AMBIGUOUS_SPECIAL_HANDLING",
                f"unrecognized special handling code requires manual review: {normalized}",
            )

        # ORD-INV-003: body/special-handling compatibility must be proven
        # against a trusted, order-intake-captured requirement -- never
        # against anything supplied for the first time at offer-acceptance.
        required_body_type = facts["required_body_type"]
        if required_body_type is None:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "DISPATCH_BODY_TYPE_REQUIREMENT_MISSING",
                "order has no captured dispatch body-type requirement",
            )
        if not facts["body_type_known"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "DISPATCH_BODY_TYPE_UNKNOWN",
                f"required body type is not a recognized vehicle body type for this platform: "
                f"{_normalize_body_type(required_body_type)}",
            )
        vehicle_body_type = facts["vehicle_body_type"]
        if (
            vehicle_body_type is None
            or _normalize_body_type(vehicle_body_type) != _normalize_body_type(required_body_type)
        ):
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VEHICLE_BODY_TYPE_MISMATCH",
                "candidate vehicle's model body type does not match the order's required body type",
            )

        if facts["vendor_eligibility_status"] != "approved":
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VENDOR_NOT_APPROVED", "vendor eligibility status is not approved",
            )
        if facts["vehicle_status"] != "approved":
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VEHICLE_NOT_APPROVED", "vehicle status is not approved",
            )
        if facts["driver_eligibility_status"] != "approved":
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "DRIVER_NOT_APPROVED", "driver eligibility status is not approved",
            )
        if not facts["driver_vendor_association_valid"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "DRIVER_VENDOR_ASSOCIATION_INVALID",
                "driver has no currently valid association with the vendor",
            )
        if facts["capacity_kg"] is None or facts["capacity_kg"] < facts["cargo_weight_kg"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VEHICLE_CAPACITY_INSUFFICIENT",
                "vehicle model capacity is below the order cargo weight",
            )
        if not facts["fitness_valid"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VEHICLE_FITNESS_INVALID",
                "vehicle has no currently verified, unexpired fitness document",
            )
        if not facts["insurance_valid"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VEHICLE_INSURANCE_INVALID",
                "vehicle has no currently verified, unexpired insurance document",
            )
        if facts["vehicle_busy"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "VEHICLE_UNAVAILABLE", "vehicle already has an active trip assignment",
            )
        if facts["driver_busy"]:
            return self._ineligible(
                connection, platform_id, order_id, correlation_id,
                "DRIVER_UNAVAILABLE", "driver already has an active trip assignment",
            )

        inserted = connection.execute(
            """
            INSERT INTO zippy.dispatch_offers (
                platform_id, order_id, vendor_profile_id, vehicle_id, driver_profile_id,
                status, scoring_input_version, idempotency_key, expires_at
            ) VALUES (%s, %s, %s, %s, %s, 'pending', 'manual-v1', %s, %s)
            ON CONFLICT (platform_id, idempotency_key) DO NOTHING
            RETURNING dispatch_offer_id, status
            """,
            (
                platform_id, order_id, vendor_profile_id, vehicle_id, driver_profile_id,
                idempotency_key, expires_at,
            ),
        ).fetchone()
        if inserted is None:
            raise RuntimeError("dispatch offer persistence failed")
        self._record_event(
            connection, platform_id, "dispatch_offer", inserted["dispatch_offer_id"],
            "dispatch.offer_created",
            {"order_id": str(order_id), "vendor_profile_id": str(vendor_profile_id)},
            correlation_id,
        )
        self._record_outbox(
            connection, platform_id, "dispatch_offer", inserted["dispatch_offer_id"],
            "dispatch.offer_created", idempotency_key,
            {"order_id": str(order_id), "dispatch_offer_id": str(inserted["dispatch_offer_id"])},
            correlation_id,
        )
        return DispatchOfferOutcome(
            "created", inserted["dispatch_offer_id"], inserted["status"], None, False
        )

    def _ineligible(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        order_id: UUID,
        correlation_id: UUID,
        reason_code: str,
        reason: str,
    ) -> DispatchOfferOutcome:
        self._raise_exception(
            connection, platform_id, reason_code, "medium", "order", order_id,
            reason, correlation_id,
        )
        return DispatchOfferOutcome("manual_review", None, None, reason_code, False)

    # ------------------------------------------------------------ offer lifecycle
    def accept_dispatch_offer(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        dispatch_offer_id: UUID,
        assigned_by_account_id: UUID,
        correlation_id: UUID,
    ) -> DispatchAssignmentOutcome:
        platform_id = identity.platform_id
        located = connection.execute(
            """
            SELECT order_id FROM zippy.dispatch_offers
             WHERE platform_id = %s AND dispatch_offer_id = %s
            """,
            (platform_id, dispatch_offer_id),
        ).fetchone()
        if located is None:
            raise ConflictError("dispatch offer not found")
        order_id = located["order_id"]

        # Serialize every concurrent accept/assign attempt for this order.
        connection.execute(
            "SELECT order_id FROM zippy.orders WHERE platform_id = %s AND order_id = %s FOR UPDATE",
            (platform_id, order_id),
        )
        offer = connection.execute(
            """
            SELECT status, expires_at, vendor_profile_id, vehicle_id, driver_profile_id
              FROM zippy.dispatch_offers
             WHERE platform_id = %s AND dispatch_offer_id = %s
             FOR UPDATE
            """,
            (platform_id, dispatch_offer_id),
        ).fetchone()
        if offer is None:
            raise ConflictError("dispatch offer not found")
        if not self._actor_authorized_for_offer(
            connection, identity, offer["vendor_profile_id"], offer["driver_profile_id"]
        ):
            raise ForbiddenError("Actor is not authorized to accept this dispatch offer")

        # Idempotent replay: this exact offer already won the accept race.
        if offer["status"] == "accepted":
            assignment_row = connection.execute(
                """
                SELECT trip_assignment_id, trip_id FROM zippy.trip_assignments
                 WHERE platform_id = %s AND dispatch_offer_id = %s
                """,
                (platform_id, dispatch_offer_id),
            ).fetchone()
            if assignment_row is None:
                raise ConflictError("dispatch offer accepted without an assignment record")
            order_row = connection.execute(
                "SELECT status FROM zippy.orders WHERE platform_id = %s AND order_id = %s",
                (platform_id, order_id),
            ).fetchone()
            if order_row is None:
                raise ConflictError("order not found")
            return DispatchAssignmentOutcome(
                dispatch_offer_id, assignment_row["trip_id"],
                assignment_row["trip_assignment_id"], order_row["status"], True,
            )

        # Read-only check: a mutation here would be rolled back by the
        # ConflictError raised in the same request transaction. Persisting
        # the 'expired' status is `expire_if_due`'s job, called separately
        # (by the route, before this method) in its own committed transaction.
        if offer["status"] == "pending" and offer["expires_at"] <= _now(connection):
            raise ConflictError("dispatch offer has expired")
        if offer["status"] != "pending":
            raise ConflictError(f"dispatch offer is not pending: {offer['status']}")

        existing_assignment = connection.execute(
            """
            SELECT trip_assignment.trip_assignment_id, trip_assignment.trip_id
              FROM zippy.trip_assignments trip_assignment
              JOIN zippy.trips trip
                ON trip.platform_id = trip_assignment.platform_id
               AND trip.trip_id = trip_assignment.trip_id
             WHERE trip_assignment.platform_id = %s AND trip.order_id = %s
               AND trip_assignment.released_at IS NULL
            """,
            (platform_id, order_id),
        ).fetchone()
        if existing_assignment is not None:
            raise ConflictError("order already has an active trip assignment")

        updated = connection.execute(
            """
            UPDATE zippy.dispatch_offers
               SET status = 'accepted', responded_at = clock_timestamp()
             WHERE platform_id = %s AND dispatch_offer_id = %s AND status = 'pending'
            RETURNING dispatch_offer_id
            """,
            (platform_id, dispatch_offer_id),
        ).fetchone()
        if updated is None:
            raise ConflictError("dispatch offer was decided concurrently")

        trip = connection.execute(
            """
            INSERT INTO zippy.trips (platform_id, order_id, status)
            VALUES (%s, %s, 'assigned')
            ON CONFLICT (platform_id, order_id) DO NOTHING
            RETURNING trip_id
            """,
            (platform_id, order_id),
        ).fetchone()
        if trip is None:
            existing_trip = connection.execute(
                "SELECT trip_id FROM zippy.trips WHERE platform_id = %s AND order_id = %s",
                (platform_id, order_id),
            ).fetchone()
            if existing_trip is None:
                raise RuntimeError("trip persistence failed")
            trip = existing_trip
            connection.execute(
                "UPDATE zippy.trips SET status = 'assigned', updated_at = clock_timestamp() "
                "WHERE platform_id = %s AND trip_id = %s AND status = 'planned'",
                (platform_id, trip["trip_id"]),
            )
        trip_id = trip["trip_id"]

        assignment = connection.execute(
            """
            INSERT INTO zippy.trip_assignments (
                platform_id, trip_id, dispatch_offer_id, vendor_profile_id, vehicle_id,
                driver_profile_id, assigned_by_account_id, correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING trip_assignment_id
            """,
            (
                platform_id, trip_id, dispatch_offer_id, offer["vendor_profile_id"],
                offer["vehicle_id"], offer["driver_profile_id"], assigned_by_account_id,
                correlation_id,
            ),
        ).fetchone()
        if assignment is None:
            raise RuntimeError("trip assignment persistence failed")

        idempotency_key = f"dispatch:assign:{dispatch_offer_id}"
        request_hash = _sha256_json(
            {"dispatch_offer_id": str(dispatch_offer_id), "order_id": str(order_id)}
        )
        order_status_row = connection.execute(
            """
            SELECT zippy.transition_order(%s, %s, 'confirmed', 'assigned', %s, %s, %s, %s, %s) AS status
            """,
            (
                platform_id, order_id, assigned_by_account_id,
                "dispatch offer accepted", idempotency_key, request_hash, correlation_id,
            ),
        ).fetchone()
        if order_status_row is None:
            raise RuntimeError("order transition returned no status")
        order_status = order_status_row["status"]

        self._record_event(
            connection, platform_id, "trip", trip_id, "dispatch.assignment_created",
            {
                "dispatch_offer_id": str(dispatch_offer_id),
                "vehicle_id": str(offer["vehicle_id"]),
                "driver_profile_id": str(offer["driver_profile_id"]),
            },
            correlation_id,
        )
        self._record_outbox(
            connection, platform_id, "trip", trip_id, "dispatch.assignment_created",
            # Distinct from transition_order's own idempotency key: both write
            # to event_outbox with destination='internal', and that table's
            # uniqueness is (platform_id, destination, idempotency_key) --
            # reusing the same key would silently collide with the RPC's own
            # 'order.status_changed' outbox row via ON CONFLICT DO NOTHING.
            f"{idempotency_key}:assignment-created",
            {"trip_id": str(trip_id), "trip_assignment_id": str(assignment["trip_assignment_id"])},
            correlation_id,
        )
        return DispatchAssignmentOutcome(
            dispatch_offer_id, trip_id, assignment["trip_assignment_id"], order_status, False
        )

    def expire_if_due(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        dispatch_offer_id: UUID,
    ) -> bool:
        """Lazily persist the 'expired' transition for a past-due pending offer.

        Called in its own transaction (never alongside a conflict-raising
        accept attempt, which would roll this mutation back too).
        """
        updated = connection.execute(
            """
            UPDATE zippy.dispatch_offers SET status = 'expired'
             WHERE platform_id = %s AND dispatch_offer_id = %s AND status = 'pending'
               AND expires_at <= clock_timestamp()
            RETURNING dispatch_offer_id
            """,
            (platform_id, dispatch_offer_id),
        ).fetchone()
        return updated is not None

    def decline_dispatch_offer(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        dispatch_offer_id: UUID,
        reason: str,
        correlation_id: UUID,
    ) -> str:
        return self._resolve_offer(
            connection, identity, dispatch_offer_id, "declined", reason, correlation_id
        )

    def cancel_dispatch_offer(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        dispatch_offer_id: UUID,
        reason: str,
        correlation_id: UUID,
    ) -> str:
        if "admin" not in identity.roles:
            raise ForbiddenError("Actor is not authorized to cancel dispatch offers")
        return self._resolve_offer(
            connection, identity, dispatch_offer_id, "cancelled", reason, correlation_id
        )

    def _resolve_offer(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        dispatch_offer_id: UUID,
        new_status: str,
        reason: str,
        correlation_id: UUID,
    ) -> str:
        platform_id = identity.platform_id
        offer = connection.execute(
            """
            SELECT status, vendor_profile_id, driver_profile_id FROM zippy.dispatch_offers
             WHERE platform_id = %s AND dispatch_offer_id = %s
             FOR UPDATE
            """,
            (platform_id, dispatch_offer_id),
        ).fetchone()
        if offer is None:
            raise ConflictError("dispatch offer not found")
        if new_status == "declined" and not self._actor_authorized_for_offer(
            connection, identity, offer["vendor_profile_id"], offer["driver_profile_id"]
        ):
            raise ForbiddenError("Actor is not authorized to decline this dispatch offer")
        if offer["status"] != "pending":
            raise ConflictError(f"dispatch offer is not pending: {offer['status']}")
        responded_column = (
            "responded_at = clock_timestamp()" if new_status == "declined" else "responded_at = responded_at"
        )
        connection.execute(
            f"""
            UPDATE zippy.dispatch_offers
               SET status = %s, {responded_column}
             WHERE platform_id = %s AND dispatch_offer_id = %s AND status = 'pending'
            """,
            (new_status, platform_id, dispatch_offer_id),
        )
        self._record_event(
            connection, platform_id, "dispatch_offer", dispatch_offer_id,
            f"dispatch.offer_{new_status}", {"reason": reason}, correlation_id,
        )
        return new_status

    # ------------------------------------------------------------ shared helpers
    def _actor_authorized_for_offer(
        self,
        connection: Connection[dict[str, Any]],
        identity: RequestIdentity,
        vendor_profile_id: UUID,
        driver_profile_id: UUID,
    ) -> bool:
        """Resolve authority only from server-side identity, never request metadata."""
        if "admin" in identity.roles:
            return True
        row = connection.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM zippy.vendor_profiles vendor
                     WHERE vendor.platform_id = %s AND vendor.vendor_profile_id = %s
                       AND vendor.account_id = %s
                ) AS is_direct_vendor,
                EXISTS (
                    SELECT 1
                      FROM zippy.vendor_profiles vendor
                      JOIN zippy.company_memberships membership
                        ON membership.platform_id = vendor.platform_id
                       AND membership.legal_entity_id = vendor.legal_entity_id
                     WHERE vendor.platform_id = %s AND vendor.vendor_profile_id = %s
                       AND membership.account_id = %s
                       AND membership.valid_from <= clock_timestamp()
                       AND (membership.valid_until IS NULL OR membership.valid_until > clock_timestamp())
                ) AS is_company_member,
                EXISTS (
                    SELECT 1 FROM zippy.driver_profiles driver
                     WHERE driver.platform_id = %s AND driver.driver_profile_id = %s
                       AND driver.account_id = %s
                ) AS is_driver
            """,
            (
                identity.platform_id, vendor_profile_id, identity.account_id,
                identity.platform_id, vendor_profile_id, identity.account_id,
                identity.platform_id, driver_profile_id, identity.account_id,
            ),
        ).fetchone()
        if row is None:
            return False
        return bool(row["is_direct_vendor"] or row["is_company_member"] or row["is_driver"])

    def _record_event(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        event_data: dict[str, Any],
        correlation_id: UUID,
        actor_account_id: UUID | None = None,
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
                platform_id, aggregate_type, aggregate_id,
                platform_id, aggregate_type, aggregate_id,
                event_type, Jsonb(event_data), actor_account_id, correlation_id,
            ),
        )

    def _record_outbox(
        self,
        connection: Connection[dict[str, Any]],
        platform_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        correlation_id: UUID,
    ) -> None:
        connection.execute(
            """
            INSERT INTO zippy.event_outbox (
                platform_id, aggregate_type, aggregate_id, aggregate_version,
                event_type, destination, payload, idempotency_key, correlation_id
            )
            SELECT %s, %s, %s,
                   coalesce((
                       SELECT max(aggregate_version) + 1 FROM zippy.event_outbox
                        WHERE platform_id = %s AND aggregate_type = %s AND aggregate_id = %s
                   ), 1),
                   %s, 'internal', %s, %s, %s
            ON CONFLICT (platform_id, destination, idempotency_key) DO NOTHING
            """,
            (
                platform_id, aggregate_type, aggregate_id,
                platform_id, aggregate_type, aggregate_id,
                event_type, Jsonb(payload), idempotency_key, correlation_id,
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


def _now(connection: Connection[dict[str, Any]]) -> datetime:
    row = connection.execute("SELECT clock_timestamp() AS now").fetchone()
    if row is None:
        raise RuntimeError("clock_timestamp query returned no row")
    return cast(datetime, row["now"])


def _sha256_json(payload: dict[str, Any]) -> str:
    import hashlib
    import json

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
