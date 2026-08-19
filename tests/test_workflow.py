from datetime import datetime, timezone

from oncall_agent.mcp_client import (
    InMemoryToolTransport,
    MCPToolClient,
    PermanentToolError,
    RetryPolicy,
)
from oncall_agent.models import AlertEvent
from oncall_agent.workflow import build_workflow


def tool_result(source, payload):
    return {
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def high_cpu_alert():
    return AlertEvent(
        alert_id="alert-001",
        service="checkout-api",
        alert_type="high_cpu",
        severity="critical",
        message="CPU utilization above 90% for five minutes",
    )


async def test_workflow_generates_evidence_based_report():
    transport = InMemoryToolTransport(
        {
            "query_cpu_metrics": [
                tool_result("mock://cpu", {"utilization": 0.93})
            ],
            "query_logs": [
                tool_result(
                    "mock://logs",
                    {"entries": [{"message": "payment timeout after 3000ms"}]},
                )
            ],
        }
    )
    graph = build_workflow(
        MCPToolClient(transport, RetryPolicy(base_delay_seconds=0))
    )

    state = await graph.ainvoke({"alert": high_cpu_alert()})

    assert state["report"].needs_human is False
    assert state["report"].confidence == 0.88
    assert "timeouts" in state["report"].root_cause
    assert len(state["evidence"]) == 2


async def test_replanner_adds_independent_signal():
    transport = InMemoryToolTransport(
        {
            "query_cpu_metrics": [
                tool_result("mock://cpu", {"utilization": 0.93})
            ],
            "query_logs": [PermanentToolError("log service unavailable")],
            "query_memory_metrics": [
                tool_result("mock://memory", {"utilization": 0.66})
            ],
        }
    )
    graph = build_workflow(
        MCPToolClient(transport, RetryPolicy(base_delay_seconds=0)),
        max_rounds=2,
    )

    state = await graph.ainvoke({"alert": high_cpu_alert()})

    assert [name for name, _ in transport.calls] == [
        "query_cpu_metrics",
        "query_logs",
        "query_memory_metrics",
    ]
    assert sum(item.success for item in state["evidence"]) == 2
    assert state["rounds"] == 2
    assert state["report"].needs_human is False


async def test_round_limit_degrades_to_human_intervention():
    transport = InMemoryToolTransport(
        {
            "query_cpu_metrics": [PermanentToolError("metrics unavailable")],
            "query_logs": [PermanentToolError("logs unavailable")],
        }
    )
    graph = build_workflow(
        MCPToolClient(transport, RetryPolicy(base_delay_seconds=0)),
        max_rounds=1,
    )

    state = await graph.ainvoke({"alert": high_cpu_alert()})

    assert state["rounds"] == 1
    assert state["report"].needs_human is True
    assert state["report"].confidence == 0.35
