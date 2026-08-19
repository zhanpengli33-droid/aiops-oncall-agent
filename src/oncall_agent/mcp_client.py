"""Resilient transport boundary for MCP tool calls."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping, Protocol

from pydantic import ValidationError

from .models import ToolEvidence


class ToolCallError(RuntimeError):
    """Base error for a tool call."""


class TransientToolError(ToolCallError):
    """A temporary failure that may succeed when retried."""


class PermanentToolError(ToolCallError):
    """A non-retryable request or data error."""


class InvalidToolResponse(PermanentToolError):
    """The transport returned a response that violates the tool contract."""


class ToolTransport(Protocol):
    """Minimal transport contract used by the workflow."""

    async def call_tool(
        self, name: str, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    timeout_seconds: float = 1.0
    base_delay_seconds: float = 0.05

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds cannot be negative")


class MCPToolClient:
    """Adds timeout, retry and response validation to a tool transport."""

    def __init__(
        self,
        transport: ToolTransport,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._transport = transport
        self._policy = retry_policy or RetryPolicy()

    async def call_tool(
        self, name: str, arguments: Mapping[str, Any]
    ) -> ToolEvidence:
        last_error: Exception | None = None

        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                raw = await asyncio.wait_for(
                    self._transport.call_tool(name, arguments),
                    timeout=self._policy.timeout_seconds,
                )
                return self._to_evidence(name, raw, attempt)
            except PermanentToolError as exc:
                return self._failed_evidence(name, attempt, exc)
            except (TimeoutError, TransientToolError) as exc:
                last_error = exc
                if attempt < self._policy.max_attempts:
                    delay = self._policy.base_delay_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        assert last_error is not None
        return self._failed_evidence(name, self._policy.max_attempts, last_error)

    @staticmethod
    def _to_evidence(
        name: str, raw: Mapping[str, Any], attempt: int
    ) -> ToolEvidence:
        if not isinstance(raw, Mapping):
            raise InvalidToolResponse("tool response must be a mapping")

        missing = {"source", "timestamp", "payload"} - set(raw)
        if missing:
            raise InvalidToolResponse(
                f"tool response missing fields: {', '.join(sorted(missing))}"
            )

        try:
            return ToolEvidence(
                tool=name,
                success=True,
                source=str(raw["source"]),
                timestamp=raw["timestamp"],
                payload=dict(raw["payload"]),
                attempts=attempt,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise InvalidToolResponse(f"invalid tool response: {exc}") from exc

    @staticmethod
    def _failed_evidence(
        name: str, attempt: int, error: Exception
    ) -> ToolEvidence:
        return ToolEvidence(
            tool=name,
            success=False,
            source=f"tool://{name}",
            timestamp=datetime.now(timezone.utc),
            attempts=attempt,
            error=f"{type(error).__name__}: {error}",
        )


ResponseFactory = Callable[[], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]
ResponseItem = Mapping[str, Any] | Exception | ResponseFactory


class InMemoryToolTransport:
    """Deterministic transport used by tests and local examples."""

    def __init__(self, responses: Mapping[str, list[ResponseItem]]) -> None:
        self._responses = {name: list(items) for name, items in responses.items()}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self, name: str, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.calls.append((name, dict(arguments)))
        queue = self._responses.get(name)
        if not queue:
            raise PermanentToolError(f"no response configured for tool {name}")

        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            item = item()
            if inspect.isawaitable(item):
                item = await item
        return item
