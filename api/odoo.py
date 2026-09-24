"""Draft-only Odoo 18 adapter (D-26).

Supported JSON-RPC operations only. No ORM magic, no direct SQL, no live
credentials in tests. Prohibited methods (posting, payment registration,
reconciliation, confirmation beyond draft) are refused before any transport
call, and tests assert they are never invoked.
"""

from __future__ import annotations

from typing import Any, Protocol


class OdooProhibitedMethodError(Exception):
    """Raised before any transport call when a prohibited method is requested."""


class OdooTransportError(Exception):
    """Raised for transport or Odoo-side protocol failures."""


class OdooJsonRpcTransport(Protocol):
    """Deterministic transport port; fake implementations in tests."""

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any: ...


# D-26 draft-only allowlist.
_ALLOWED_METHODS: dict[str, frozenset[str]] = {
    "res.partner": frozenset({"search", "create", "read"}),
    "account.move": frozenset({"create", "read"}),
}

# Hard denials checked before the allowlist; message never includes payload data.
_PROHIBITED_METHODS = frozenset(
    {
        "action_post",
        "action_register_payment",
        "action_validate",
        "button_validate",
        "button_draft",
        "action_confirm",
        "action_invoice_paid",
        "write",
        "unlink",
    }
)

_DRAFT_MOVE_TYPES = frozenset({"out_invoice", "in_invoice"})


class OdooDraftAdapter:
    """Partner sync plus draft customer-invoice / draft vendor-bill requests."""

    def __init__(self, transport: OdooJsonRpcTransport) -> None:
        self._transport = transport

    def _execute(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        if method in _PROHIBITED_METHODS:
            raise OdooProhibitedMethodError(f"prohibited method: {model}.{method}")
        if method not in _ALLOWED_METHODS.get(model, frozenset()):
            raise OdooProhibitedMethodError(f"method not allowlisted: {model}.{method}")
        try:
            return self._transport.execute_kw(model, method, args, kwargs)
        except OdooProhibitedMethodError:
            raise
        except Exception as exc:
            raise OdooTransportError(f"odoo_transport:{type(exc).__name__}") from exc

    def find_or_create_partner(self, email: str, name: str) -> int:
        ids = self._execute(
            "res.partner", "search", [[["email", "=", email]]], {"limit": 1}
        )
        if isinstance(ids, list) and ids:
            return int(ids[0])
        return int(self._execute("res.partner", "create", [{"name": name, "email": email}], {}))

    def create_draft_customer_invoice(
        self, partner_id: int, reference: str, amount: str, currency: str
    ) -> int:
        return self._create_draft_move(partner_id, reference, amount, currency, "out_invoice")

    def create_draft_vendor_bill(
        self, partner_id: int, reference: str, amount: str, currency: str
    ) -> int:
        return self._create_draft_move(partner_id, reference, amount, currency, "in_invoice")

    def _create_draft_move(
        self, partner_id: int, reference: str, amount: str, currency: str, move_type: str
    ) -> int:
        if move_type not in _DRAFT_MOVE_TYPES:
            raise OdooProhibitedMethodError(f"move type not draft-allowed: {move_type}")
        payload = {
            "move_type": move_type,
            "partner_id": partner_id,
            "ref": reference,
            "zippy_mirror_amount": amount,
            "zippy_mirror_currency": currency,
        }
        return int(self._execute("account.move", "create", [payload], {}))
