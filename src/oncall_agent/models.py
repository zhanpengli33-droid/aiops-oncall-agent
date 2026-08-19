"""Domain models shared by the workflow and MCP boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict


ToolName = Literal["query_logs", "query_cpu_metrics", "query_memory_metrics"]


class AlertEvent(BaseModel):
    """Normalized alert received by the diagnosis workflow."""

    model_config = ConfigDict(extra="forbid")

    alert_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    alert_type: str = Field(min_length=1)
    severity: Literal["warning", "critical"] = "warning"
    message: str = Field(min_length=1)
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DiagnosticStep(BaseModel):
    """One explicit tool action in a diagnosis plan."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    tool: ToolName
    arguments: dict[str, Any]
    rationale: str


class ToolEvidence(BaseModel):
    """Normalized evidence returned from any MCP tool call."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    success: bool
    source: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    attempts: int = Field(ge=1)
    error: str | None = None


class DiagnosisReport(BaseModel):
    """Final output produced by the workflow."""

    model_config = ConfigDict(extra="forbid")

    alert_id: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_summary: list[str]
    recommendations: list[str]
    needs_human: bool = False


class OnCallState(TypedDict, total=False):
    """LangGraph state for one diagnosis run."""

    alert: AlertEvent
    plan: list[DiagnosticStep]
    cursor: int
    evidence: list[ToolEvidence]
    rounds: int
    needs_replan: bool
    report: DiagnosisReport
