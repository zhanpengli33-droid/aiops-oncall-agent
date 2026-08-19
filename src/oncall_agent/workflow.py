"""LangGraph Plan-Execute-Replan workflow for incident diagnosis."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from .mcp_client import MCPToolClient
from .models import (
    AlertEvent,
    DiagnosisReport,
    DiagnosticStep,
    OnCallState,
    ToolEvidence,
)


class RuleBasedReasoner:
    """Deterministic reasoning used to keep local tests reproducible."""

    def plan(self, alert: AlertEvent) -> list[DiagnosticStep]:
        common = {"service": alert.service, "window_minutes": 15}
        plans: dict[str, list[DiagnosticStep]] = {
            "high_cpu": [
                DiagnosticStep(
                    step_id="cpu-1",
                    tool="query_cpu_metrics",
                    arguments=common,
                    rationale="Confirm whether CPU remains above the alert threshold.",
                ),
                DiagnosticStep(
                    step_id="logs-1",
                    tool="query_logs",
                    arguments={
                        "service": alert.service,
                        "minutes": 15,
                        "keyword": "timeout",
                    },
                    rationale="Look for timeouts that can explain request buildup.",
                ),
            ],
            "high_memory": [
                DiagnosticStep(
                    step_id="memory-1",
                    tool="query_memory_metrics",
                    arguments=common,
                    rationale="Confirm whether memory remains above the threshold.",
                ),
                DiagnosticStep(
                    step_id="logs-1",
                    tool="query_logs",
                    arguments={
                        "service": alert.service,
                        "minutes": 15,
                        "keyword": "memory",
                    },
                    rationale="Search for allocation or out-of-memory warnings.",
                ),
            ],
            "error_rate": [
                DiagnosticStep(
                    step_id="logs-1",
                    tool="query_logs",
                    arguments={
                        "service": alert.service,
                        "minutes": 15,
                        "keyword": "error",
                    },
                    rationale="Identify the dominant application error signature.",
                ),
                DiagnosticStep(
                    step_id="cpu-1",
                    tool="query_cpu_metrics",
                    arguments=common,
                    rationale="Check whether resource pressure correlates with errors.",
                ),
            ],
        }
        return plans.get(alert.alert_type, plans["error_rate"])

    def next_step(
        self, alert: AlertEvent, evidence: list[ToolEvidence]
    ) -> DiagnosticStep | None:
        called = {item.tool for item in evidence}
        candidates = [
            ("query_logs", {"service": alert.service, "minutes": 30}),
            (
                "query_cpu_metrics",
                {"service": alert.service, "window_minutes": 30},
            ),
            (
                "query_memory_metrics",
                {"service": alert.service, "window_minutes": 30},
            ),
        ]
        for index, (tool, arguments) in enumerate(candidates, start=1):
            if tool not in called:
                return DiagnosticStep(
                    step_id=f"replan-{index}",
                    tool=tool,
                    arguments=arguments,
                    rationale="Collect an independent signal after incomplete evidence.",
                )
        return None

    def finalize(
        self, alert: AlertEvent, evidence: list[ToolEvidence]
    ) -> DiagnosisReport:
        valid = [item for item in evidence if item.success]
        summaries = [self._summarize(item) for item in valid]

        if len(valid) < 2:
            return DiagnosisReport(
                alert_id=alert.alert_id,
                root_cause="Insufficient evidence for a reliable root-cause conclusion.",
                confidence=0.35,
                evidence_summary=summaries,
                recommendations=[
                    "Escalate to the on-call engineer and inspect the original platform data."
                ],
                needs_human=True,
            )

        if alert.alert_type == "high_cpu":
            cpu = self._utilization(valid, "query_cpu_metrics")
            has_timeout = self._logs_contain(valid, "timeout")
            if cpu >= 0.85 and has_timeout:
                return DiagnosisReport(
                    alert_id=alert.alert_id,
                    root_cause="Downstream timeouts caused request buildup and sustained CPU pressure.",
                    confidence=0.88,
                    evidence_summary=summaries,
                    recommendations=[
                        "Check downstream dependency latency and error rate.",
                        "Apply temporary traffic limiting before scaling the service.",
                    ],
                )

        if alert.alert_type == "high_memory":
            memory = self._utilization(valid, "query_memory_metrics")
            if memory >= 0.85:
                return DiagnosisReport(
                    alert_id=alert.alert_id,
                    root_cause="Memory utilization remained above the safe threshold.",
                    confidence=0.82,
                    evidence_summary=summaries,
                    recommendations=[
                        "Capture a heap profile and compare allocation growth.",
                        "Restart one unhealthy instance only after preserving evidence.",
                    ],
                )

        return DiagnosisReport(
            alert_id=alert.alert_id,
            root_cause="The alert correlates with abnormal service logs and resource metrics.",
            confidence=0.68,
            evidence_summary=summaries,
            recommendations=["Review the evidence and validate the suspected dependency."],
        )

    @staticmethod
    def _summarize(evidence: ToolEvidence) -> str:
        return f"{evidence.tool} from {evidence.source} succeeded in {evidence.attempts} attempt(s)"

    @staticmethod
    def _utilization(evidence: list[ToolEvidence], tool: str) -> float:
        for item in evidence:
            if item.tool == tool:
                return float(item.payload.get("utilization", 0.0))
        return 0.0

    @staticmethod
    def _logs_contain(evidence: list[ToolEvidence], keyword: str) -> bool:
        for item in evidence:
            if item.tool != "query_logs":
                continue
            for entry in item.payload.get("entries", []):
                if keyword.lower() in str(entry.get("message", "")).lower():
                    return True
        return False


def build_workflow(
    client: MCPToolClient,
    reasoner: RuleBasedReasoner | None = None,
    max_rounds: int = 2,
):
    """Build and compile the diagnosis graph."""
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")
    reasoner = reasoner or RuleBasedReasoner()

    def planner(state: OnCallState) -> dict:
        return {
            "plan": reasoner.plan(state["alert"]),
            "cursor": 0,
            "evidence": [],
            "rounds": 0,
            "needs_replan": False,
        }

    async def executor(state: OnCallState) -> dict:
        step = state["plan"][state["cursor"]]
        result = await client.call_tool(step.tool, step.arguments)
        return {
            "evidence": [*state.get("evidence", []), result],
            "cursor": state["cursor"] + 1,
        }

    def route_after_executor(state: OnCallState) -> Literal["executor", "replanner"]:
        if state["cursor"] < len(state["plan"]):
            return "executor"
        return "replanner"

    def replanner(state: OnCallState) -> dict:
        rounds = state.get("rounds", 0) + 1
        valid_count = sum(item.success for item in state.get("evidence", []))
        if valid_count >= 2 or rounds >= max_rounds:
            return {"rounds": rounds, "needs_replan": False}

        extra_step = reasoner.next_step(state["alert"], state.get("evidence", []))
        if extra_step is None:
            return {"rounds": rounds, "needs_replan": False}
        return {
            "plan": [*state["plan"], extra_step],
            "rounds": rounds,
            "needs_replan": True,
        }

    def route_after_replanner(
        state: OnCallState,
    ) -> Literal["executor", "finalizer"]:
        return "executor" if state.get("needs_replan", False) else "finalizer"

    def finalizer(state: OnCallState) -> dict:
        return {
            "report": reasoner.finalize(
                state["alert"], state.get("evidence", [])
            )
        }

    builder = StateGraph(OnCallState)
    builder.add_node("planner", planner)
    builder.add_node("executor", executor)
    builder.add_node("replanner", replanner)
    builder.add_node("finalizer", finalizer)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "executor")
    builder.add_conditional_edges("executor", route_after_executor)
    builder.add_conditional_edges("replanner", route_after_replanner)
    builder.add_edge("finalizer", END)
    return builder.compile()
