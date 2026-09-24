"""Unit tests for the draft-only Odoo adapter (D-26)."""

from __future__ import annotations

import pytest

from api.odoo import (
    OdooDraftAdapter,
    OdooProhibitedMethodError,
    OdooTransportError,
)


class FakeTransport:
    def __init__(self, existing_partners: list[int] | None = None, fail: bool = False):
        self.calls: list[tuple[str, str]] = []
        self.existing_partners = existing_partners or []
        self.fail = fail
        self.next_id = 1000

    def execute_kw(self, model, method, args, kwargs):
        self.calls.append((model, method))
        if self.fail:
            raise ConnectionError("synthetic transport failure")
        if model == "res.partner" and method == "search":
            return self.existing_partners
        self.next_id += 1
        return self.next_id


def test_partner_reuse_and_create_paths():
    reuse = OdooDraftAdapter(FakeTransport(existing_partners=[42]))
    assert reuse.find_or_create_partner("a@example.invalid", "A") == 42

    transport = FakeTransport()
    adapter = OdooDraftAdapter(transport)
    partner_id = adapter.find_or_create_partner("b@example.invalid", "B")
    assert transport.calls == [("res.partner", "search"), ("res.partner", "create")]
    assert partner_id == 1001


def test_draft_invoice_and_vendor_bill_use_account_move_create():
    transport = FakeTransport()
    adapter = OdooDraftAdapter(transport)
    invoice_id = adapter.create_draft_customer_invoice(42, "ref-1", "100.00", "INR")
    bill_id = adapter.create_draft_vendor_bill(42, "ref-2", "250.00", "INR")
    assert invoice_id != bill_id
    assert transport.calls == [
        ("account.move", "create"),
        ("account.move", "create"),
    ]


@pytest.mark.parametrize(
    "method",
    [
        "action_post",
        "action_register_payment",
        "action_validate",
        "button_validate",
        "button_draft",
        "action_confirm",
        "write",
        "unlink",
    ],
)
def test_prohibited_methods_never_reach_transport(method):
    transport = FakeTransport()
    adapter = OdooDraftAdapter(transport)
    with pytest.raises(OdooProhibitedMethodError):
        adapter._execute("account.move", method, [], {})
    assert transport.calls == []


def test_non_allowlisted_model_or_method_refused():
    transport = FakeTransport()
    adapter = OdooDraftAdapter(transport)
    with pytest.raises(OdooProhibitedMethodError):
        adapter._execute("sale.order", "create", [], {})
    with pytest.raises(OdooProhibitedMethodError):
        adapter._execute("res.partner", "unlink", [], {})
    with pytest.raises(OdooProhibitedMethodError):
        adapter._create_draft_move(1, "r", "1.00", "INR", "entry")
    assert transport.calls == []


def test_transport_failure_is_normalized():
    adapter = OdooDraftAdapter(FakeTransport(fail=True))
    with pytest.raises(OdooTransportError):
        adapter.find_or_create_partner("c@example.invalid", "C")
