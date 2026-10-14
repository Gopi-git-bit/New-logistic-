"""Disposable-PostgreSQL M4 dispatch integration tests (D-27 part A/D).

Runs only inside the M4 proof harness (ZIPPY_M4_TEST_DATABASE_URL). Synthetic
identities and fixtures only; no external network calls. Offer creation
names one exact vendor/vehicle/driver candidate -- there is no automatic
search, scoring, ranking, or invented timeout/escalation policy.
"""

from __future__ import annotations

import hashlib
import os
import socket
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from api.config import Settings
from api.database import Database
from api.repositories import ConflictError, CoreRepository, ForbiddenError
from api.repositories_dispatch import DispatchRepository
from api.tests_m4.conftest import (
    ADMIN,
    CROSS_TENANT_ORDER,
    CUSTOMER,
    DRIVER_1,
    DRIVER_2,
    DRIVER_PROFILE_1,
    DRIVER_PROFILE_2,
    ORDER_A,
    ORDER_E,
    VEHICLE_1,
    VEHICLE_2,
    VEHICLE_MODEL,
    VENDOR,
    VENDOR_PROFILE,
)

DATABASE_URL = os.environ.get("ZIPPY_M4_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="requires the isolated M4 PostgreSQL proof"
)
PLATFORM_ID = "10000000-0000-0000-0000-000000000001"


def _merged(settings: Settings) -> Settings:
    return replace(settings, database_url=DATABASE_URL or "")


def _content_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _query(sql: str, parameters: tuple = ()) -> list[dict]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        connection.execute("SELECT set_config('zippy.platform_id', %s, false)", (PLATFORM_ID,))
        return connection.execute(sql, parameters).fetchall()


def _execute(sql: str, parameters: tuple = ()) -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute("SELECT set_config('zippy.platform_id', %s, false)", (PLATFORM_ID,))
        connection.execute(sql, parameters)


def _execute_as_account(sql: str, parameters: tuple, account_id: str) -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute("SELECT set_config('zippy.platform_id', %s, false)", (PLATFORM_ID,))
        connection.execute("SELECT set_config('zippy.account_id', %s, false)", (account_id,))
        connection.execute(sql, parameters)


def _future(minutes: int = 30) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def _create_offer(
    database_url: str,
    order_id,
    vehicle_id,
    driver_profile_id,
    idempotency_key: str,
    expires_at: datetime | None = None,
    vendor_profile_id=VENDOR_PROFILE,
):
    repository = DispatchRepository()
    database = Database(database_url)
    database.open()
    try:
        with database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, ADMIN)
            return repository.create_dispatch_offer(
                connection,
                identity,
                order_id,
                vendor_profile_id,
                vehicle_id,
                driver_profile_id,
                expires_at or _future(),
                idempotency_key,
                uuid4(),
            )
    finally:
        database.close()


def _accept_offer(database_url: str, dispatch_offer_id, subject: str):
    repository = DispatchRepository()
    database = Database(database_url)
    database.open()
    try:
        with database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, subject)
            repository.expire_if_due(connection, identity.platform_id, dispatch_offer_id)
        with database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, subject)
            return repository.accept_dispatch_offer(
                connection, identity, dispatch_offer_id, identity.account_id, uuid4()
            )
    finally:
        database.close()


def _create_eligible_vehicle() -> str:
    """A fresh, fully-eligible vehicle independent of the shared VEHICLE_1/2
    fixtures, for tests that permanently consume it via a real accept."""
    vehicle_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.vehicles (
            vehicle_id, platform_id, vendor_profile_id, vehicle_model_id,
            registration_number, status, approved_by_account_id, approved_at
        ) VALUES (%s, %s, %s, %s, %s, 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (vehicle_id, PLATFORM_ID, str(VENDOR_PROFILE), str(VEHICLE_MODEL), f"FRESH-VEH-{vehicle_id[:8]}"),
    )
    for doc_type in ("fitness", "insurance"):
        _execute(
            """
            INSERT INTO zippy.vehicle_documents (
                platform_id, vehicle_id, document_type, object_key, checksum_sha256,
                verification_status, verified_by_account_id, verified_at
            ) VALUES (%s, %s, %s, %s, %s, 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
            """,
            (PLATFORM_ID, vehicle_id, doc_type, f"synthetic/fresh/{doc_type}-{vehicle_id[:8]}", _content_hash(doc_type + vehicle_id)),
        )
    return vehicle_id


def _create_eligible_driver() -> str:
    """A fresh, fully-eligible driver independent of the shared
    DRIVER_PROFILE_1/2 fixtures, for tests that permanently consume it via a
    real accept."""
    driver_profile_id = str(uuid4())
    account_id = str(uuid4())
    _execute(
        "INSERT INTO zippy.accounts (account_id, platform_id, external_subject, email_normalized, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (account_id, PLATFORM_ID, f"fresh-driver-{driver_profile_id[:8]}", f"fresh-driver-{driver_profile_id[:8]}@example.invalid"),
    )
    _execute(
        "INSERT INTO zippy.driver_profiles (driver_profile_id, platform_id, account_id, licence_reference, eligibility_status) "
        "VALUES (%s, %s, %s, %s, 'approved')",
        (driver_profile_id, PLATFORM_ID, account_id, f"LIC-FRESH-{driver_profile_id[:8]}"),
    )
    _execute(
        "INSERT INTO zippy.driver_associations (platform_id, driver_profile_id, vendor_profile_id, valid_from) "
        "VALUES (%s, %s, %s, clock_timestamp() - interval '1 day')",
        (PLATFORM_ID, driver_profile_id, str(VENDOR_PROFILE)),
    )
    return driver_profile_id


# ------------------------------------------------------------------ offer creation


def test_eligible_offer_creation_and_accept_creates_atomic_assignment(settings: Settings):
    merged = _merged(settings)
    # Dedicated fresh order/vehicle/driver: accepting permanently consumes
    # them, so the shared ORDER_E/VEHICLE_1/DRIVER_PROFILE_1 baseline (reused
    # read-only by many other tests) must not be touched here.
    order_id = _create_confirmed_order()
    vehicle_id = _create_eligible_vehicle()
    driver_profile_id = _create_eligible_driver()
    outcome = _create_offer(
        merged.database_url, order_id, vehicle_id, driver_profile_id, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "created"
    assert outcome.status == "pending"

    assignment = _accept_offer(merged.database_url, outcome.dispatch_offer_id, ADMIN)
    assert assignment.duplicate is False
    assert assignment.order_status == "assigned"

    order = _query(
        "SELECT status FROM zippy.orders WHERE order_id = %s", (order_id,)
    )[0]
    assert order["status"] == "assigned"
    trip = _query(
        "SELECT status FROM zippy.trips WHERE trip_id = %s", (str(assignment.trip_id),)
    )[0]
    assert trip["status"] == "assigned"
    events = _query(
        "SELECT event_type FROM zippy.operational_events WHERE aggregate_id = %s ORDER BY aggregate_version",
        (str(assignment.trip_id),),
    )
    assert any(e["event_type"] == "dispatch.assignment_created" for e in events)
    outbox = _query(
        "SELECT count(*) AS n FROM zippy.event_outbox WHERE aggregate_id = %s AND event_type = 'dispatch.assignment_created'",
        (str(assignment.trip_id),),
    )[0]
    assert outbox["n"] == 1


def test_idempotent_offer_replay_returns_original_result(settings: Settings):
    merged = _merged(settings)
    key = f"offer:{uuid4()}"
    first = _create_offer(merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, key)
    second = _create_offer(merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, key)
    assert second.outcome == "duplicate"
    assert second.dispatch_offer_id == first.dispatch_offer_id
    assert second.duplicate is True

    receipts = _query(
        "SELECT count(*) AS n FROM zippy.dispatch_offers WHERE idempotency_key = %s", (key,)
    )[0]
    assert receipts["n"] == 1


def test_idempotency_key_reused_with_different_request_conflicts(settings: Settings):
    merged = _merged(settings)
    key = f"offer:{uuid4()}"
    _create_offer(merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, key)
    with pytest.raises(ConflictError):
        _create_offer(merged.database_url, ORDER_E, VEHICLE_2, DRIVER_PROFILE_2, key)


def test_insufficient_capacity_produces_manual_review(settings: Settings):
    merged = _merged(settings)
    _execute(
        """
        INSERT INTO zippy.vehicle_models (
            vehicle_model_id, platform_id, model_code, display_name, capacity_kg,
            body_type, source_version, approved_by_account_id, approved_at
        ) VALUES (%s, %s, 'SMALL-MODEL', 'Undersized model', 1.000, 'flatbed',
                  'test-m4-v1', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (str(uuid4()), PLATFORM_ID),
    )
    small_model = _query(
        "SELECT vehicle_model_id FROM zippy.vehicle_models WHERE model_code = 'SMALL-MODEL'"
    )[0]["vehicle_model_id"]
    small_vehicle_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.vehicles (
            vehicle_id, platform_id, vendor_profile_id, vehicle_model_id,
            registration_number, status, approved_by_account_id, approved_at
        ) VALUES (%s, %s, %s, %s, %s, 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (small_vehicle_id, PLATFORM_ID, str(VENDOR_PROFILE), str(small_model), f"SMALL-VEH-{small_vehicle_id[:8]}"),
    )
    for doc_type in ("fitness", "insurance"):
        _execute(
            """
            INSERT INTO zippy.vehicle_documents (
                platform_id, vehicle_id, document_type, object_key, checksum_sha256,
                verification_status, verified_by_account_id, verified_at
            ) VALUES (%s, %s, %s, %s, %s, 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
            """,
            (PLATFORM_ID, small_vehicle_id, doc_type, f"synthetic/small/{doc_type}-{small_vehicle_id[:8]}", _content_hash(doc_type)),
        )

    outcome = _create_offer(
        merged.database_url, ORDER_E, small_vehicle_id, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "VEHICLE_CAPACITY_INSUFFICIENT"
    exception = _query(
        "SELECT count(*) AS n FROM zippy.operational_exceptions WHERE exception_code = 'VEHICLE_CAPACITY_INSUFFICIENT'"
    )[0]
    assert exception["n"] >= 1


@pytest.mark.parametrize("document_type", ["fitness", "insurance"])
def test_expired_vehicle_document_produces_manual_review(settings: Settings, document_type: str):
    merged = _merged(settings)
    vehicle_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.vehicles (
            vehicle_id, platform_id, vendor_profile_id, vehicle_model_id,
            registration_number, status, approved_by_account_id, approved_at
        ) VALUES (%s, %s, %s, %s, %s, 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (vehicle_id, PLATFORM_ID, str(VENDOR_PROFILE), str(VEHICLE_MODEL), f"EXPIRED-VEH-{vehicle_id[:8]}"),
    )
    for doc_type in ("fitness", "insurance"):
        valid_until_clause = "clock_timestamp()::date - interval '1 day'" if doc_type == document_type else "NULL"
        _execute(
            f"""
            INSERT INTO zippy.vehicle_documents (
                platform_id, vehicle_id, document_type, object_key, checksum_sha256,
                verification_status, valid_until, verified_by_account_id, verified_at
            ) VALUES (%s, %s, %s, %s, %s, 'verified', {valid_until_clause}, 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
            """,
            (PLATFORM_ID, vehicle_id, doc_type, f"synthetic/expired/{doc_type}-{vehicle_id[:8]}", _content_hash(doc_type + vehicle_id)),
        )

    outcome = _create_offer(
        merged.database_url, ORDER_E, vehicle_id, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    expected_code = "VEHICLE_FITNESS_INVALID" if document_type == "fitness" else "VEHICLE_INSURANCE_INVALID"
    assert outcome.reason_code == expected_code


def test_unapproved_driver_produces_manual_review(settings: Settings):
    merged = _merged(settings)
    driver_profile_id = str(uuid4())
    driver_account_id = str(uuid4())
    _execute(
        "INSERT INTO zippy.accounts (account_id, platform_id, external_subject, email_normalized, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (driver_account_id, PLATFORM_ID, f"unapproved-driver-{driver_profile_id[:8]}", f"unapproved-{driver_profile_id[:8]}@example.invalid"),
    )
    _execute(
        "INSERT INTO zippy.driver_profiles (driver_profile_id, platform_id, account_id, licence_reference, eligibility_status) "
        "VALUES (%s, %s, %s, %s, 'suspended')",
        (driver_profile_id, PLATFORM_ID, driver_account_id, f"LIC-UNAPPROVED-{driver_profile_id[:8]}"),
    )
    _execute(
        "INSERT INTO zippy.driver_associations (platform_id, driver_profile_id, vendor_profile_id, valid_from) "
        "VALUES (%s, %s, %s, clock_timestamp() - interval '1 day')",
        (PLATFORM_ID, driver_profile_id, str(VENDOR_PROFILE)),
    )
    outcome = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, driver_profile_id, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "DRIVER_NOT_APPROVED"


def test_unavailable_vehicle_and_driver_produce_manual_review(settings: Settings):
    """A vehicle/driver already on an active (unreleased) trip assignment is unavailable."""
    merged = _merged(settings)
    busy_order = _create_confirmed_order()
    busy_vehicle = _create_eligible_vehicle()
    busy_driver = _create_eligible_driver()
    other_vehicle = _create_eligible_vehicle()
    other_driver = _create_eligible_driver()
    first = _create_offer(
        merged.database_url, busy_order, busy_vehicle, busy_driver, f"offer:{uuid4()}"
    )
    assert first.outcome == "created"
    _accept_offer(merged.database_url, first.dispatch_offer_id, ADMIN)

    # A different order competing for the now-busy vehicle/driver must fail closed.
    busy_outcome_vehicle = _create_offer(
        merged.database_url, _create_confirmed_order(), busy_vehicle, other_driver, f"offer:{uuid4()}"
    )
    assert busy_outcome_vehicle.outcome == "manual_review"
    assert busy_outcome_vehicle.reason_code == "VEHICLE_UNAVAILABLE"

    busy_outcome_driver = _create_offer(
        merged.database_url, _create_confirmed_order(), other_vehicle, busy_driver, f"offer:{uuid4()}"
    )
    assert busy_outcome_driver.outcome == "manual_review"
    assert busy_outcome_driver.reason_code == "DRIVER_UNAVAILABLE"


def _create_confirmed_order(required_body_type: str | None = "flatbed") -> str:
    """ORDER_A is 'pending' by default in other M4 fixtures; promote a
    dedicated confirmed order here so this test does not interfere with
    other tests that depend on ORDER_A's original status.

    Inserts a matching `zippy.dispatch_requirements` row (default
    'flatbed', matching VEHICLE_MODEL/VEHICLE_1/VEHICLE_2's body type) so
    existing eligibility scenarios are unaffected by the ORD-INV-003 gate;
    pass `required_body_type=None` to build a fixture with no captured
    requirement at all.
    """
    order_id = str(uuid4())
    quote_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.quotes (
            quote_id, platform_id, customer_profile_id, policy_version, input_hash_sha256,
            input_evidence, amount, currency_code, expires_at, created_by_account_id
        ) VALUES (%s, %s, 'c1000000-0000-0000-0000-000000000001', 'test-m4-v1', %s,
                  '{"synthetic": true}'::jsonb, 100.00, 'INR',
                  clock_timestamp() + interval '1 hour', 'c0000000-0000-0000-0000-000000000001')
        """,
        (quote_id, PLATFORM_ID, _content_hash(quote_id)),
    )
    _execute(
        """
        INSERT INTO zippy.orders (
            order_id, platform_id, booking_customer_profile_id, quote_id, status,
            cargo_description, cargo_weight_kg, created_by_account_id, correlation_id
        ) VALUES (%s, %s, 'c1000000-0000-0000-0000-000000000001', %s, 'confirmed',
                  'Synthetic availability-conflict fixture', 1.000,
                  'c0000000-0000-0000-0000-000000000001', %s)
        """,
        (order_id, PLATFORM_ID, quote_id, str(uuid4())),
    )
    _execute(
        "INSERT INTO zippy.transaction_participants (platform_id, order_id, participant_role, customer_profile_id) "
        "VALUES (%s, %s, 'customer', 'c1000000-0000-0000-0000-000000000001')",
        (PLATFORM_ID, order_id),
    )
    _execute(
        "INSERT INTO zippy.transaction_participants (platform_id, order_id, participant_role, vendor_profile_id) "
        "VALUES (%s, %s, 'vendor', %s)",
        (PLATFORM_ID, order_id, str(VENDOR_PROFILE)),
    )
    if required_body_type is not None:
        _execute(
            """
            INSERT INTO zippy.dispatch_requirements (
                platform_id, order_id, required_body_type, created_by_account_id, correlation_id
            ) VALUES (%s, %s, %s, 'c0000000-0000-0000-0000-000000000001', %s)
            """,
            (PLATFORM_ID, order_id, required_body_type, str(uuid4())),
        )
    return order_id


@pytest.mark.parametrize(
    "special_handling,expected_code",
    [("hazardous", "HAZARDOUS_CARGO_NO_WORKFLOW"), ("unclassified-mystery", "AMBIGUOUS_SPECIAL_HANDLING")],
)
def test_hazardous_and_ambiguous_cargo_fail_closed_to_manual_review(
    settings: Settings, special_handling: str, expected_code: str
):
    merged = _merged(settings)
    order_id = _create_confirmed_order()
    _execute(
        "UPDATE zippy.orders SET special_handling_code = %s WHERE platform_id = %s AND order_id = %s",
        (special_handling, PLATFORM_ID, order_id),
    )
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == expected_code


def test_order_not_dispatch_eligible_produces_manual_review(settings: Settings):
    merged = _merged(settings)
    # ORDER_A is 'pending' (not 'confirmed') in the shared M4 fixtures.
    outcome = _create_offer(
        merged.database_url, ORDER_A, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "ORDER_NOT_DISPATCH_ELIGIBLE"


def test_cross_tenant_order_reference_is_rejected(settings: Settings):
    merged = _merged(settings)
    with pytest.raises(ConflictError):
        _create_offer(
            merged.database_url, CROSS_TENANT_ORDER, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
        )


def test_only_admin_may_create_dispatch_offers(settings: Settings):
    merged = _merged(settings)
    repository = DispatchRepository()
    database = Database(merged.database_url)
    database.open()
    try:
        with pytest.raises(ForbiddenError), database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, CUSTOMER)
            repository.create_dispatch_offer(
                connection, identity, ORDER_E, VENDOR_PROFILE, VEHICLE_1, DRIVER_PROFILE_1,
                _future(), f"offer:{uuid4()}", uuid4(),
            )
    finally:
        database.close()


# ------------------------------------------------------------------ body-type compatibility (ORD-INV-003)


def _catalogue_closed_model() -> None:
    """Register a platform-1 vehicle_models row with body_type 'closed' so a
    'closed' requirement is a *known* vocabulary value; without it the gate
    correctly reports DISPATCH_BODY_TYPE_UNKNOWN instead of a mismatch."""
    model_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.vehicle_models (
            vehicle_model_id, platform_id, model_code, display_name, capacity_kg,
            body_type, source_version, approved_by_account_id, approved_at
        ) VALUES (%s, %s, %s, 'Catalogued closed model', 9.000, 'closed',
                  'test-m4-v1', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (model_id, PLATFORM_ID, f"CLOSED-MODEL-{model_id[:8]}"),
    )


def test_matching_body_type_permits_eligibility(settings: Settings):
    """Exact (normalized) match of the stored requirement permits eligibility."""
    merged = _merged(settings)
    order_id = _create_confirmed_order(required_body_type="flatbed")
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "created"
    assert outcome.reason_code is None


def test_mismatching_body_type_rejects_eligibility(settings: Settings):
    merged = _merged(settings)
    # 'closed' is catalogued here so the requirement is known; VEHICLE_1 is
    # 'flatbed', so this is an explicit known-vs-known mismatch.
    _catalogue_closed_model()
    order_id = _create_confirmed_order(required_body_type="closed")
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "VEHICLE_BODY_TYPE_MISMATCH"
    offers = _query(
        "SELECT count(*) AS n FROM zippy.dispatch_offers WHERE order_id = %s", (order_id,)
    )[0]
    assert offers["n"] == 0


def test_missing_requirement_produces_manual_fallback(settings: Settings):
    merged = _merged(settings)
    order_id = _create_confirmed_order(required_body_type=None)
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "DISPATCH_BODY_TYPE_REQUIREMENT_MISSING"
    offers = _query(
        "SELECT count(*) AS n FROM zippy.dispatch_offers WHERE order_id = %s", (order_id,)
    )[0]
    assert offers["n"] == 0


def test_unknown_requirement_produces_manual_fallback(settings: Settings):
    """A requirement not present in this platform's vehicle_models vocabulary is
    unknown/ambiguous and must fall back to manual handling, never fuzzy-match."""
    merged = _merged(settings)
    order_id = _create_confirmed_order(required_body_type="teleporter")
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "DISPATCH_BODY_TYPE_UNKNOWN"


def test_cross_tenant_requirement_is_invisible(settings: Settings):
    """A requirement row belonging to another platform can never satisfy this
    platform's order: the eligibility join is platform-scoped and RLS-forced, so
    even if platform 2 has requirements, platform 1's order with no requirement
    of its own falls back as missing. The pre-existing platform-2 fixtures
    (CROSS_TENANT_ORDER has no requirement row) plus RLS prove invisibility; an
    app-role INSERT of a platform-2 row is correctly rejected by the RLS WITH
    CHECK, which is itself asserted here."""
    merged = _merged(settings)
    # RLS denies a cross-tenant insert outright (the denied row can never exist).
    with pytest.raises(psycopg.Error):
        _execute(
            """
            INSERT INTO zippy.dispatch_requirements (
                platform_id, order_id, required_body_type, created_by_account_id, correlation_id
            ) VALUES ('10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000c99',
                      'flatbed', 'c0000000-0000-0000-0000-000000000099', %s)
            """,
            (str(uuid4()),),
        )
    # And a platform-1 order with no captured requirement of its own is never
    # satisfied by any other platform's data.
    order_id = _create_confirmed_order(required_body_type=None)
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "DISPATCH_BODY_TYPE_REQUIREMENT_MISSING"


def test_requirement_is_immutable_after_offer_and_assignment(settings: Settings):
    """The requirement row is immutable by construction: the application role
    has only SELECT/INSERT on dispatch_requirements, so no runtime code path --
    after offer creation or after assignment -- can change it."""
    merged = _merged(settings)
    # Fresh vehicle/driver: the accept below permanently consumes them, so the
    # shared VEHICLE_1/DRIVER_PROFILE_1 fixtures must not be used here.
    order_id = _create_confirmed_order(required_body_type="flatbed")
    vehicle_id = _create_eligible_vehicle()
    driver_profile_id = _create_eligible_driver()
    offer = _create_offer(
        merged.database_url, order_id, vehicle_id, driver_profile_id, f"offer:{uuid4()}"
    )
    assert offer.outcome == "created"
    update_sql = (
        "UPDATE zippy.dispatch_requirements SET required_body_type = 'closed-box' "
        f"WHERE platform_id = '{PLATFORM_ID}' AND order_id = '{order_id}'"
    )
    delete_sql = (
        f"DELETE FROM zippy.dispatch_requirements WHERE platform_id = '{PLATFORM_ID}' "
        f"AND order_id = '{order_id}'"
    )
    for forbidden in (update_sql, delete_sql):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            _execute(forbidden)
    assignment = _accept_offer(merged.database_url, offer.dispatch_offer_id, ADMIN)
    assert assignment.order_status == "assigned"
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _execute(update_sql)
    stored = _query(
        "SELECT required_body_type FROM zippy.dispatch_requirements "
        "WHERE platform_id = %s AND order_id = %s",
        (PLATFORM_ID, order_id),
    )[0]
    assert stored["required_body_type"] == "flatbed"


def test_acceptance_cannot_override_stored_requirement(settings: Settings):
    """Accepting an already-created offer only replays the stored decision; the
    acceptance request has no body and no way to alter the requirement, and a
    later offer against a different body type still evaluates against the
    original stored requirement, not any new input."""
    merged = _merged(settings)
    _catalogue_closed_model()
    order_id = _create_confirmed_order(required_body_type="closed")
    rejected = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert rejected.outcome == "manual_review"
    assert rejected.reason_code == "VEHICLE_BODY_TYPE_MISMATCH"
    # Re-evaluating the same order with a fresh idempotency key still reads the
    # unchanged stored requirement -- nothing from any request path can replace it.
    again = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert again.outcome == "manual_review"
    assert again.reason_code == "VEHICLE_BODY_TYPE_MISMATCH"
    stored = _query(
        "SELECT required_body_type FROM zippy.dispatch_requirements "
        "WHERE platform_id = %s AND order_id = %s",
        (PLATFORM_ID, order_id),
    )[0]
    assert stored["required_body_type"] == "closed"


def test_capacity_and_body_compatibility_both_required(settings: Settings):
    """A body-type match must not compensate for insufficient capacity."""
    merged = _merged(settings)
    order_id = _create_confirmed_order(required_body_type="flatbed")
    small_model_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.vehicle_models (
            vehicle_model_id, platform_id, model_code, display_name, capacity_kg,
            body_type, source_version, approved_by_account_id, approved_at
        ) VALUES (%s, %s, %s, 'Body-matching but undersized', 0.500, 'flatbed',
                  'test-m4-v1', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (small_model_id, PLATFORM_ID, f"SMALL-FLAT-{small_model_id[:8]}"),
    )
    small_vehicle_id = str(uuid4())
    _execute(
        """
        INSERT INTO zippy.vehicles (
            vehicle_id, platform_id, vendor_profile_id, vehicle_model_id,
            registration_number, status, approved_by_account_id, approved_at
        ) VALUES (%s, %s, %s, %s, %s, 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
        """,
        (small_vehicle_id, PLATFORM_ID, str(VENDOR_PROFILE), small_model_id, f"SF-{small_vehicle_id[:8]}"),
    )
    for doc_type in ("fitness", "insurance"):
        _execute(
            """
            INSERT INTO zippy.vehicle_documents (
                platform_id, vehicle_id, document_type, object_key, checksum_sha256,
                verification_status, verified_by_account_id, verified_at
            ) VALUES (%s, %s, %s, %s, %s, 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp())
            """,
            (PLATFORM_ID, small_vehicle_id, doc_type, f"synthetic/sf/{doc_type}-{small_vehicle_id[:8]}", _content_hash(doc_type + small_vehicle_id)),
        )
    outcome = _create_offer(
        merged.database_url, order_id, small_vehicle_id, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "VEHICLE_CAPACITY_INSUFFICIENT"


def test_failed_compatibility_creates_no_assignment_or_transition(settings: Settings):
    merged = _merged(settings)
    _catalogue_closed_model()
    order_id = _create_confirmed_order(required_body_type="closed")
    outcome = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert outcome.outcome == "manual_review"
    assert outcome.reason_code == "VEHICLE_BODY_TYPE_MISMATCH"
    order = _query("SELECT status FROM zippy.orders WHERE order_id = %s", (order_id,))[0]
    assert order["status"] == "confirmed"
    assignments = _query(
        """
        SELECT count(*) AS n FROM zippy.trip_assignments assignment
          JOIN zippy.trips trip ON trip.trip_id = assignment.trip_id
         WHERE trip.order_id = %s
        """,
        (order_id,),
    )[0]
    assert assignments["n"] == 0


# ------------------------------------------------------------------ offer lifecycle


def test_unauthorized_actor_cannot_accept_offer(settings: Settings):
    merged = _merged(settings)
    offer = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    with pytest.raises(ForbiddenError):
        # driver2 is not named on this offer (driver1 is).
        _accept_offer(merged.database_url, offer.dispatch_offer_id, DRIVER_2)


def test_expired_offer_cannot_be_accepted(settings: Settings):
    merged = _merged(settings)
    # expires_at must satisfy the schema's `expires_at > created_at` check at
    # creation time, so simulate expiry by waiting past a short real expiry
    # rather than moving expires_at into the past afterward.
    offer = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}",
        expires_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    time.sleep(1.5)
    with pytest.raises(ConflictError):
        _accept_offer(merged.database_url, offer.dispatch_offer_id, ADMIN)
    expired = _query(
        "SELECT status FROM zippy.dispatch_offers WHERE dispatch_offer_id = %s",
        (str(offer.dispatch_offer_id),),
    )[0]
    assert expired["status"] == "expired"


def test_declined_offer_cannot_be_accepted(settings: Settings):
    merged = _merged(settings)
    offer = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    repository = DispatchRepository()
    database = Database(merged.database_url)
    database.open()
    try:
        with database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, DRIVER_1)
            status = repository.decline_dispatch_offer(
                connection, identity, offer.dispatch_offer_id, "driver unavailable", uuid4()
            )
        assert status == "declined"
    finally:
        database.close()
    with pytest.raises(ConflictError):
        _accept_offer(merged.database_url, offer.dispatch_offer_id, ADMIN)


def test_cancelled_offer_cannot_be_accepted(settings: Settings):
    merged = _merged(settings)
    offer = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    repository = DispatchRepository()
    database = Database(merged.database_url)
    database.open()
    try:
        with database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, ADMIN)
            status = repository.cancel_dispatch_offer(
                connection, identity, offer.dispatch_offer_id, "order cancelled", uuid4()
            )
        assert status == "cancelled"
    finally:
        database.close()
    with pytest.raises(ConflictError):
        _accept_offer(merged.database_url, offer.dispatch_offer_id, ADMIN)


def test_only_admin_may_cancel_dispatch_offers(settings: Settings):
    merged = _merged(settings)
    offer = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    repository = DispatchRepository()
    database = Database(merged.database_url)
    database.open()
    try:
        with pytest.raises(ForbiddenError), database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, VENDOR)
            repository.cancel_dispatch_offer(
                connection, identity, offer.dispatch_offer_id, "attempted by non-admin", uuid4()
            )
    finally:
        database.close()


# ------------------------------------------------------------------ atomic assignment


def test_concurrent_competing_acceptance_yields_exactly_one_assignment(settings: Settings):
    merged = _merged(settings)
    # Dedicated fresh order/vehicles/drivers: whichever offer wins the race
    # permanently consumes them, so the shared baseline fixtures are not used.
    order_id = _create_confirmed_order()
    vehicle_a = _create_eligible_vehicle()
    vehicle_b = _create_eligible_vehicle()
    driver_a = _create_eligible_driver()
    driver_b = _create_eligible_driver()
    offer_a = _create_offer(
        merged.database_url, order_id, vehicle_a, driver_a, f"offer:{uuid4()}"
    )
    offer_b = _create_offer(
        merged.database_url, order_id, vehicle_b, driver_b, f"offer:{uuid4()}"
    )
    assert offer_a.outcome == "created"
    assert offer_b.outcome == "created"

    results: dict[str, tuple] = {}

    def _attempt(key: str, dispatch_offer_id) -> None:
        try:
            outcome = _accept_offer(merged.database_url, dispatch_offer_id, ADMIN)
            results[key] = ("ok", outcome)
        except (ConflictError, ForbiddenError) as exc:
            results[key] = ("error", exc)

    thread_a = threading.Thread(target=_attempt, args=("a", offer_a.dispatch_offer_id))
    thread_b = threading.Thread(target=_attempt, args=("b", offer_b.dispatch_offer_id))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=30)
    thread_b.join(timeout=30)

    outcomes = [results["a"], results["b"]]
    successes = [o for o in outcomes if o[0] == "ok"]
    failures = [o for o in outcomes if o[0] == "error"]
    assert len(successes) == 1
    assert len(failures) == 1

    active_assignments = _query(
        """
        SELECT count(*) AS n FROM zippy.trip_assignments trip_assignment
          JOIN zippy.trips trip
            ON trip.platform_id = trip_assignment.platform_id AND trip.trip_id = trip_assignment.trip_id
         WHERE trip.order_id = %s AND trip_assignment.released_at IS NULL
        """,
        (order_id,),
    )[0]
    assert active_assignments["n"] == 1
    accepted_offers = _query(
        "SELECT count(*) AS n FROM zippy.dispatch_offers WHERE order_id = %s AND status = 'accepted'",
        (order_id,),
    )[0]
    assert accepted_offers["n"] == 1


def test_rollback_on_injected_order_conflict_leaves_no_partial_assignment(settings: Settings):
    """Force `transition_order` to fail (order already moved away from
    'confirmed' by another process) after the offer/trip/assignment writes
    inside the same transaction, and prove the whole attempt rolls back."""
    merged = _merged(settings)
    order_id = _create_confirmed_order()
    offer = _create_offer(
        merged.database_url, order_id, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    assert offer.outcome == "created"

    # Simulate a concurrent process moving the order to 'cancelled' through
    # the same sanctioned RPC transition_order itself uses; the app role has
    # no direct UPDATE privilege on orders.status by design.
    _execute_as_account(
        """
        SELECT zippy.transition_order(%s, %s, 'confirmed', 'cancelled', %s, %s, %s, %s, %s)
        """,
        (
            PLATFORM_ID, order_id, "a0000000-0000-0000-0000-000000000001",
            "concurrent cancellation test fixture", f"cancel:{uuid4()}",
            _content_hash(f"cancel:{order_id}"), str(uuid4()),
        ),
        "a0000000-0000-0000-0000-000000000001",
    )

    with pytest.raises(psycopg.Error):
        _accept_offer(merged.database_url, offer.dispatch_offer_id, ADMIN)

    offer_after = _query(
        "SELECT status FROM zippy.dispatch_offers WHERE dispatch_offer_id = %s",
        (str(offer.dispatch_offer_id),),
    )[0]
    assert offer_after["status"] == "pending"
    assignment_count = _query(
        "SELECT count(*) AS n FROM zippy.trip_assignments WHERE dispatch_offer_id = %s",
        (str(offer.dispatch_offer_id),),
    )[0]
    assert assignment_count["n"] == 0
    order_scoped_events = _query(
        """
        SELECT count(*) AS n FROM zippy.operational_events event
          JOIN zippy.trips trip ON trip.trip_id = event.aggregate_id
         WHERE trip.order_id = %s AND event.event_type = 'dispatch.assignment_created'
        """,
        (order_id,),
    )[0]
    assert order_scoped_events["n"] == 0


# ------------------------------------------------------------------ no network / secret-free


def test_dispatch_flow_makes_no_raw_socket_connections(settings: Settings, monkeypatch):
    merged = _merged(settings)
    database = Database(merged.database_url)
    database.open()  # established before patching; psycopg uses libpq, not Python sockets
    try:
        original_connect = socket.socket.connect

        def _blocked(self, *args, **kwargs):
            raise AssertionError("unexpected Python-level socket connection during dispatch flow")

        monkeypatch.setattr(socket.socket, "connect", _blocked)
        repository = DispatchRepository()
        with database.transaction(PLATFORM_ID) as connection:
            identity = CoreRepository().resolve_identity(connection, PLATFORM_ID, ADMIN)
            outcome = repository.create_dispatch_offer(
                connection, identity, ORDER_E, VENDOR_PROFILE, VEHICLE_1, DRIVER_PROFILE_1,
                _future(), f"offer:{uuid4()}", uuid4(),
            )
        assert outcome.outcome in ("created", "duplicate")
        monkeypatch.setattr(socket.socket, "connect", original_connect)
    finally:
        database.close()


def test_dispatch_conflict_errors_contain_no_secrets(settings: Settings):
    """Dispatch ConflictError/ForbiddenError text must never leak the
    database connection string or webhook/JWT secrets from Settings."""
    merged = _merged(settings)
    messages: list[str] = []

    try:
        _create_offer(
            merged.database_url, CROSS_TENANT_ORDER, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
        )
    except ConflictError as exc:
        messages.append(str(exc))

    offer = _create_offer(
        merged.database_url, ORDER_E, VEHICLE_1, DRIVER_PROFILE_1, f"offer:{uuid4()}"
    )
    try:
        _accept_offer(merged.database_url, offer.dispatch_offer_id, DRIVER_2)
    except ForbiddenError as exc:
        messages.append(str(exc))

    assert messages, "expected at least one captured dispatch exception message"
    combined = " ".join(messages)
    assert merged.database_url not in combined
    assert settings.auth_jwt_secret not in combined
    assert settings.razorpay_webhook_secret not in combined
