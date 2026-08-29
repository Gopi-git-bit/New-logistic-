"""Zippy Logistics — Persistent Idempotency.

Uses webhook_events table for idempotency key storage.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

import httpx


class IdempotencyStore:
    """Persistent idempotency store using Supabase."""

    def __init__(self, supabase_url: str, service_key: str):
        self.base_url = supabase_url.rstrip("/")
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.Client(timeout=10.0)

    def check(self, idempotency_key: str) -> Optional[dict]:
        """Check if idempotency key already exists. Returns existing result or None."""
        try:
            resp = self._http.get(
                f"{self.base_url}/rest/v1/webhook_events",
                params={
                    "idempotency_key": f"eq.{idempotency_key}",
                    "select": "id,event_type,payload,created_at",
                },
                headers=self.headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data[0]
        except Exception:
            pass
        return None

    def store(
        self,
        idempotency_key: str,
        provider: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> str:
        """Store an idempotency key. Returns the record ID."""
        try:
            resp = self._http.post(
                f"{self.base_url}/rest/v1/webhook_events",
                json={
                    "provider": provider,
                    "event_type": event_type,
                    "payload": payload,
                    "idempotency_key": idempotency_key,
                },
                headers={**self.headers, "Prefer": "return=representation"},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                if data and len(data) > 0:
                    return str(data[0].get("id", ""))
        except Exception:
            pass
        return ""

    def close(self) -> None:
        self._http.close()
