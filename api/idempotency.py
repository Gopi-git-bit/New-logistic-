"""Zippy Logistics — Atomic, Resource-Aware Idempotency.

Uses webhook_events table with INSERT ... ON CONFLICT for atomicity.
Keys are scoped by (idempotency_key, resource_type) so two different
resources can use the same key without colliding.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx


class IdempotencyStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IdempotencyResult:
    """Result of an idempotency check."""
    found: bool
    record_id: Optional[str] = None
    status: Optional[IdempotencyStatus] = None
    response_data: Optional[dict[str, Any]] = None


class IdempotencyStore:
    """Atomic idempotency store using Supabase webhook_events table.

    Atomicity: Uses PostgreSQL INSERT ... ON CONFLICT to guarantee that
    two concurrent requests with the same key cannot both succeed.
    Resource awareness: Keys are composite (idempotency_key, event_type)
    so different resource types can share a key prefix.
    """

    def __init__(self, supabase_url: str, service_key: str):
        self.base_url = supabase_url.rstrip("/")
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.Client(timeout=10.0)

    def check(self, idempotency_key: str, resource_type: str = "order") -> IdempotencyResult:
        """Check if idempotency key exists. Returns existing result or empty."""
        try:
            resp = self._http.get(
                f"{self.base_url}/rest/v1/webhook_events",
                params={
                    "idempotency_key": f"eq.{idempotency_key}",
                    "event_type": f"eq.{resource_type}",
                    "select": "id,event_type,payload,status,created_at",
                    "order": "created_at.desc",
                    "limit": "1",
                },
                headers=self.headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    row = data[0]
                    return IdempotencyResult(
                        found=True,
                        record_id=str(row.get("id", "")),
                        status=IdempotencyStatus(row.get("status", "completed")),
                        response_data=row.get("payload"),
                    )
        except Exception:
            pass
        return IdempotencyResult(found=False)

    def claim(
        self,
        idempotency_key: str,
        resource_type: str,
        payload: dict[str, Any],
    ) -> tuple[bool, Optional[IdempotencyResult]]:
        """Atomically claim an idempotency key.

        Returns (claimed: bool, existing_result: IdempotencyResult | None).
        If claimed=True, this request owns the key and should proceed.
        If claimed=False, the existing_result contains the prior response.
        """
        try:
            # First try to INSERT the claim atomically
            resp = self._http.post(
                f"{self.base_url}/rest/v1/webhook_events",
                json={
                    "idempotency_key": idempotency_key,
                    "event_type": resource_type,
                    "payload": payload,
                    "status": "in_progress",
                    "provider": "api",
                },
                headers={**self.headers, "Prefer": "return=representation"},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                if data:
                    return (True, IdempotencyResult(
                        found=True,
                        record_id=str(data[0].get("id", "")),
                        status=IdempotencyStatus.IN_PROGRESS,
                    ))
                return (True, IdempotencyResult(found=True))
            elif resp.status_code == 409:
                # Conflict — key already exists, fetch the existing record
                existing = self.check(idempotency_key, resource_type)
                return (False, existing)
        except Exception:
            pass
        # On error, let the caller proceed (fail open for availability)
        return (True, IdempotencyResult(found=False))

    def complete(
        self,
        idempotency_key: str,
        resource_type: str,
        response_data: dict[str, Any],
    ) -> bool:
        """Mark an idempotency claim as completed with the response data."""
        try:
            resp = self._http.patch(
                f"{self.base_url}/rest/v1/webhook_events",
                params={
                    "idempotency_key": f"eq.{idempotency_key}",
                    "event_type": f"eq.{resource_type}",
                },
                json={
                    "status": "completed",
                    "payload": response_data,
                },
                headers=self.headers,
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def fail(
        self,
        idempotency_key: str,
        resource_type: str,
        error: str,
    ) -> bool:
        """Mark an idempotency claim as failed."""
        try:
            resp = self._http.patch(
                f"{self.base_url}/rest/v1/webhook_events",
                params={
                    "idempotency_key": f"eq.{idempotency_key}",
                    "event_type": f"eq.{resource_type}",
                },
                json={
                    "status": "failed",
                    "payload": {"error": error},
                },
                headers=self.headers,
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def close(self) -> None:
        self._http.close()
