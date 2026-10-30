import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "benchmarks"))

from replay_transformations import (
    ARTIFACTS,
    build_evaluation_request,
    offline_case,
)


def test_all_cached_transformations_construct_current_evaluator_requests():
    for case_key in ARTIFACTS:
        request = build_evaluation_request(case_key)

        assert request.rubric_version == "1.0"
        assert request.task_decomposition.operational_decomposition.operational_subtasks
        assert request.accounting.w0 == 1
        assert request.accounting.w1 >= 0
        assert request.transformation_context == {}
        assert request.agentic_task_synthesis is not None
        assert request.human_agent_activity_modeling is not None
        assert request.activity_effort_estimation is not None


def test_offline_replay_is_diagnostic_only_and_preserves_cached_accounting():
    reports = {case_key: offline_case(case_key) for case_key in ARTIFACTS}

    assert set(reports) == set(ARTIFACTS)
    assert all(report["status"] == "validated" for report in reports.values())
    assert all("missing_source_fields" not in report for report in reports.values())
    assert all(report["semantic_decision"] is None for report in reports.values())
    assert all(report["findings"] == [] for report in reports.values())
    assert all(report["token_usage"] is None for report in reports.values())
    assert all(report["cost"] is None for report in reports.values())
