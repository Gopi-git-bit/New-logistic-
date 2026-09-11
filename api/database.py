"""PostgreSQL connection pool with transaction-local request context."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, database_url: str) -> None:
        self._pool = cast(
            ConnectionPool[Connection[dict[str, Any]]],
            ConnectionPool(
                database_url,
                min_size=1,
                max_size=8,
                open=False,
                kwargs={"row_factory": dict_row},
            ),
        )

    def open(self) -> None:
        self._pool.open(wait=True)

    def close(self) -> None:
        self._pool.close()

    def ready(self) -> bool:
        try:
            with self._pool.connection(timeout=2) as connection:
                connection.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 - readiness fails closed for any pool fault
            return False

    @contextmanager
    def transaction(
        self, platform_id: UUID, account_id: UUID | None = None
    ) -> Iterator[Connection[dict[str, Any]]]:
        with self._pool.connection() as connection, connection.transaction():
            connection.execute(
                "SELECT set_config('zippy.platform_id', %s, true)", (str(platform_id),)
            )
            connection.execute(
                "SELECT set_config('zippy.account_id', %s, true)",
                (str(account_id) if account_id else "",),
            )
            yield connection
