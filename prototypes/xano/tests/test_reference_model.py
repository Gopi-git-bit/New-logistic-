"""Local transactional contract tests; NOT evidence of Xano behavior."""

import hashlib
import hmac
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prototypes.xano.reference_model import Principal, Prototype, Rejected

CUSTOMER = Principal("tenant-a", "customer-a", "customer")
DISPATCHER = Principal("tenant-a", "dispatch-a", "dispatcher")
VENDOR = Principal("tenant-a", "vendor-a", "vendor")
ADMIN = Principal("tenant-a", "owner", "human_admin")
AGENT = Principal("tenant-a", "oms", "agent")


class ReferenceContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "synthetic.sqlite"
        self.p = Prototype(self.path)
        self.p.initialize()
        self.p.create_order(CUSTOMER, "order-a", "create-a")
        self.p.create_order(CUSTOMER, "order-b", "create-b")
        self.p.seed_vehicle("vehicle-a", "tenant-a", "vendor-a")
        self.p.seed_vehicle("vehicle-b", "tenant-a", "vendor-b")

    def count(self, table):
        with self.p.connection() as db:
            return db.execute("SELECT count(*) FROM " + table).fetchone()[0]

    def race(self, functions):
        barrier = threading.Barrier(len(functions))

        def invoke(function):
            barrier.wait(timeout=3)
            try:
                return function()
            except Rejected:
                return "REJECTED"

        with ThreadPoolExecutor(max_workers=len(functions)) as pool:
            return list(pool.map(invoke, functions))

    def grant(self, name="g1"):
        with self.p.connection() as db:
            db.execute(
                "INSERT INTO grants VALUES(?,?,?,?,?,?,?,0)",
                (
                    name,
                    "tenant-a",
                    "oms",
                    "https://synthetic.invalid/inference",
                    "synthetic-model",
                    100,
                    10,
                ),
            )

    def reserve(
        self,
        grant="g1",
        reservation="r1",
        units=6,
        now=1,
        endpoint="https://synthetic.invalid/inference",
        model="synthetic-model",
    ):
        self.p.reserve_agent(AGENT, grant, reservation, endpoint, model, units, now)

    def event(self, **changes):
        data = {
            "event": "event-a",
            "payment": "payment-a",
            "tenant": "tenant-a",
            "order": "order-a",
            "amount": 100,
        }
        data.update(changes)
        raw = json.dumps(data).encode()
        secret = b"public-synthetic-test-only"
        return raw, hmac.new(secret, raw, hashlib.sha256).hexdigest(), secret

    def test_order_assignment_and_audit(self):
        self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a")
        self.assertEqual(self.p.read_order(CUSTOMER, "order-a")["state"], "assigned")
        self.assertEqual(
            self.p.read_order(VENDOR, "order-a"), {"id": "order-a", "state": "assigned"}
        )
        self.assertEqual(self.count("assignments"), 1)
        self.assertEqual(self.count("outbox"), 1)
        self.assertEqual(self.count("audit"), 3)

    def test_two_orders_one_vehicle(self):
        result = self.race(
            [
                lambda: self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a"),
                lambda: self.p.assign(DISPATCHER, "order-b", "vehicle-a", "b"),
            ]
        )
        self.assertEqual(result.count("REJECTED"), 1)
        self.assertEqual(self.count("assignments"), 1)
        self.assertEqual(self.count("audit"), 3)

    def test_two_vehicles_one_order(self):
        result = self.race(
            [
                lambda: self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a"),
                lambda: self.p.assign(DISPATCHER, "order-a", "vehicle-b", "b"),
            ]
        )
        self.assertEqual(result.count("REJECTED"), 1)
        self.assertEqual(self.count("assignments"), 1)

    def test_duplicate_assignment_race(self):
        result = self.race([lambda: self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a")] * 2)
        self.assertEqual(result, ["order-a", "order-a"])
        self.assertEqual(self.count("outbox"), 1)
        self.assertEqual(self.count("audit"), 3)

    def test_idempotency_payload_binding(self):
        self.assertEqual(self.p.create_order(CUSTOMER, "order-a", "create-a"), "order-a")
        with self.assertRaisesRegex(Rejected, "IDEMPOTENCY_CONFLICT"):
            self.p.create_order(CUSTOMER, "changed", "create-a")
        self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a")
        with self.assertRaisesRegex(Rejected, "IDEMPOTENCY_CONFLICT"):
            self.p.assign(DISPATCHER, "order-b", "vehicle-b", "a")

    def test_tenant_customer_vendor_read_boundaries(self):
        for principal in (
            Principal("tenant-b", "customer-a", "customer"),
            Principal("tenant-a", "other", "customer"),
            VENDOR,
            AGENT,
        ):
            with self.subTest(principal=principal), self.assertRaises(Rejected):
                self.p.read_order(principal, "order-a")
        self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a")
        with self.assertRaises(Rejected):
            self.p.read_order(Principal("tenant-a", "vendor-b", "vendor"), "order-a")

    def test_assignment_permission_and_eligibility(self):
        self.p.seed_vehicle("bad", "tenant-a", "vendor-a", False)
        self.p.seed_vehicle("foreign", "tenant-b", "vendor-b")
        for vehicle in ("bad", "foreign", "missing"):
            with self.subTest(vehicle=vehicle), self.assertRaises(Rejected):
                self.p.assign(DISPATCHER, "order-a", vehicle, "a")
        for principal in (CUSTOMER, AGENT, Principal("tenant-b", "dispatch-a", "dispatcher")):
            with self.subTest(principal=principal), self.assertRaises(Rejected):
                self.p.assign(principal, "order-a", "vehicle-a", "a")
        self.assertEqual(self.count("assignments"), 0)

    def test_interrupted_transaction_rolls_back_then_retries(self):
        with self.assertRaisesRegex(Rejected, "INJECTED_INTERRUPTION"):
            self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a", True)
        self.assertEqual(self.count("assignments"), 0)
        self.assertEqual(self.count("outbox"), 0)
        self.assertEqual(self.count("audit"), 2)
        self.assertEqual(self.p.read_order(CUSTOMER, "order-a")["state"], "created")
        Prototype(self.path).assign(DISPATCHER, "order-a", "vehicle-a", "a")
        self.assertEqual(self.count("assignments"), 1)

    def test_restart_and_expired_worker_lease(self):
        self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a")
        job = self.p.claim("worker-a", 10)
        self.assertIsNone(Prototype(self.path).claim("worker-b", 11))
        self.assertEqual(Prototype(self.path).claim("worker-b", 15), job)
        with self.assertRaisesRegex(Rejected, "STALE_LEASE"):
            self.p.acknowledge(job, "worker-a", 16)
        self.p.acknowledge(job, "worker-b", 16)
        self.assertIsNone(self.p.claim("worker-c", 20))

    def test_concurrent_worker_claim(self):
        self.p.assign(DISPATCHER, "order-a", "vehicle-a", "a")
        result = self.race([lambda: self.p.claim("a", 1), lambda: self.p.claim("b", 1)])
        self.assertEqual(result.count(None), 1)

    def test_duplicate_payment_effect_once(self):
        self.p.payment(*self.event())
        self.p.payment(*self.event())
        self.p.payment(*self.event(event="event-b"))
        self.assertEqual(self.count("payments"), 1)
        self.assertEqual(self.count("events"), 2)
        self.assertEqual(self.count("audit"), 3)

    def test_concurrent_payment_delivery(self):
        self.assertEqual(self.race([lambda: self.p.payment(*self.event())] * 2), [None, None])
        self.assertEqual(self.count("payments"), 1)

    def test_signature_validation_before_mutation(self):
        raw, _, secret = self.event()
        with self.assertRaisesRegex(Rejected, "BAD_SIGNATURE"):
            self.p.payment(raw, "0" * 64, secret)
        self.assertEqual(self.count("payments"), 0)

    def test_conflicting_event_payment_order_rejected(self):
        self.p.payment(*self.event())
        for changes in (
            {"amount": 101},
            {"event": "event-b", "amount": 101},
            {"event": "event-c", "order": "order-b"},
            {"event": "event-d", "payment": "payment-b"},
        ):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                self.p.payment(*self.event(**changes))
        self.assertEqual(self.count("payments"), 1)
        self.assertEqual(self.count("events"), 1)

    def test_invalid_amount_or_foreign_tenant(self):
        for changes in ({"amount": True}, {"amount": 0}, {"tenant": "tenant-b"}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                self.p.payment(*self.event(**changes))
        self.assertEqual(self.count("payments"), 0)

    def test_manual_distinct_human_refund_approval(self):
        self.p.request_refund(CUSTOMER, "refund-a", "order-a")
        for principal in (
            AGENT,
            CUSTOMER,
            Principal("tenant-b", "owner", "human_admin"),
            Principal("tenant-a", "customer-a", "human_admin"),
        ):
            with self.subTest(principal=principal), self.assertRaises(Rejected):
                self.p.approve_refund(principal, "refund-a")
        self.p.approve_refund(ADMIN, "refund-a")
        self.p.approve_refund(ADMIN, "refund-a")
        self.assertEqual(self.count("audit"), 4)
        self.assertEqual(self.count("payments"), 0)

    def test_refund_request_order_owner_binding(self):
        self.p.request_refund(CUSTOMER, "refund-a", "order-a")
        self.p.request_refund(CUSTOMER, "refund-a", "order-a")
        with self.assertRaises(Rejected):
            self.p.request_refund(CUSTOMER, "refund-a", "order-b")
        with self.assertRaises(Rejected):
            self.p.request_refund(Principal("tenant-a", "other", "customer"), "refund-b", "order-a")

    def test_grant_endpoint_model_expiry_identity(self):
        self.grant()
        for changes in ({"endpoint": "https://other.invalid"}, {"model": "other"}, {"now": 100}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                self.reserve(**changes)
        with self.assertRaises(Rejected):
            self.p.reserve_agent(
                Principal("tenant-b", "oms", "agent"),
                "g1",
                "r1",
                "https://synthetic.invalid/inference",
                "synthetic-model",
                1,
                1,
            )
        self.assertEqual(self.count("reservations"), 0)

    def test_budget_concurrency(self):
        self.grant("g1")
        self.grant("g2")
        result = self.race([lambda: self.reserve("g1", "r1"), lambda: self.reserve("g2", "r2")])
        self.assertEqual(result.count("REJECTED"), 1)
        with self.p.connection() as db:
            self.assertEqual(db.execute("SELECT reserved FROM agent_budget").fetchone()[0], 6)

    def test_one_use_grant_and_idempotent_reservation(self):
        self.grant()
        self.reserve()
        self.reserve()
        with self.assertRaises(Rejected):
            self.reserve(reservation="r2")
        with self.assertRaises(Rejected):
            self.reserve(units=5)
        self.assertEqual(self.count("reservations"), 1)
        self.assertEqual(self.count("audit"), 3)

    def test_missing_grant_invalid_units(self):
        for units in (0, -1, True):
            with self.subTest(units=units), self.assertRaises(Rejected):
                self.reserve(units=units)
        with self.assertRaises(Rejected):
            self.reserve()


if __name__ == "__main__":
    unittest.main()
