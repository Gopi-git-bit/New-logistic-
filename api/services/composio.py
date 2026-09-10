"""Typed Composio MCP gateway and bounded TinyFish tool adapter.

This module intentionally implements the standard MCP JSON-RPC boundary only.
Provider-specific TinyFish endpoints must be added after the official contract
is recorded; do not guess endpoints or payloads.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field


class IntegrationError(RuntimeError):
    """Sanitized external-integration failure."""


class TinyFishTask(BaseModel):
    task_type: str = Field(min_length=1, max_length=100)
    target_domain: str = Field(min_length=1, max_length=253)
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=16, max_length=128)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timeout_seconds: int = Field(default=120, ge=5, le=300)
    max_steps: int = Field(default=30, ge=1, le=100)
    evidence_required: bool = True


@dataclass(frozen=True)
class ToolResult:
    content: list[dict[str, Any]]
    is_error: bool = False
    request_id: Optional[str] = None


class ComposioGateway:
    """Minimal async MCP JSON-RPC client with no arbitrary-tool surface."""

    def __init__(
        self,
        mcp_url: str,
        api_key: str,
        *,
        timeout_s: float = 30.0,
        allowed_tools: frozenset[str] = frozenset(),
    ) -> None:
        if not mcp_url or not api_key:
            raise ValueError("Composio MCP URL and API key are required")
        self._url = mcp_url
        self._allowed_tools = allowed_tools
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_s),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

    async def call_tool(
        self, name: str, arguments: dict[str, Any], correlation_id: str
    ) -> ToolResult:
        if name not in self._allowed_tools:
            raise IntegrationError(f"Tool is not allowlisted: {name}")
        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        try:
            response = await self._http.post(
                self._url,
                json=payload,
                headers={"X-Correlation-ID": correlation_id},
            )
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as exc:
            raise IntegrationError("Composio MCP timed out") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise IntegrationError("Composio MCP request failed") from exc

        if body.get("error"):
            code = body["error"].get("code", "unknown")
            raise IntegrationError(f"Composio MCP returned error code {code}")
        result = body.get("result")
        if not isinstance(result, dict):
            raise IntegrationError("Composio MCP returned an invalid result")
        return ToolResult(
            content=result.get("content", []),
            is_error=bool(result.get("isError", False)),
            request_id=request_id,
        )

    async def health(self) -> bool:
        """Check reachability without executing any external tool."""
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/list",
            "params": {},
        }
        try:
            response = await self._http.post(self._url, json=payload)
            response.raise_for_status()
            body = response.json()
            return not bool(body.get("error"))
        except (httpx.HTTPError, ValueError):
            return False

    async def close(self) -> None:
        await self._http.aclose()


class TinyFishAdapter:
    """Bounded TinyFish capability exposed through an allowlisted MCP tool."""

    def __init__(self, gateway: ComposioGateway, tool_name: str) -> None:
        self._gateway = gateway
        self._tool_name = tool_name

    async def start_task(self, task: TinyFishTask) -> ToolResult:
        return await self._gateway.call_tool(
            self._tool_name,
            {
                "task_type": task.task_type,
                "target": {"domain": task.target_domain},
                "input": task.input,
                "idempotency_key": task.idempotency_key,
                "limits": {
                    "timeout_seconds": task.timeout_seconds,
                    "max_steps": task.max_steps,
                },
                "evidence_required": task.evidence_required,
            },
            task.correlation_id,
        )
