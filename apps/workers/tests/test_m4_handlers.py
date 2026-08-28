"""M4 handler + Odoo client tests (no network, fakes for Db/Odoo)."""

import httpx

from zippy_workers.capabilities import UnauthorizedCapability, assert_can_call_external
from zippy_workers.handlers import process_payment_event, push_order_to_odoo
from zippy_workers.odoo_client import OdooClient, OdooError


class FakeDb:
    def __init__(self):
        self.transitions: list[tuple[str, str]] = []
        self.tasks: list[tuple[str, str, dict]] = []
        self.synced: list[tuple[str, int | None]] = []
        self.failed: list[tuple[str, str]] = []

    def transition_order(self, order_id, new_status):
        self.transitions.append((order_id, new_status))

    def enqueue_task(self, agent, task_type, payload):
        self.tasks.append((agent, task_type, payload))

    def mark_odoo_synced(self, order_id, sale_id, invoice_id=None):
        self.synced.append((order_id, sale_id))

    def mark_odoo_failed(self, order_id, reason):
        self.failed.append((order_id, reason))


# ---------------------------------------------------------------- payments
def test_payment_captured_advances_and_enqueues():
    db = FakeDb()
    r = process_payment_event(
        {"event_type": "razorpay_payment.captured", "order_id": "o-1"}, db)
    assert r.ok and ("o-1", "inventory_confirmed") in db.transitions
    assert db.tasks[0][1] == "push_order_to_odoo"


def test_payment_replay_is_idempotent_noop():
    db = FakeDb()

    class Replayed(FakeDb):
        def transition_order(self, *_):
            raise RuntimeError("Invalid transition from inventory_confirmed")

    r = process_payment_event({"event_type": "x", "order_id": "o-2"}, Replayed())
    assert r.ok and r.detail["note"] == "idempotent no-op"


def test_missing_order_id_rejected():
    r = process_payment_event({}, FakeDb())
    assert not r.ok


def test_failed_event_short_circuits():
    db = FakeDb()
    r = process_payment_event({"event_type": "razorpay_payment.failed",
                               "order_id": "o-3"}, db)
    assert r.ok and "failed" in r.detail["status"]
    assert not db.transitions


# ---------------------------------------------------------------- odoo push
def test_push_happy_path_marks_synced():
    class FakeOdoo:
        def find_or_create_partner(self, email, name): return 42

        def create_sale_order(self, **kw): return 9001

    db = FakeDb()
    r = push_order_to_odoo({"order_id": "o-9", "order_number": "ZP-1",
                            "total_amount": 3463.95}, db, FakeOdoo())
    assert r.ok and r.detail["sale_order_id"] == 9001
    assert db.synced == [("o-9", 9001)] and not db.failed


def test_push_transport_failure_marks_failed():
    class BoomOdoo:
        def find_or_create_partner(self, **_): raise OdooError("transport:ConnectError")

    db = FakeDb()
    r = push_order_to_odoo({"order_id": "o-10", "order_number": "ZP-2"},
                           db, BoomOdoo())
    assert not r.ok and "transport" in db.failed[0][1]


def test_capability_matrix_gates_odoo_to_correct_agents():
    assert_can_call_external("order_management", "odoo")     # allowed
    assert_can_call_external("resource_management", "odoo")  # allowed
    try:
        assert_can_call_external("communication", "odoo")
        raise AssertionError("communication must not reach odoo")
    except UnauthorizedCapability:
        pass


# ---------------------------------------------------------------- odoo client request shape
def test_jsonrpc_body_shape_over_fake_transport():
    import json as _json

    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = _json.loads(request.content)
        calls.append(body)
        svc = body["params"]["service"]
        if svc == "common":
            return httpx.Response(200, json={"result": 7})
        method = body["params"]["method"]
        args = body["params"]["args"]
        assert svc == "object" and method == "execute_kw"
        # [db, uid, key, model, method, [args], {kwargs}]
        if args[5] == [[["email", "=", "e@x"]]]:
            return httpx.Response(200, json={"result": [11]})
        return httpx.Response(400, json={"error": {"data": {"message": "bad"}}})

    client = OdooClient("http://odoo.test", "db", "u", "k", timeout_s=1)
    client._http = httpx.Client(transport=httpx.MockTransport(handler), timeout=1)

    uid = client.authenticate()
    assert uid == 7

    ids = client.execute_kw("res.partner", "search", [[["email", "=", "e@x"]]])
    assert ids == [11]
    assert len(calls) == 2
    assert calls[-1]["params"]["args"][0:3] == ["db", 7, "k"]
