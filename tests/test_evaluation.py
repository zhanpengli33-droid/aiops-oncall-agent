import pytest

from oncall_agent.evaluation import EvaluationSummary, success_rate


def test_resume_metric_rates_are_consistent():
    rates = EvaluationSummary().rates()

    assert rates["task_completion_rate"] == pytest.approx(0.85)
    assert rates["tool_success_rate_without_retry"] == pytest.approx(0.90)
    assert rates["tool_success_rate_with_retry"] == pytest.approx(146 / 150)


@pytest.mark.parametrize(
    ("successes", "total"),
    [(-1, 10), (11, 10), (0, 0)],
)
def test_invalid_metric_inputs_are_rejected(successes, total):
    with pytest.raises(ValueError):
        success_rate(successes, total)
