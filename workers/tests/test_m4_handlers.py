"""M4 handler + Odoo client tests (no network, fakes for Db/Odoo)."""

from types import SimpleNamespace

import httpx
import pytest

from zippy_workers.capabilities import UnauthorizedCapability, assert_can_call_external
from zippy_workers.config import WorkerSettings
from zippy_workers.handlers import process_payment_event
from zippy_workers.kernel import default_tools_for, run_one_tick
from zippy_workers.odoo_client import OdooClient


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
def test_payment_captured_advances_without_odoo_work():
    db = FakeDb()
    r = process_payment_event({"event_type": "razorpay_payment.captured", "order_id": "o-1"}, db)
    assert r.ok and ("o-1", "inventory_confirmed") in db.transitions
    assert not db.tasks
    assert not db.synced and not db.failed


def test_payment_replay_is_idempotent_noop():
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
    r = process_payment_event({"event_type": "razorpay_payment.failed", "order_id": "o-3"}, db)
    assert r.ok and "failed" in r.detail["status"]
    assert not db.transitions


# ---------------------------------------------------------------- odoo push
@pytest.mark.parametrize("agent", ["order_management", "resource_management", "communication"])
def test_active_capability_matrix_denies_odoo(agent):
    with pytest.raises(UnauthorizedCapability):
        assert_can_call_external(agent, "odoo")


def test_default_runtime_has_no_odoo_dependency(monkeypatch):
    monkeypatch.setattr("zippy_workers.ocr_provider.make_ocr_provider", lambda: object())
    monkeypatch.setattr("zippy_workers.notification_sender.make_notification_sender", lambda: object())
    settings = WorkerSettings()
    tools = default_tools_for(FakeDb(), settings)
    assert "push_order_to_odoo" not in tools
    assert {"process_payment_event", "place_order", "assign_driver", "update_delivery_status"} <= tools.keys()
    assert not any(name.startswith("odoo_") for name in WorkerSettings.model_fields)


def test_existing_odoo_task_is_failed_not_completed():
    class TaskSource(FakeDb):
        def __init__(self):
            super().__init__()
            self.completed = []
            self.spent = []
            self.beats = []

        def claim(self, *_):
            return SimpleNamespace(data=[{
                "task_id": "legacy-odoo-1",
                "task_type": "push_order_to_odoo",
                "payload": {"order_id": "o-1"},
            }])

        def complete(self, *args):
            self.completed.append(args)

        def fail(self, task_id, reason):
            self.failed.append((task_id, reason))

        def spend(self, *args):
            self.spent.append(args)

        def beat(self, agent):
            self.beats.append(agent)

    source = TaskSource()
    assert run_one_tick("order_management", "worker-1", source, {}, WorkerSettings()) == 1
    assert source.failed == [("legacy-odoo-1", "no_handler:push_order_to_odoo")]
    assert not source.completed and not source.spent and not source.synced
    assert source.beats == ["order_management"]


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
