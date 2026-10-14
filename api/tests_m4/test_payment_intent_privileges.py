"""Payment-intent privilege regression tests (D-27 part C).

Runs only inside the M4 proof harness (ZIPPY_M4_TEST_DATABASE_URL), which
connects as the restricted application login (`zippy_m2_app_login`, granted
only `zippy_app` membership). Proves runtime authority is limited to the
minimum SELECT/INSERT needed and that UPDATE/DELETE on
`zippy.payment_intents` are rejected at the privilege layer, independent of
row content or RLS.
"""

from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("ZIPPY_M4_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="requires the isolated M4 PostgreSQL proof"
)
PLATFORM_ID = "10000000-0000-0000-0000-000000000001"


def _connect() -> psycopg.Connection:  # type: ignore[type-arg]
    connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    connection.execute("SELECT set_config('zippy.platform_id', %s, false)", (PLATFORM_ID,))
    return connection


def test_restricted_login_privilege_catalog_for_payment_intents():
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                has_table_privilege(current_user, 'zippy.payment_intents', 'SELECT') AS can_select,
                has_table_privilege(current_user, 'zippy.payment_intents', 'INSERT') AS can_insert,
                has_table_privilege(current_user, 'zippy.payment_intents', 'UPDATE') AS can_update,
                has_table_privilege(current_user, 'zippy.payment_intents', 'DELETE') AS can_delete,
                has_table_privilege(current_user, 'zippy.payment_intents', 'TRUNCATE') AS can_truncate
            """
        ).fetchone()
    assert row == {
        "can_select": True,
        "can_insert": True,
        "can_update": False,
        "can_delete": False,
        "can_truncate": False,
    }


def test_restricted_login_cannot_update_payment_intents():
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as excinfo, _connect() as connection:
        connection.execute(
            "UPDATE zippy.payment_intents SET expected_amount_minor_units = 1 "
            "WHERE payment_intent_id = %s",
            (str(uuid4()),),
        )
    assert excinfo.value.sqlstate == "42501"


def test_restricted_login_cannot_delete_payment_intents():
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as excinfo, _connect() as connection:
        connection.execute(
            "DELETE FROM zippy.payment_intents WHERE payment_intent_id = %s",
            (str(uuid4()),),
        )
    assert excinfo.value.sqlstate == "42501"


def test_migration_owner_role_is_not_the_runtime_login():
    """Migration/owner authority is separate from runtime authority: the
    table owner is the NOLOGIN migration role, never the connected runtime
    login used by this test suite."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT tableowner, session_user <> tableowner AS owner_is_not_session_user
              FROM pg_tables
             WHERE schemaname = 'zippy' AND tablename = 'payment_intents'
            """
        ).fetchone()
    assert row is not None
    assert row["tableowner"] == "zippy_migrator"
    assert row["owner_is_not_session_user"] is True
