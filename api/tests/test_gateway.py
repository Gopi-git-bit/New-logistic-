"""Unit tests for Razorpay sandbox webhook verification and parsing."""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from api.gateway import (
    EVENT_PROJECTION_STATUS,
    MAX_AMOUNT_MINOR_UNITS,
    RECONCILE_ONLY_EVENTS,
    MalformedEventError,
    major_units_to_minor,
    minor_units_to_major,
    parse_event,
    payload_hash,
    verify_signature,
)

SECRET = "m4-synthetic-webhook-secret-32bytes!"
ORDER_A = "30000000-0000-0000-0000-00000000000a"
PROVIDER_ORDER_REF = "order_syn_a"


def _sign(raw: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _payment_body(
    event: str = "payment.captured",
    event_id: str = "evt_syn_1",
    amount: object = 10000,
    order_id_field: object = PROVIDER_ORDER_REF,
) -> bytes:
    entity: dict[str, object] = {
        "id": "pay_syn_1",
        "amount": amount,
        "currency": "INR",
        "notes": {"zippy_order_id": ORDER_A},
    }
    if order_id_field is not None:
        entity["order_id"] = order_id_field
    return json.dumps(
        {
            "id": event_id,
            "event": event,
            "payload": {"payment": {"entity": entity}},
        }
    ).encode()


def test_valid_signature_accepted():
    raw = _payment_body()
    assert verify_signature(raw, _sign(raw), SECRET) is True


def test_tampered_body_or_wrong_secret_rejected():
    raw = _payment_body()
    assert verify_signature(raw + b" ", _sign(raw), SECRET) is False
    assert verify_signature(raw, _sign(raw, "other-secret"), SECRET) is False
    assert verify_signature(raw, _sign(raw)[:-2] + "00", SECRET) is False


def test_missing_inputs_fail_closed():
    raw = _payment_body()
    assert verify_signature(raw, None, SECRET) is False
    assert verify_signature(raw, "", SECRET) is False
    assert verify_signature(raw, _sign(raw), "") is False


def test_parse_captured_event_uses_provider_reference_not_notes():
    raw = _payment_body()
    event = parse_event(raw)
    assert event.provider == "razorpay"
    assert event.provider_event_id == "evt_syn_1"
    assert event.event_type == "payment.captured"
    assert event.payment_id == "pay_syn_1"
    assert event.provider_reference_id == PROVIDER_ORDER_REF
    assert event.amount_minor_units == 10000
    assert event.currency == "INR"
    # notes are preserved only as untrusted evidence, never as a trusted link
    assert event.notes == {"zippy_order_id": ORDER_A}
    assert event.evidence_hash == payload_hash(raw)


def test_parse_event_without_provider_reference_has_none():
    raw = _payment_body(order_id_field=None)
    event = parse_event(raw)
    assert event.provider_reference_id is None
    assert event.notes == {"zippy_order_id": ORDER_A}


@pytest.mark.parametrize(
    "amount",
    [True, False, 10000.0, "10000", -1, 0, MAX_AMOUNT_MINOR_UNITS + 1],
)
def test_amount_validation_rejects_unsafe_values(amount):
    raw = _payment_body(amount=amount)
    event = parse_event(raw)
    assert event.amount_minor_units is None


def test_amount_validation_accepts_boundary_values():
    raw = _payment_body(amount=1)
    assert parse_event(raw).amount_minor_units == 1
    raw = _payment_body(amount=MAX_AMOUNT_MINOR_UNITS)
    assert parse_event(raw).amount_minor_units == MAX_AMOUNT_MINOR_UNITS


def test_minor_major_conversions_are_exact_and_reversible():
    assert minor_units_to_major(10000) == Decimal("100.00")
    assert minor_units_to_major(1) == Decimal("0.01")
    assert major_units_to_minor(Decimal("100.00")) == 10000
    assert major_units_to_minor(Decimal("0.01")) == 1


def test_parse_refund_event_extracts_refund_id():
    raw = json.dumps(
        {
            "id": "evt_syn_rfnd",
            "event": "refund.processed",
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_syn_1",
                        "payment_id": "pay_syn_1",
                        "amount": 10000,
                        "currency": "INR",
                        "notes": {"zippy_order_id": ORDER_A},
                    }
                }
            },
        }
    ).encode()
    event = parse_event(raw)
    assert event.event_type == "refund.processed"
    assert event.refund_id == "rfnd_syn_1"
    assert event.event_type in RECONCILE_ONLY_EVENTS
    # refunds never resolve through a provider order reference
    assert event.provider_reference_id is None


def test_malformed_bodies_rejected():
    with pytest.raises(MalformedEventError):
        parse_event(b"{")
    with pytest.raises(MalformedEventError):
        parse_event(json.dumps(["not", "object"]).encode())
    with pytest.raises(MalformedEventError):
        parse_event(json.dumps({"event": "payment.captured"}).encode())
    with pytest.raises(MalformedEventError):
        parse_event(json.dumps({"id": "evt_x"}).encode())


def test_unsupported_and_incomplete_events_parse_safely():
    unsupported = parse_event(json.dumps({"id": "evt_u", "event": "order.paid"}).encode())
    assert unsupported.event_type not in EVENT_PROJECTION_STATUS
    no_amount = parse_event(
        json.dumps(
            {
                "id": "evt_na",
                "event": "payment.failed",
                "payload": {"payment": {"entity": {"id": "pay_x", "amount": "bad"}}},
            }
        ).encode()
    )
    assert no_amount.amount_minor_units is None
    assert no_amount.provider_reference_id is None
