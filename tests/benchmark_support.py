"""Credential-free semantic benchmark contracts and review helpers."""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from task_decomposition import (
    TaskDecomposition,
    TransformationDecompositionResult,
    classify_effect,
    validate_stage_chain,
)


BENCHMARK_PATH = Path(__file__).parents[1] / "benchmarks" / "processes.json"
TOLERANCE = Decimal("0.000000001")


class ExpectedRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min: Decimal = Field(ge=0)
    max: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "ExpectedRange":
        if self.min > self.max:
            raise ValueError("expected range min must not exceed max")
        return self


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    process_name: str = Field(min_length=1)
    process_description: str = Field(min_length=1)
    task_context: dict[str, str] = Field(min_length=1)
    transformation_context: dict[str, str] = Field(min_length=1)
    expected_task_count: ExpectedRange
    must_contain: tuple[str, ...] = Field(min_length=1)
    normally_retain: tuple[str, ...] = ()
    expected_net_substitution_range: ExpectedRange


@dataclass(frozen=True)
class HardValidityReport:
    valid: bool
    errors: tuple[str, ...] = ()


def load_benchmark_cases() -> tuple[BenchmarkCase, ...]:
    raw = json.loads(BENCHMARK_PATH.read_text())
    cases = tuple(BenchmarkCase.model_validate(item) for item in raw)
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("benchmark case IDs must be unique")
    return cases


def check_hard_validity(
    result: TransformationDecompositionResult,
) -> HardValidityReport:
    errors: list[str] = []
    task: TaskDecomposition = result.task_decomposition
    subtasks = task.operational_decomposition.operational_subtasks
    subtask_ids = {item.subtask_id for item in subtasks}
    allocations = task.baseline_effort_allocations
    allocation_ids = {item.subtask_id for item in allocations}

    if allocations and allocation_ids != subtask_ids:
        errors.append(
            "baseline allocations do not cover exactly the operational subtasks"
        )
    if allocations and all(item.weight_ratio is not None for item in allocations):
        total = sum((item.weight_ratio for item in allocations), Decimal("0"))
        if abs(total - Decimal("1")) > TOLERANCE:
            errors.append("baseline weight ratios do not sum to one")
    if allocations and all(item.effort is not None for item in allocations):
        if sum((item.effort.value for item in allocations), Decimal("0")) <= 0:
            errors.append("baseline effort allocation is not positive")

    try:
        validate_stage_chain(
            task.operational_decomposition,
            result.retain_remove_classification,
            result.added_work_classification,
        )
    except Exception as exc:
        errors.append(f"stage validation failed: {exc}")

    accounting = result.accounting
    if accounting.w0 <= 0:
        errors.append("accounting W0 is not positive")
    if accounting.w1 < 0:
        errors.append("accounting W1 is negative")
    if accounting.net_substitution_ratio != 1 - accounting.net_remaining_work_ratio:
        errors.append("net substitution identity failed")
    if (
        accounting.w1 > 0
        and accounting.net_augmentation_multiplier
        != 1 / accounting.net_remaining_work_ratio
    ):
        errors.append("augmentation identity failed")
    if accounting.effect is not classify_effect(accounting.w0, accounting.w1):
        errors.append("effect classification does not match W0/W1")
    return HardValidityReport(valid=not errors, errors=tuple(errors))


def review_task_semantics(
    case: BenchmarkCase, task: TaskDecomposition
) -> dict[str, Any]:
    subtasks = task.operational_decomposition.operational_subtasks
    descriptions = " ".join(
        f"{item.subtask_name} {item.description or ''}" for item in subtasks
    ).lower()
    missing = tuple(
        term for term in case.must_contain if term.lower() not in descriptions
    )
    normalized_names = [item.subtask_name.strip().lower() for item in subtasks]
    duplicate_names = tuple(
        name
        for name in sorted(set(normalized_names))
        if normalized_names.count(name) > 1
    )
    weights = tuple(
        item.weight_ratio
        for item in task.baseline_effort_allocations
        if item.weight_ratio is not None
    )
    return {
        "task_count": len(subtasks),
        "task_count_in_expected_range": case.expected_task_count.min
        <= len(subtasks)
        <= case.expected_task_count.max,
        "missing_expected_work_terms": missing,
        "duplicate_task_names": duplicate_names,
        "weight_total": sum(weights, Decimal("0")) if weights else None,
        "review_required": bool(missing or duplicate_names),
    }


def review_transformation_semantics(
    case: BenchmarkCase,
    result: TransformationDecompositionResult,
) -> dict[str, Any]:
    classifications = result.retain_remove_classification.classified_subtasks
    retained_text = " ".join(
        f"{item.subtask_name or ''} {item.rationale or ''}"
        for item in classifications
        if item.classification.value == "retain"
    ).lower()
    missing_retain_signals = tuple(
        term for term in case.normally_retain if term.lower() not in retained_text
    )
    net_substitution = result.accounting.net_substitution_ratio
    expected_range = case.expected_net_substitution_range
    return {
        "retained_count": sum(
            item.classification.value == "retain" for item in classifications
        ),
        "removed_count": sum(
            item.classification.value == "remove" for item in classifications
        ),
        "added_work_count": len(result.added_work_classification.added_work_rows),
        "missing_retain_signals": missing_retain_signals,
        "net_substitution": net_substitution,
        "net_substitution_in_broad_expected_range": expected_range.min
        <= net_substitution
        <= expected_range.max,
        "review_required": bool(missing_retain_signals),
    }


def render_review_artifact(
    case: BenchmarkCase,
    result: TransformationDecompositionResult,
) -> str:
    allocations = {
        item.subtask_id: item
        for item in result.task_decomposition.baseline_effort_allocations
    }
    operational = result.task_decomposition.operational_decomposition
    classifications = {
        item.subtask_id: item
        for item in result.retain_remove_classification.classified_subtasks
    }
    lines = [
        f"# {case.process_name}",
        "",
        f"Process: {case.process_description}",
        f"Transformation: {next(iter(case.transformation_context.values()))}",
        "",
        "## TASK DECOMPOSITION",
        "",
        "| Task | Description | Effort weight | Dependencies |",
        "| --- | --- | ---: | --- |",
    ]
    for item in operational.operational_subtasks:
        allocation = allocations.get(item.subtask_id)
        weight = ""
        if allocation is not None:
            weight = str(allocation.weight_ratio or allocation.effort.value)
        lines.append(
            f"| {item.subtask_name} | {item.description or ''} | {weight} | {', '.join(item.depends_on) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## TRANSFORMATION",
            "",
            "| Task | Classification | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for item in operational.operational_subtasks:
        classification = classifications[item.subtask_id]
        lines.append(
            f"| {item.subtask_name} | {classification.classification.value.upper()} | {classification.rationale or ''} |"
        )
    lines.extend(
        [
            "",
            "## ADDED HUMAN WORK",
            "",
            "| Category | Description | Effort |",
            "| --- | --- | ---: |",
        ]
    )
    for item in result.added_work_classification.added_work_rows:
        amount = "" if item.amount is None else str(item.amount.value)
        lines.append(
            f"| {item.category.value} | {item.description or item.workload_name} | {amount} |"
        )
    accounting = result.accounting
    lines.extend(
        [
            "",
            "## RESULT",
            "",
            f"Gross removed ratio: {accounting.gross_removed_work_ratio}",
            f"Added human work ratio: {accounting.added_human_work_ratio}",
            f"Net remaining ratio: {accounting.net_remaining_work_ratio}",
            f"Net substitution ratio: {accounting.net_substitution_ratio}",
            f"Augmentation multiplier: {accounting.net_augmentation_multiplier}",
            f"Effect: {accounting.effect.value.upper()}",
        ]
    )
    return "\n".join(lines) + "\n"
