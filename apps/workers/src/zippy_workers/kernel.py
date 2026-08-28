"""Heartbeat kernel — claims and executes agent tasks each tick.

D-17 enforcement lives DB-side: claim_agent_tasks() raises AGENT_PAUSED /
AGENT_BUDGET_EXHAUSTED before any work starts, so a paused or unfunded
agent consumes zero tool calls.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from .config import WorkerSettings, get_settings
from .executor import Executor, TaskContext
from .loop_guardian import LoopGuardian


class SupabaseTaskSource:
    """Thin RPC-backed queue client (service-role)."""

    def __init__(self, settings: WorkerSettings) -> None:
        if not (settings.supabase_url and settings.supabase_service_role_key):
            raise RuntimeError("supabase_url/service key required for kernel")
        from supabase import create_client  # deferred heavy import

        self._client = create_client(settings.supabase_url,
                                     settings.supabase_service_role_key)
        self._settings = settings

    def claim(self, agent: str, worker_id: str, heartbeat_id: str):
        return self._client.rpc(
            "claim_agent_tasks",
            {"p_agent_name": agent, "p_claimed_by": worker_id,
             "p_limit": self._settings.claim_batch_size,
             "p_heartbeat_id": heartbeat_id},
        ).execute()

    def complete(self, task_id: str, result: dict) -> None:
        self._client.rpc("complete_agent_task",
                         {"p_task_id": task_id, "p_result": result}).execute()

    def fail(self, task_id: str, error: str) -> None:
        self._client.rpc("fail_agent_task",
                         {"p_task_id": task_id, "p_error": error}).execute()

    def spend(self, agent: str, cents: int) -> None:
        self._client.rpc("record_agent_spend",
                         {"p_agent_name": agent, "p_amount_cents": cents}).execute()

    def beat(self, agent: str) -> None:
        self._client.rpc("heartbeat_agent", {"p_agent_name": agent}).execute()

    # ---- Db port for business handlers (M4) --------------------------------
    def transition_order(self, order_id: str, new_status: str) -> None:
        self._client.rpc("transition_order",
                         {"p_order_id": order_id, "p_new_status": new_status,
                          "p_actor_id": None, "p_actor_role": "system"}).execute()

    def enqueue_task(self, agent: str, task_type: str, payload: dict) -> None:
        self._client.rpc("enqueue_agent_task",
                         {"p_agent_name": agent, "p_task_type": task_type,
                          "p_payload": payload}).execute()

    def mark_odoo_synced(self, order_id: str, sale_id: int,
                         invoice_id: int | None = None) -> None:
        self._client.rpc("mark_odoo_synced",
                         {"p_order_id": order_id, "p_sale_order_id": sale_id,
                          "p_invoice_id": invoice_id}).execute()

    def mark_odoo_failed(self, order_id: str, reason: str) -> None:
        self._client.rpc("mark_odoo_failed",
                         {"p_order_id": order_id, "p_reason": reason}).execute()

    # ---- Db port for business handlers (M6) --------------------------------
    def generate_quote(self, order_id: str) -> dict | None:
        res = self._client.rpc("generate_order_quote",
                               {"p_order_id": order_id}).execute()
        if res.data and len(res.data) > 0:
            return dict(res.data[0]) if isinstance(res.data[0], dict) else {"total_amount": res.data[0][-1]}
        return None

    def match_drivers(self, pickup_wkt: str, radius_m: float, limit: int,
                      required_class: str | None,
                      cargo_weight: float | None) -> list[dict]:
        # Convert WKT POINT to GeoJSON dict for Supabase PostgREST
        # Format: "SRID=4326;POINT(lng lat)" or "POINT(lng lat)"
        raw = pickup_wkt.replace("SRID=4326;", "").strip()
        coords = raw.split("(")[1].rstrip(")").split()
        lng, lat = float(coords[0]), float(coords[1])
        geo_json = {"type": "Point", "coordinates": [lng, lat]}
        params = {"p_pickup": geo_json, "p_radius_m": radius_m, "p_limit": limit}
        if required_class:
            params["p_required_class"] = required_class
        if cargo_weight is not None:
            params["p_cargo_weight_t"] = cargo_weight
        res = self._client.rpc("match_nearby_drivers", params).execute()
        return [dict(r) for r in (res.data or [])]

    def assign_provider(self, order_id: str, provider_id: str,
                        provider_type: str) -> None:
        self._client.rpc("assign_order_provider", {
            "p_order_id": order_id, "p_provider_id": provider_id,
            "p_provider_type": provider_type,
        }).execute()

    def validate_payment_plan(self, mode: str, total: float,
                              advance: float) -> bool:
        res = self._client.rpc("validate_payment_plan", {
            "p_mode": mode, "p_total_amount": total,
            "p_advance_amount": advance,
        }).execute()
        return bool(res.data)

    def get_order(self, order_id: str) -> dict | None:
        res = self._client.table("orders").select("*").eq(
            "order_id", order_id).limit(1).execute()
        if res.data and len(res.data) > 0:
            return dict(res.data[0])
        return None

    # ---- Db port for business handlers (M5) --------------------------------
    def upsert_document(self, order_id: str, doc_type: str, image_url: str | None,
                        ocr_text: str | None, ocr_confidence: float | None,
                        ocr_provider: str | None, uploaded_by: str | None) -> str:
        # M5 RPC: upsert_order_document
        res = self._client.rpc("upsert_order_document", {
            "p_order_id": order_id, "p_doc_type": doc_type,
            "p_image_url": image_url, "p_ocr_raw_text": ocr_text,
            "p_ocr_confidence": ocr_confidence, "p_ocr_provider": ocr_provider,
            "p_uploaded_by": uploaded_by,
        }).execute()
        return str(res.data) if res.data else ""

    def mark_notification_sent(self, notification_id: str,
                               external_id: str | None = None) -> None:
        self._client.rpc("mark_notification_sent",
                         {"p_notification_id": notification_id,
                          "p_external_id": external_id}).execute()

    def mark_notification_failed(self, notification_id: str,
                                 reason: str | None = None) -> None:
        self._client.rpc("mark_notification_failed",
                         {"p_notification_id": notification_id,
                          "p_reason": reason}).execute()

    def log_notification(self, user_id: str, channel: str, ntype: str,
                         title: str, body: str, payload: dict | None = None,
                         external_id: str | None = None,
                         idempotency_key: str | None = None) -> None:
        self._client.table("notification_log").insert({
            "user_id": user_id, "channel": channel, "notification_type": ntype,
            "title": title, "body": body, "payload": payload or {},
            "external_id": external_id, "idempotency_key": idempotency_key,
        }).execute()

    def set_status(self, agent: str, status: str, reason: str | None = None) -> None:
        """Persist pause/block AFTER a failed claim (statement-level atomicity
        means side effects inside a failed RPC are rolled back)."""
        self._client.rpc("set_agent_status",
                         {"p_agent_name": agent, "p_status": status,
                          "p_reason": reason}).execute()


def run_one_tick(agent: str, worker_id: str, source: SupabaseTaskSource,
                 tool_fn_by_type: dict[str, Callable[[dict], dict]],
                 settings: WorkerSettings | None = None) -> int:
    """One heartbeat cycle for `agent`. Returns tasks executed (done+failed)."""
    settings = settings or get_settings()
    guardian = LoopGuardian(max_tool_calls=settings.max_tool_calls_per_tick)
    executor = Executor(agent, guardian)

    hb = uuid.uuid4()
    claimed = source.claim(agent, worker_id, str(hb)).data or []

    for row in claimed:
        ctx = TaskContext(agent=agent, task_id=row["task_id"],
                          task_type=row.get("task_type") or "",
                          payload=row.get("payload") or {})
        tool = tool_fn_by_type.get(ctx.task_type)
        if tool is None:
            source.fail(ctx.task_id, f"no_handler:{ctx.task_type}")
            continue

        result = executor.run(ctx, tool)
        if result.ok:
            source.complete(ctx.task_id, result.output or {})
            # simple accounting hook: 0.5c per completed task until per-call pricing lands
            source.spend(agent, 1)
        else:
            source.fail(ctx.task_id, f"{result.final_state.value}:{result.reason}")

    source.beat(agent)
    return len(claimed)


def default_tools_for(source: SupabaseTaskSource,
                      settings: WorkerSettings) -> dict:
    """Wire M4+M5+M6 handlers to RPC-backed Db."""
    from .handlers import process_payment_event, push_order_to_odoo
    from .handlers import process_document_upload, process_notification_job
    from .handlers import place_order, assign_driver, update_delivery_status
    from .odoo_client import OdooClient
    from .ocr_provider import make_ocr_provider
    from .notification_sender import make_notification_sender

    def _odoo():
        if not settings.odoo_url:
            raise RuntimeError("ODOO_URL missing")
        return OdooClient(settings.odoo_url, settings.odoo_db,
                          settings.odoo_user, settings.odoo_api_key or "")

    ocr = make_ocr_provider()
    sender = make_notification_sender()

    return {
        "process_payment_event": lambda payload: process_payment_event(payload, source),
        "push_order_to_odoo": lambda payload: push_order_to_odoo(payload, source, _odoo()),
        "process_document_upload": lambda payload: process_document_upload(payload, source, ocr),
        "process_notification_job": lambda payload: process_notification_job(payload, source, sender),
        "place_order": lambda payload: place_order(payload, source),
        "assign_driver": lambda payload: assign_driver(payload, source),
        "update_delivery_status": lambda payload: update_delivery_status(payload, source),
    }


class Kernel:
    def __init__(self, agents: list[str],
                 tools_by_agent: dict[str, dict[str, Callable[[dict], dict]]] | None = None):
        self.agents = agents
        self.tools = tools_by_agent or {}
        self.stop_after_ticks: int | None = None   # test hook

    def start_forever(self) -> None:  # pragma: no cover - production loop
        s = get_settings()
        src = SupabaseTaskSource(s)
        i = 0
        while True:
            t0 = time.time()
            for a in self.agents:
                try:
                    tools = self.tools.get(a) or (
                        default_tools_for(src, s) if a in ("order_management", "communication", "resource_management") else {})
                    run_one_tick(a, f"worker-{uuid.uuid4().hex[:6]}", src, tools, s)
                except Exception as exc:  # noqa: BLE001 - keep the kernel alive
                    _log_skip(a, exc)
                    msg = str(exc)
                    if "AGENT_BUDGET_EXHAUSTED" in msg:
                        try:  # persist pause (claim-side write was rolled back)
                            src.set_status(a, "paused", "BUDGET_EXHAUSTED")
                        except Exception:  # noqa: BLE001
                            pass
            if self.stop_after_ticks is not None:
                i += 1
                if i >= self.stop_after_ticks:
                    return
            sleep_for = max(0.05, s.tick_interval_seconds - (time.time() - t0))
            time.sleep(sleep_for)


def _log_skip(agent: str, exc: Exception) -> None:
    msg = str(exc)
    if "AGENT_PAUSED" in msg or "AGENT_BUDGET_EXHAUSTED" in msg:
        print(f"[kernel] skipping {agent}: {msg.splitlines()[0]}")
    else:
        print(f"[kernel] {agent} tick error: {exc}")
