import asyncio
from datetime import datetime, timezone

import pytest

from oncall_agent.mcp_client import (
    InMemoryToolTransport,
    MCPToolClient,
    PermanentToolError,
    RetryPolicy,
    TransientToolError,
)


def tool_result(payload=None):
    return {
        "source": "mock://tool",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {"ok": True},
    }


async def test_transient_error_is_retried():
    transport = InMemoryToolTransport(
        {"query_logs": [TransientToolError("busy"), tool_result()]}
    )
    client = MCPToolClient(
        transport,
        RetryPolicy(max_attempts=3, timeout_seconds=0.1, base_delay_seconds=0),
    )

    result = await client.call_tool("query_logs", {"service": "checkout-api"})

    assert result.success is True
    assert result.attempts == 2
    assert len(transport.calls) == 2


async def test_permanent_error_is_not_retried():
    transport = InMemoryToolTransport(
        {"query_logs": [PermanentToolError("bad request"), tool_result()]}
    )
    client = MCPToolClient(transport, RetryPolicy(base_delay_seconds=0))

    result = await client.call_tool("query_logs", {})

    assert result.success is False
    assert result.attempts == 1
    assert len(transport.calls) == 1


async def test_timeout_is_retried_until_limit():
    class SlowTransport:
        def __init__(self):
            self.calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1
            await asyncio.sleep(0.02)
            return tool_result()

    transport = SlowTransport()
    client = MCPToolClient(
        transport,
        RetryPolicy(
            max_attempts=2,
            timeout_seconds=0.001,
            base_delay_seconds=0,
        ),
    )

    result = await client.call_tool("query_logs", {})

    assert result.success is False
    assert result.attempts == 2
    assert transport.calls == 2
    assert "TimeoutError" in result.error


async def test_missing_response_fields_are_rejected_without_retry():
    transport = InMemoryToolTransport({"query_logs": [{"payload": {}}]})
    client = MCPToolClient(transport, RetryPolicy(base_delay_seconds=0))

    result = await client.call_tool("query_logs", {})

    assert result.success is False
    assert result.attempts == 1
    assert "missing fields" in result.error
