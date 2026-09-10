from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from api.services.composio import (
    ComposioGateway,
    IntegrationError,
    TinyFishAdapter,
    TinyFishTask,
)


def test_tinyfish_task_rejects_unbounded_limits() -> None:
    with pytest.raises(ValidationError):
        TinyFishTask(
            task_type="read_only",
            target_domain="example.com",
            idempotency_key="0123456789abcdef",
            max_steps=1000,
        )


def test_gateway_fails_closed_for_unlisted_tool() -> None:
    async def run() -> None:
        gateway = ComposioGateway(
            "https://mcp.invalid",
            "test-key",
            allowed_tools=frozenset({"tinyfish.start_task"}),
        )
        try:
            with pytest.raises(IntegrationError, match="not allowlisted"):
                await gateway.call_tool(
                    "arbitrary.http",
                    {},
                    "00000000-0000-0000-0000-000000000000",
                )
        finally:
            await gateway.close()

    asyncio.run(run())


def test_adapter_uses_bounded_task_schema() -> None:
    task = TinyFishTask(
        task_type="read_only",
        target_domain="example.com",
        idempotency_key="0123456789abcdef",
    )
    assert task.timeout_seconds == 120
    assert task.max_steps == 30
    assert task.evidence_required is True
