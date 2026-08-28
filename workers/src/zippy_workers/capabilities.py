"""Capability-based agent permissions (PRD §15 matrix).

Single source of truth enforced by `enforce_capability`; callers must consult
it before ANY external call, financial action, or cross-domain write.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class UnauthorizedCapability(Exception):
    """Raised when an agent attempts an action outside its matrix row."""


@dataclass(frozen=True)
class Capability:
    read: frozenset[str]
    write: frozenset[str]
    external: frozenset[str]          # e.g. {"mapbox", "razorpay", "odoo"}
    financial: bool = False           # may move money / alter ledgers
    forbidden: tuple[str, ...] = field(default_factory=tuple)  # hard denials


_MATRIX: dict[str, Capability] = {
    "customer_service": Capability(
        read=frozenset({"orders", "users", "notifications"}),
        write=frozenset({"notifications", "messages"}),
        external=frozenset(),
        forbidden=("admin_actions", "payments_write"),
    ),
    "order_management": Capability(
        read=frozenset({"orders", "vehicles", "drivers", "companies", "pricing"}),
        write=frozenset({"orders", "order_events", "quotes"}),
        external=frozenset({"mapbox", "odoo"}),
        forbidden=("payments_capture",),
    ),
    "transportation": Capability(
        read=frozenset({"orders", "vehicles", "telemetry", "routes"}),
        write=frozenset({"telemetry", "tracking", "alerts_route"}),
        external=frozenset({"mapbox"}),
        forbidden=("pricing_write", "payments_any"),
    ),
    "resource_management": Capability(
        read=frozenset({"vehicles", "drivers", "companies", "orders"}),
        write=frozenset({"vehicle_status", "driver_status", "assignments"}),
        external=frozenset({"odoo"}),
        forbidden=("payments_any",),
    ),
    "payment_settlement": Capability(
        read=frozenset({"orders", "payments", "transactions", "settlements"}),
        write=frozenset({"payments", "transactions", "settlements"}),
        external=frozenset({"razorpay", "stripe"}),
        financial=True,
        forbidden=("order_state_machine_direct",),  # must go through transition_order
    ),
    "platform_administration": Capability(
        read=frozenset({"*"}),                      # oversight reads everything
        write=frozenset({"admin_actions", "agent_registry", "user_flags"}),
        external=frozenset(),
        forbidden=("financial_self_approval",),     # cannot move money unilaterally
    ),
    "communication": Capability(
        read=frozenset({"notifications", "messages", "templates", "orders"}),
        write=frozenset({"notification_log", "notification_queue", "webhook_events",
                         "order_documents"}),
        external=frozenset({"sms", "email", "push"}),
        forbidden=("orders_state_machine_write", "payments_any"),
    ),
}


def has_capability(agent: str, scope: str, domain: str) -> bool:
    """True when `agent` holds `scope` ('read'|'write') on `domain`."""
    cap = _MATRIX.get(agent)
    if cap is None:
        return False
    if domain in cap.forbidden:
        return False
    pool = cap.read if scope == "read" else cap.write
    return "*" in pool or domain in pool


def assert_can_call_external(agent: str, service: str) -> None:
    """External API calls are explicit-only; never implicit via wildcard."""
    cap = _MATRIX.get(agent)
    if cap is None or service not in cap.external:
        raise UnauthorizedCapability(f"{agent} -> external:{service}")


def assert_financial(agent: str) -> None:
    cap = _MATRIX.get(agent)
    if cap is None or not cap.financial or "*" in cap.forbidden:
        raise UnauthorizedCapability(f"{agent} -> financial")


def is_forbidden(agent: str, action: str) -> bool:
    cap = _MATRIX.get(agent)
    return cap is not None and action in cap.forbidden
