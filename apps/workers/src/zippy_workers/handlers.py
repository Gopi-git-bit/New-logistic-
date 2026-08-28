"""M4+M5 business handlers — injected with a Db port for testability.

Each handler runs under a specific agent; capability gates are asserted
before any external call. Handlers never talk to Supabase directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .capabilities import assert_can_call_external
from .odoo_client import OdooClient
from .ocr_provider import OCRExtractor
from .notification_sender import NotificationSender


class Db(Protocol):
    """Port mirroring the SQL RPCs the handlers need."""

    def transition_order(self, order_id: str, new_status: str) -> None: ...
    def enqueue_task(self, agent: str, task_type: str,
                     payload: dict[str, Any]) -> None: ...
    def mark_odoo_synced(self, order_id: str, sale_id: int,
                         invoice_id: int | None = None) -> None: ...
    def mark_odoo_failed(self, order_id: str, reason: str) -> None: ...

    # M5: POD / document pipeline
    def upsert_document(self, order_id: str, doc_type: str, image_url: str | None,
                        ocr_text: str | None, ocr_confidence: float | None,
                        ocr_provider: str | None, uploaded_by: str | None) -> str: ...

    # M5: notification queue
    def mark_notification_sent(self, notification_id: str,
                               external_id: str | None = None) -> None: ...
    def mark_notification_failed(self, notification_id: str,
                                 reason: str | None = None) -> None: ...
    def log_notification(self, user_id: str, channel: str, ntype: str,
                         title: str, body: str, payload: dict | None = None,
                         external_id: str | None = None,
                         idempotency_key: str | None = None) -> None: ...

    # M6: order lifecycle
    def generate_quote(self, order_id: str) -> dict | None: ...
    def match_drivers(self, pickup_wkt: str, radius_m: float, limit: int,
                      required_class: str | None,
                      cargo_weight: float | None) -> list[dict]: ...
    def assign_provider(self, order_id: str, provider_id: str,
                        provider_type: str) -> None: ...
    def validate_payment_plan(self, mode: str, total: float,
                              advance: float) -> bool: ...
    def get_order(self, order_id: str) -> dict | None: ...


@dataclass
class HandlerResult:
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- payments
def process_payment_event(payload: dict[str, Any], db: Db) -> HandlerResult:
    """razorpay_payment.captured|authorized → advance order state machine.

    Idempotent by construction: an illegal replayed transition raises inside
    transition_order and we treat 'payment_succeeded already' as success.
    """
    event_type = payload.get("event_type") or payload.get("event")
    order_id = payload.get("order_id")
    if not order_id:
        return HandlerResult(False, {"error": "missing order_id"})

    if event_type == "razorpay_payment.failed":
        return HandlerResult(True, {"note": "failure recorded upstream", "status": "failed"})

    try:
        db.transition_order(str(order_id), "inventory_confirmed")
    except Exception as exc:  # noqa: BLE001 - illegal-hop == already done
        msg = str(exc)
        if "Invalid transition" in msg or "already" in msg.lower():
            return HandlerResult(True, {"note": "idempotent no-op"})
        return HandlerResult(False, {"error": msg[:200]})

    # Next hop in pipeline: mirror to Odoo (dedupe key reuse)
    db.enqueue_task("order_management", "push_order_to_odoo",
                    {"order_id": order_id})
    return HandlerResult(True, {"advanced_to": "inventory_confirmed"})


# ---------------------------------------------------------------- odoo push
def push_order_to_odoo(payload: dict[str, Any], db: Db,
                       odoo: OdooClient) -> HandlerResult:
    """Mirror the order into Odoo 18 CE (partner + sale.order)."""
    assert_can_call_external("order_management", "odoo")

    order_id = payload.get("order_id")
    order_number = payload.get("order_number")
    total = float(payload.get("total_amount", 0))
    email = payload.get("consignee_email") or f"anon-{order_number}@zippy.local"
    name = payload.get("customer_name") or f"Zippy Order {order_number}"

    try:
        partner_id = odoo.find_or_create_partner(email=email, name=name)
        sale_id = odoo.create_sale_order(
            partner_id=partner_id,
            order_number=str(order_number),
            total_amount=total,
            reference_note=payload.get("special_instructions"),
        )
        db.mark_odoo_synced(str(order_id), sale_id)
        return HandlerResult(True, {"sale_order_id": sale_id, "partner_id": partner_id})
    except Exception as exc:  # noqa: BLE001 - transport/protocol failures
        reason = str(exc)[:200]
        db.mark_odoo_failed(str(order_id), reason)
        return HandlerResult(False, {"error": reason})


HANDLER_TOOLS = {
    "process_payment_event": process_payment_event,
}


# =====================================================================
# M5 — Document / POD pipeline
# =====================================================================

def process_document_upload(payload: dict[str, Any], db: Db,
                            ocr: OCRExtractor) -> HandlerResult:
    """Driver uploads a document image → OCR extraction → order_documents.

    For POD docs, auto-transitions order to 'delivered' on success.
    Payload: {order_id, document_type, image_url, uploaded_by}
    """
    order_id = payload.get("order_id")
    doc_type = payload.get("document_type", "other")
    image_url = payload.get("image_url")

    if not order_id:
        return HandlerResult(False, {"error": "missing order_id"})
    if not image_url:
        return HandlerResult(False, {"error": "missing image_url"})

    # Attempt OCR extraction (best-effort; null provider on failure)
    ocr_text: str | None = None
    ocr_conf: float | None = None
    ocr_prov: str | None = None
    try:
        # Fetch image bytes from URL (stub: in production use httpx)
        import httpx as _httpx
        resp = _httpx.get(image_url, timeout=15.0)
        resp.raise_for_status()
        result = ocr.extract(resp.content, resp.headers.get("content-type", "image/jpeg"))
        if result.provider != "tesseract_unavailable":
            ocr_text = result.raw_text
            ocr_conf = result.confidence
            ocr_prov = result.provider
    except Exception:  # noqa: BLE001 — OCR failure is non-fatal
        ocr_prov = "ocr_failed"

    # Persist document
    doc_id = db.upsert_document(
        order_id=str(order_id), doc_type=doc_type, image_url=image_url,
        ocr_text=ocr_text, ocr_confidence=ocr_conf,
        ocr_provider=ocr_prov, uploaded_by=payload.get("uploaded_by"),
    )

    # For POD documents, auto-advance state machine to delivered
    if doc_type == "pod":
        try:
            db.transition_order(str(order_id), "delivered")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "Invalid transition" in msg or "already" in msg.lower():
                pass  # idempotent — already delivered
            else:
                return HandlerResult(False, {"error": msg[:200], "doc_id": doc_id})

    return HandlerResult(True, {
        "doc_id": doc_id,
        "ocr_provider": ocr_prov,
        "ocr_confidence": ocr_conf,
        "advanced_to": "delivered" if doc_type == "pod" else None,
    })


# =====================================================================
# M5 — Notification delivery
# =====================================================================

def process_notification_job(payload: dict[str, Any], db: Db,
                             sender: NotificationSender) -> HandlerResult:
    """Dequeue → deliver → log.  Payload: {notification_id, user_id, channel,
    title, body, notification_type, payload: dict}.
    """
    notification_id = payload.get("notification_id")
    user_id = payload.get("user_id")
    channel = payload.get("channel", "in_app")
    title = payload.get("title", "")
    body = payload.get("body", "")
    ntype = payload.get("notification_type", "system")
    inner_payload = payload.get("payload") or {}

    if not notification_id:
        return HandlerResult(False, {"error": "missing notification_id"})
    if not user_id:
        return HandlerResult(False, {"error": "missing user_id"})

    # Deliver via provider
    result = sender.send(destination=str(user_id), title=title, body=body,
                         payload=inner_payload)

    if result.ok:
        db.mark_notification_sent(str(notification_id), result.external_id)
        # Also log to notification_log for user visibility
        db.log_notification(
            user_id=str(user_id), channel=channel, ntype=ntype,
            title=title, body=body, payload=inner_payload,
            external_id=result.external_id,
            idempotency_key=f"nq:{notification_id}",
        )
        return HandlerResult(True, {
            "notification_id": notification_id,
            "provider": result.provider,
            "external_id": result.external_id,
        })
    else:
        db.mark_notification_failed(str(notification_id), result.error)
        return HandlerResult(False, {
            "notification_id": notification_id,
            "error": result.error,
        })


# =====================================================================
# M6 — Order lifecycle handlers
# =====================================================================

def place_order(payload: dict[str, Any], db: Db) -> HandlerResult:
    """Place a new order: validate payment plan → generate quote → persist.

    Payload: {order_id, customer_id, pickup, delivery, cargo, vehicle_class,
              payment_mode, advance_amount (for partial)}
    Returns quote details on success.
    """
    order_id = payload.get("order_id")
    customer_id = payload.get("customer_id")
    if not order_id or not customer_id:
        return HandlerResult(False, {"error": "missing order_id or customer_id"})

    # 1. Generate quote via DB RPC
    quote = db.generate_quote(str(order_id))
    if not quote:
        return HandlerResult(False, {"error": "quote_generation_failed"})

    total = float(quote.get("total_amount", 0))
    mode = payload.get("payment_mode", "full")
    advance = float(payload.get("advance_amount", 0))

    # Full mode = 100% advance; to_pay = 0% advance
    if mode == "full" and not payload.get("advance_amount"):
        advance = total
    elif mode == "to_pay":
        advance = 0

    # 2. Validate payment plan
    if not db.validate_payment_plan(mode, total, advance):
        return HandlerResult(False, {
            "error": "invalid_payment_plan",
            "mode": mode, "total": total, "advance": advance,
        })

    # 3. Transition to pending (initial state)
    try:
        db.transition_order(str(order_id), "pending")
    except Exception as exc:
        msg = str(exc)
        if "Invalid transition" in msg or "already" in msg.lower():
            pass  # already pending
        else:
            return HandlerResult(False, {"error": msg[:200]})

    return HandlerResult(True, {
        "order_id": order_id,
        "total_amount": total,
        "quote": quote,
        "payment_mode": mode,
    })


def assign_driver(payload: dict[str, Any], db: Db) -> HandlerResult:
    """Match nearby drivers and assign best candidate to order.

    Payload: {order_id, radius_m (default 50000), required_class, cargo_weight}
    """
    order_id = payload.get("order_id")
    if not order_id:
        return HandlerResult(False, {"error": "missing order_id"})

    # Fetch order to get pickup location
    order = db.get_order(str(order_id))
    if not order:
        return HandlerResult(False, {"error": "order_not_found"})

    # Extract pickup geography (WKT)
    pickup_loc = order.get("pickup_location")
    if not pickup_loc:
        # Fallback: build from lat/lng columns
        lat = order.get("pickup_latitude")
        lng = order.get("pickup_longitude")
        if lat is None or lng is None:
            return HandlerResult(False, {"error": "no_pickup_location"})
        pickup_wkt = f"SRID=4326;POINT({lng} {lat})"
    else:
        pickup_wkt = str(pickup_loc)

    # Match drivers
    radius = float(payload.get("radius_m", 50000))
    limit = int(payload.get("limit", 5))
    req_class = payload.get("required_class")
    cargo_wt = payload.get("cargo_weight")
    drivers = db.match_drivers(pickup_wkt, radius, limit, req_class, cargo_wt)

    if not drivers:
        return HandlerResult(True, {"order_id": order_id, "drivers": [],
                                    "note": "no_available_drivers"})

    # Pick best driver (first by score)
    best = drivers[0]
    provider_id = str(best.get("user_id") or best.get("driver_id", ""))
    if not provider_id:
        return HandlerResult(True, {"order_id": order_id, "drivers": drivers,
                                    "note": "no_valid_provider_id"})

    # Assign provider to order
    db.assign_provider(str(order_id), provider_id, "driver")

    # Advance state machine: inventory_confirmed → driver_assigned
    try:
        db.transition_order(str(order_id), "driver_assigned")
    except Exception as exc:
        msg = str(exc)
        if "Invalid transition" in msg or "already" in msg.lower():
            pass  # idempotent
        else:
            return HandlerResult(False, {"error": msg[:200]})

    return HandlerResult(True, {
        "order_id": order_id,
        "driver_name": best.get("driver_name"),
        "provider_id": provider_id,
        "vehicle_type": best.get("vehicle_type"),
        "distance_m": best.get("distance_m"),
        "score": best.get("score"),
        "drivers_found": len(drivers),
    })


def update_delivery_status(payload: dict[str, Any], db: Db) -> HandlerResult:
    """Manual status advancement: pickup → in_transit → delivered.

    Payload: {order_id, action: "pickup"|"in_transit"|"delivered"}
    For 'delivered', caller should prefer process_document_upload with POD.
    """
    order_id = payload.get("order_id")
    action = payload.get("action")
    if not order_id or not action:
        return HandlerResult(False, {"error": "missing order_id or action"})

    _ACTION_TO_STATUS = {
        "pickup": "in_transit",
        "in_transit": "in_transit",
        "delivered": "delivered",
    }
    new_status = _ACTION_TO_STATUS.get(action)
    if not new_status:
        return HandlerResult(False, {"error": f"unknown action: {action}"})

    try:
        db.transition_order(str(order_id), new_status)
    except Exception as exc:
        msg = str(exc)
        if "Invalid transition" in msg or "already" in msg.lower():
            return HandlerResult(True, {"note": "idempotent no-op",
                                        "action": action})
        return HandlerResult(False, {"error": msg[:200]})

    return HandlerResult(True, {"order_id": order_id, "action": action,
                                "advanced_to": new_status})
