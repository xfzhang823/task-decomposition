import json
from pathlib import Path


def _transformation_renderer_source():
    notebook = json.loads(
        Path("notebooks/task_decomposition_end_to_end.ipynb").read_text()
    )
    return "".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
        and any("def transformation_table" in line for line in cell.get("source", []))
    )


def test_notebook_renders_resolver_added_work_details_and_reconciliation():
    source = _transformation_renderer_source()
    compile(source, "task_decomposition_end_to_end.ipynb", "exec")

    for field in (
        "expected_occurrences_per_parent_output",
        "relative_effort_per_occurrence",
        "reference_effort",
        "reference_occurrences_per_parent_output",
        "reference_effort_per_occurrence",
        "calculated_added_effort_per_parent_output",
    ):
        assert field in source
    assert "added_work_estimate_details" in source
    assert "Added-work calculation details" in source
    assert "Added-work reconciliation" in source


def test_notebook_renders_activity_estimates_and_canonical_summary():
    source = _transformation_renderer_source()
    for field in (
        "activity_effort_estimation",
        "expected_occurrences_per_parent_output",
        "active_effort_per_occurrence",
        "expected_effort_per_parent_output",
        "minutes_per_occurrence",
        "expected_minutes_per_parent_output",
        "calibration_source",
        "calibration_rationale",
        "calibration_provenance",
        "normalized_W0",
        "normalized_W1",
        "net_effort_reduction_ratio",
        "Activity effort by category (reporting projection)",
    ):
        assert field in source
    assert "Not run: activity-based estimates are authoritative" in source
