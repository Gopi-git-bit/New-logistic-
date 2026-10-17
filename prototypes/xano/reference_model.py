"""Offline synthetic contract oracle. NOT Xano code, an API, or production storage."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class Rejected(Exception):
    """A contract operation was denied without committing partial effects."""


@dataclass(frozen=True)
class Principal:
    """Trusted fixture identity; a future adapter must derive this from verified auth."""

    tenant: str
    account: str
    role: str


SCHEMA = """
CREATE TABLE orders(id TEXT PRIMARY KEY, tenant TEXT, customer TEXT, state TEXT);
CREATE TABLE vehicles(id TEXT PRIMARY KEY, tenant TEXT, vendor TEXT, eligible INTEGER);
CREATE TABLE assignments(order_id TEXT PRIMARY KEY, vehicle_id TEXT UNIQUE, vendor TEXT);
CREATE TABLE commands(tenant TEXT, actor TEXT, action TEXT, key TEXT, fingerprint TEXT,
 result TEXT, PRIMARY KEY(tenant,actor,action,key));
CREATE TABLE audit(id INTEGER PRIMARY KEY, tenant TEXT, actor TEXT, action TEXT, subject TEXT);
CREATE TABLE outbox(id INTEGER PRIMARY KEY, subject TEXT UNIQUE, lease TEXT, until_at INTEGER,
 done INTEGER DEFAULT 0);
CREATE TABLE payments(payment_id TEXT PRIMARY KEY, tenant TEXT, order_id TEXT UNIQUE,
 amount INTEGER CHECK(amount>0));
CREATE TABLE events(event_id TEXT PRIMARY KEY, fingerprint TEXT);
CREATE TABLE refunds(id TEXT PRIMARY KEY, tenant TEXT, requester TEXT, order_id TEXT, approved_by TEXT);
CREATE TABLE agent_budget(id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER, reserved INTEGER);
CREATE TABLE grants(id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, endpoint TEXT, model TEXT,
 expires INTEGER, max_units INTEGER, used INTEGER DEFAULT 0);
CREATE TABLE reservations(id TEXT PRIMARY KEY, grant_id TEXT UNIQUE, units INTEGER);
"""


def require(ok: object, code: str) -> None:
    if not ok:
        raise Rejected(code)


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Prototype:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self, cap: int = 10) -> None:
        with self.connection() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO agent_budget VALUES(1,?,0)", (cap,))

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise Rejected("CONFLICT") from exc
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def seed_vehicle(self, vehicle: str, tenant: str, vendor: str, eligible: bool = True) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO vehicles VALUES(?,?,?,?)", (vehicle, tenant, vendor, eligible))

    def audit(self, db: sqlite3.Connection, p: Principal, action: str, subject: str) -> None:
        db.execute(
            "INSERT INTO audit(tenant,actor,action,subject) VALUES(?,?,?,?)",
            (p.tenant, p.account, action, subject),
        )

    def replay(
        self, db: sqlite3.Connection, p: Principal, action: str, key: str, payload: object
    ) -> str | None:
        require(bool(key), "IDEMPOTENCY_REQUIRED")
        row = db.execute(
            "SELECT * FROM commands WHERE tenant=? AND actor=? AND action=? AND key=?",
            (p.tenant, p.account, action, key),
        ).fetchone()
        if row:
            require(row["fingerprint"] == fingerprint(payload), "IDEMPOTENCY_CONFLICT")
            return str(row["result"])
        return None

    def remember(
        self,
        db: sqlite3.Connection,
        p: Principal,
        action: str,
        key: str,
        payload: object,
        result: str,
    ) -> str:
        db.execute(
            "INSERT INTO commands VALUES(?,?,?,?,?,?)",
            (p.tenant, p.account, action, key, fingerprint(payload), result),
        )
        return result

    def create_order(self, p: Principal, order: str, key: str) -> str:
        require(p.role == "customer", "FORBIDDEN")
        with self.connection() as db:
            previous = self.replay(db, p, "create", key, order)
            if previous:
                return previous
            db.execute("INSERT INTO orders VALUES(?,?,?,'created')", (order, p.tenant, p.account))
            self.audit(db, p, "created", order)
            return self.remember(db, p, "create", key, order, order)

    def read_order(self, p: Principal, order: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM orders WHERE id=? AND tenant=?", (order, p.tenant)
            ).fetchone()
            require(row is not None, "NOT_FOUND")
            assert row is not None
            assigned = db.execute(
                "SELECT vendor FROM assignments WHERE order_id=?", (order,)
            ).fetchone()
            require(
                (p.role == "customer" and row["customer"] == p.account)
                or (p.role == "vendor" and assigned and assigned["vendor"] == p.account),
                "NOT_FOUND",
            )
            # No customer account or unrelated vendor profile in the response.
            return {"id": row["id"], "state": row["state"]}

    def assign(
        self, p: Principal, order: str, vehicle: str, key: str, fail_before_commit: bool = False
    ) -> str:
        require(p.role == "dispatcher", "FORBIDDEN")
        payload = [order, vehicle]
        with self.connection() as db:
            previous = self.replay(db, p, "assign", key, payload)
            if previous:
                return previous
            o = db.execute(
                "SELECT * FROM orders WHERE id=? AND tenant=?", (order, p.tenant)
            ).fetchone()
            v = db.execute(
                "SELECT * FROM vehicles WHERE id=? AND tenant=?", (vehicle, p.tenant)
            ).fetchone()
            require(o and v and o["state"] == "created" and v["eligible"] == 1, "INELIGIBLE")
            db.execute("INSERT INTO assignments VALUES(?,?,?)", (order, vehicle, v["vendor"]))
            # Prototype equivalent only; existing orders/RPCs are never modified.
            db.execute("UPDATE orders SET state='assigned' WHERE id=?", (order,))
            self.audit(db, p, "assigned", order)
            db.execute("INSERT INTO outbox(subject) VALUES(?)", (order,))
            require(not fail_before_commit, "INJECTED_INTERRUPTION")
            return self.remember(db, p, "assign", key, payload, order)

    def claim(self, token: str, now: int, ttl: int = 5) -> int | None:
        require(bool(token) and 0 < ttl <= 5, "LEASE_REJECTED")
        with self.connection() as db:
            row = db.execute(
                "SELECT id FROM outbox WHERE done=0 AND (lease IS NULL OR until_at<=?) ORDER BY id LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE outbox SET lease=?,until_at=? WHERE id=?", (token, now + ttl, row["id"])
            )
            return int(row["id"])

    def acknowledge(self, job: int, token: str, now: int) -> None:
        with self.connection() as db:
            count = db.execute(
                "UPDATE outbox SET done=1 WHERE id=? AND lease=? AND until_at>? AND done=0",
                (job, token, now),
            ).rowcount
            require(count == 1, "STALE_LEASE")

    def payment(self, raw: bytes, signature: str, secret: bytes) -> None:
        require(
            hmac.compare_digest(hmac.new(secret, raw, hashlib.sha256).hexdigest(), signature),
            "BAD_SIGNATURE",
        )
        data = json.loads(raw)
        require(set(data) == {"event", "payment", "tenant", "order", "amount"}, "BAD_EVENT")
        require(type(data["amount"]) is int and data["amount"] > 0, "BAD_AMOUNT")
        with self.connection() as db:
            event = db.execute(
                "SELECT fingerprint FROM events WHERE event_id=?", (data["event"],)
            ).fetchone()
            if event:
                require(event["fingerprint"] == fingerprint(data), "EVENT_CONFLICT")
                return
            order = db.execute(
                "SELECT id FROM orders WHERE id=? AND tenant=?", (data["order"], data["tenant"])
            ).fetchone()
            require(order, "UNKNOWN_ORDER")
            old = db.execute(
                "SELECT * FROM payments WHERE payment_id=?", (data["payment"],)
            ).fetchone()
            if old:
                require(
                    (old["tenant"], old["order_id"], old["amount"])
                    == (data["tenant"], data["order"], data["amount"]),
                    "PAYMENT_CONFLICT",
                )
            else:
                db.execute(
                    "INSERT INTO payments VALUES(?,?,?,?)",
                    (data["payment"], data["tenant"], data["order"], data["amount"]),
                )
                self.audit(
                    db,
                    Principal(data["tenant"], "synthetic-webhook", "webhook"),
                    "payment_recorded",
                    data["order"],
                )
            db.execute("INSERT INTO events VALUES(?,?)", (data["event"], fingerprint(data)))

    def request_refund(self, p: Principal, refund: str, order: str) -> None:
        require(p.role == "customer", "FORBIDDEN")
        with self.connection() as db:
            o = db.execute(
                "SELECT id FROM orders WHERE id=? AND tenant=? AND customer=?",
                (order, p.tenant, p.account),
            ).fetchone()
            require(o, "NOT_FOUND")
            old = db.execute("SELECT * FROM refunds WHERE id=?", (refund,)).fetchone()
            if old:
                require(
                    old["tenant"] == p.tenant
                    and old["requester"] == p.account
                    and old["order_id"] == order,
                    "CONFLICT",
                )
                return
            db.execute(
                "INSERT INTO refunds VALUES(?,?,?,?,NULL)", (refund, p.tenant, p.account, order)
            )
            self.audit(db, p, "refund_requested", refund)

    def approve_refund(self, p: Principal, refund: str) -> None:
        require(p.role == "human_admin", "MANUAL_APPROVAL_REQUIRED")
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM refunds WHERE id=? AND tenant=?", (refund, p.tenant)
            ).fetchone()
            require(row and row["requester"] != p.account, "SELF_APPROVAL_DENIED")
            if row["approved_by"] is not None:
                require(row["approved_by"] == p.account, "CONFLICT")
                return
            db.execute("UPDATE refunds SET approved_by=? WHERE id=?", (p.account, refund))
            self.audit(db, p, "refund_approved", refund)
        # No provider call or payout adapter exists in this prototype.

    def reserve_agent(
        self,
        p: Principal,
        grant: str,
        reservation: str,
        endpoint: str,
        model: str,
        units: int,
        now: int,
    ) -> None:
        require(p.role == "agent" and type(units) is int and units > 0, "FORBIDDEN")
        with self.connection() as db:
            g = db.execute("SELECT * FROM grants WHERE id=?", (grant,)).fetchone()
            require(
                g
                and (g["tenant"], g["agent"], g["endpoint"], g["model"])
                == (p.tenant, p.account, endpoint, model)
                and now < g["expires"]
                and units <= g["max_units"],
                "GRANT_REJECTED",
            )
            old = db.execute("SELECT * FROM reservations WHERE id=?", (reservation,)).fetchone()
            if old:
                require(old["grant_id"] == grant and old["units"] == units, "CONFLICT")
                return
            require(g["used"] == 0, "GRANT_CONSUMED")
            changed = db.execute(
                "UPDATE agent_budget SET reserved=reserved+? WHERE id=1 AND reserved+?<=cap",
                (units, units),
            ).rowcount
            require(changed == 1, "BUDGET_EXCEEDED")
            db.execute("INSERT INTO reservations VALUES(?,?,?)", (reservation, grant, units))
            db.execute("UPDATE grants SET used=1 WHERE id=?", (grant,))
            self.audit(db, p, "agent_reserved", reservation)
        # Reservation is not authorization to execute an external call.
