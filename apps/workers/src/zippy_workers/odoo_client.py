"""Odoo 18 CE JSON-RPC client (system of record).

Capability-gated externally: callers must already hold
assert_can_call_external('order_management', 'odoo').
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel


class OdooError(Exception):
    """ Raised for transport or Odoo-side protocol errors."""


class OdooRecord(BaseModel):
    model: str
    method: str                 # create | write | search | search_read ...
    args: list = []
    kwargs: dict = {}


class OdooClient:
    """Thin /jsonrpc wrapper — no ORM, deterministic request shapes."""

    def __init__(self, base_url: str, db: str, username: str,
                 api_key: str, timeout_s: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.db = db
        self.username = username
        self.api_key = api_key
        self._timeout = timeout_s
        self._uid: int | None = None
        self._http = httpx.Client(timeout=timeout_s)

    # ------------------------------------------------------------------ rpc
    def _call(self, service: str, method: str, args: list) -> object:
        body = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": None,
        }
        try:
            resp = self._http.post(f"{self.base_url}/jsonrpc", json=body)
        except httpx.HTTPError as exc:
            raise OdooError(f"transport:{type(exc).__name__}") from exc

        if resp.status_code != 200:
            raise OdooError(f"http_{resp.status_code}")

        data = resp.json()
        if "error" in data:
            raise OdooError(str(data["error"].get("data", {}).get("message",
                                                              data["error"]))[:200])
        return data.get("result")

    def authenticate(self) -> int:
        uid = self._call("common", "login", [self.db, self.username, self.api_key])
        if not isinstance(uid, int):
            raise OdooError("auth_failed")
        self._uid = uid
        return uid

    def execute_kw(self, model: str, method: str,
                   args: list | None = None, kwargs: dict | None = None):
        if self._uid is None:
            self.authenticate()
        return self._call("object", "execute_kw", [
            self.db, self._uid, self.api_key, model, method,
            args or [], kwargs or {},
        ])

    # ------------------------------------------------------- high-level ops
    def find_or_create_partner(self, email: str, name: str) -> int:
        ids = self.execute_kw("res.partner", "search",
                              [[["email", "=", email]]],
                              {"limit": 1})
        if isinstance(ids, list) and ids:
            return int(ids[0])
        new_id = self.execute_kw("res.partner", "create", [{"name": name, "email": email}])
        return int(new_id)

    def create_sale_order(self, partner_id: int, order_number: str,
                          total_amount: float, reference_note: str | None = None) -> int:
        payload = {
            "partner_id": partner_id,
            "client_order_ref": order_number,
            "amount_total_mirror": total_amount,   # mirrored; Odoo recomputes its own totals
        }
        if reference_note:
            payload["note"] = reference_note
        return int(self.execute_kw("sale.order", "create", [payload]))

    def close(self) -> None:
        self._http.close()
