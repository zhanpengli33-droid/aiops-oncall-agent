"""FastMCP tools backed by local incident fixtures."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from importlib import resources
from typing import Any

from fastmcp import FastMCP


mcp = FastMCP(name="OnCall Diagnostics")


@lru_cache(maxsize=1)
def _load_incidents() -> dict[str, Any]:
    data_file = resources.files("oncall_agent.data").joinpath(
        "sample_incidents.json"
    )
    with data_file.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _find_service(service: str) -> dict[str, Any]:
    for incident in _load_incidents()["incidents"]:
        if incident["service"] == service:
            return incident
    raise ValueError(f"unknown service: {service}")


def _result(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def _validate_minutes(minutes: int) -> None:
    if not 1 <= minutes <= 120:
        raise ValueError("minutes must be between 1 and 120")


@mcp.tool
def query_logs(service: str, minutes: int = 15, keyword: str | None = None) -> dict:
    """Query recent mock log entries for a service."""
    _validate_minutes(minutes)
    incident = _find_service(service)
    entries = incident["logs"]
    if keyword:
        keyword_lower = keyword.lower()
        entries = [
            entry for entry in entries if keyword_lower in entry["message"].lower()
        ]
    return _result(
        "mock://cls/logs",
        {"service": service, "minutes": minutes, "entries": entries},
    )


@mcp.tool
def query_cpu_metrics(service: str, window_minutes: int = 15) -> dict:
    """Query the latest mock CPU utilization for a service."""
    _validate_minutes(window_minutes)
    incident = _find_service(service)
    return _result(
        "mock://monitor/cpu",
        {
            "service": service,
            "window_minutes": window_minutes,
            "utilization": incident["metrics"]["cpu_utilization"],
        },
    )


@mcp.tool
def query_memory_metrics(service: str, window_minutes: int = 15) -> dict:
    """Query the latest mock memory utilization for a service."""
    _validate_minutes(window_minutes)
    incident = _find_service(service)
    return _result(
        "mock://monitor/memory",
        {
            "service": service,
            "window_minutes": window_minutes,
            "utilization": incident["metrics"]["memory_utilization"],
        },
    )


if __name__ == "__main__":
    mcp.run()
