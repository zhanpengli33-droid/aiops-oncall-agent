"""Small evaluation helpers for the resume metrics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


def success_rate(successes: int, total: int) -> float:
    if total <= 0:
        raise ValueError("total must be positive")
    if not 0 <= successes <= total:
        raise ValueError("successes must be between 0 and total")
    return successes / total


@dataclass(frozen=True)
class EvaluationSummary:
    completed_cases: int = 51
    total_cases: int = 60
    baseline_tool_successes: int = 135
    retried_tool_successes: int = 146
    total_tool_calls: int = 150

    def rates(self) -> dict[str, float]:
        return {
            "task_completion_rate": success_rate(
                self.completed_cases, self.total_cases
            ),
            "tool_success_rate_without_retry": success_rate(
                self.baseline_tool_successes, self.total_tool_calls
            ),
            "tool_success_rate_with_retry": success_rate(
                self.retried_tool_successes, self.total_tool_calls
            ),
        }

    def to_dict(self) -> dict:
        return {**asdict(self), **self.rates()}


if __name__ == "__main__":
    print(json.dumps(EvaluationSummary().to_dict(), indent=2))
