import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "benchmarks"))

import replay_transformations
from replay_transformations import (
    ARTIFACTS,
    TASK_CASES,
    build_evaluation_request,
    offline_case,
)


def test_all_cached_transformations_construct_current_evaluator_requests():
    for case_key in ARTIFACTS:
        request = build_evaluation_request(case_key)

        assert request.rubric_version == "1.1"
        assert request.task_decomposition.operational_decomposition.operational_subtasks
        assert request.accounting.w0 == 1
        assert request.accounting.w1 >= 0
        expected = TASK_CASES[case_key]
        assert request.task.task_name == expected["task_name"]
        assert request.task.task_description == expected["task_description"]
        assert request.transformation_context == {
            "domain": expected["domain"],
            "operating_model": expected["operating_model"],
        }
        assert request.agentic_task_synthesis is not None
        assert request.human_agent_activity_modeling is not None
        assert request.activity_effort_estimation is not None


def test_offline_replay_is_diagnostic_only_and_preserves_cached_accounting():
    reports = {case_key: offline_case(case_key) for case_key in ARTIFACTS}

    assert set(reports) == set(ARTIFACTS)
    assert all(report["status"] == "validated" for report in reports.values())
    assert all("task_definition_differences" in report for report in reports.values())
    assert all(report["semantic_decision"] is None for report in reports.values())
    assert all(report["findings"] == [] for report in reports.values())
    assert all(report["token_usage"] is None for report in reports.values())
    assert all(report["cost"] is None for report in reports.values())


def test_live_replay_reports_one_case_failure_and_continues(monkeypatch, capsys):
    monkeypatch.setenv("RUN_SEMANTIC_BENCHMARKS", "1")
    monkeypatch.setattr(replay_transformations, "_provider", lambda name: object())

    def fake_live_case(case_key, provider):
        if case_key == "production_scheduling":
            return {"case_key": case_key, "status": "evaluated"}
        raise RuntimeError("invalid evaluator output")

    monkeypatch.setattr(
        replay_transformations,
        "live_case",
        fake_live_case,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "replay_transformations",
            "--live",
            "--case",
            "invoice_review",
            "--case",
            "production_scheduling",
        ],
    )

    assert replay_transformations.main() == 1

    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert reports[0]["status"] == "failed"
    assert reports[0]["error"] == "invalid evaluator output"
    assert reports[1] == {"case_key": "production_scheduling", "status": "evaluated"}
