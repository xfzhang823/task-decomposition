from decimal import Decimal

import pytest
from test_staged_pipeline import TASK, make_operational

from task_transmorph import (
    BaselineSubtaskEffortEstimate,
    EffortQuantity,
    EffortUnit,
    ParentOutputContract,
    ProviderProvenance,
    ProviderStage,
    ProviderStageResponse,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    StageValidationError,
    TaskDecompositionRequest,
    TimeBasis,
    decompose_task,
    validate_operational_decomposition,
)
from task_transmorph.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION


def request(*, baseline=None, unit=EffortUnit.EFFORT):
    return TaskDecompositionRequest(
        task=TASK,
        baseline_effort=(
            EffortQuantity(
                value=baseline,
                unit=unit,
                time_basis=TimeBasis.PER_OPERATION,
            )
            if baseline is not None
            else None
        ),
    )


class BaselineProvider:
    provider_id = "baseline-provider"

    def __init__(self, operational):
        self.operational = operational

    def generate_operational_decomposition(self, request):
        return ProviderStageResponse(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            payload=self.operational,
            provenance=ProviderProvenance(
                provider_id=self.provider_id,
                stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            ),
        )

    def evaluate(self, request):
        return SemanticEvaluation(
            decision=SemanticEvaluationDecision.ACCEPT,
            rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
        )


def bottom_up_operational(values=("1", "30", "0.5")):
    units = (EffortUnit.HOURS, EffortUnit.MINUTES, EffortUnit.HOURS)
    operational = make_operational()
    estimates = tuple(
        BaselineSubtaskEffortEstimate(
            subtask_id=subtask.subtask_id,
            expected_occurrences_per_parent_output=1,
            active_effort_per_occurrence=EffortQuantity(
                value=value, unit=units[index], time_basis=TimeBasis.PER_OPERATION
            ),
            rationale="Planning estimate for one parent output.",
            assumptions=("Model-generated planning assumption.",),
        )
        for index, (subtask, value) in enumerate(
            zip(operational.operational_subtasks, values)
        )
    )
    return operational.model_copy(update={"baseline_effort_estimates": estimates})


def occurrence_based_operational(*, conflicting_weights=False):
    operational = make_operational()
    estimates = tuple(
        BaselineSubtaskEffortEstimate(
            subtask_id=subtask.subtask_id,
            expected_occurrences_per_parent_output=occurrences,
            active_effort_per_occurrence=EffortQuantity(
                value=effort, unit=EffortUnit.MINUTES, time_basis=TimeBasis.PER_OPERATION
            ),
            rationale="Planning estimate for one parent output.",
            assumptions=("Model-generated planning assumption.",),
        )
        for subtask, occurrences, effort in zip(
            operational.operational_subtasks, (1, "0.25", 3), (10, 20, 5)
        )
    )
    updates = {"baseline_effort_estimates": estimates}
    if conflicting_weights:
        updates["operational_subtasks"] = tuple(
            subtask.model_copy(update={"relative_effort_weight": weight})
            for subtask, weight in zip(
                operational.operational_subtasks, ("0.90", "0.05", "0.05")
            )
        )
    return operational.model_copy(update=updates)


def test_bottom_up_estimates_calculate_total_and_derive_relative_weights():
    result = decompose_task(request(), BaselineProvider(bottom_up_operational()))

    assert result.parent_output_contract.source == "provider_inferred"
    assert (
        result.baseline_effort_estimation.total_effort_per_parent_output.value
        == Decimal(2)
    )
    assert [row.weight_ratio for row in result.baseline_effort_allocations] == [
        Decimal("0.5"),
        Decimal("0.25"),
        Decimal("0.25"),
    ]


def test_baseline_occurrences_are_multiplied_once_per_parent_output():
    result = decompose_task(
        request(), BaselineProvider(occurrence_based_operational())
    )

    assert [
        estimate.expected_effort_per_parent_output.value
        for estimate in result.baseline_effort_estimation.estimates
    ] == [Decimal(10), Decimal(5), Decimal(15)]
    assert (
        result.baseline_effort_estimation.total_effort_per_parent_output.value
        == Decimal(30)
    )
    assert [row.weight_ratio for row in result.baseline_effort_allocations] == [
        Decimal(1) / Decimal(3),
        Decimal(1) / Decimal(6),
        Decimal(1) / Decimal(2),
    ]


def test_supplied_parent_contract_is_preserved():
    contract = ParentOutputContract(
        output_unit="One claim triaged and routed",
        completion_boundary="Claim handed to the appropriate claims team",
        scope_exclusions=("Final coverage decisions",),
        source="supplied",
    )
    result = decompose_task(
        request().model_copy(update={"parent_output_contract": contract}),
        BaselineProvider(bottom_up_operational()),
    )
    assert result.parent_output_contract == contract


def test_zero_bottom_up_effort_does_not_fabricate_weights():
    result = decompose_task(
        request(), BaselineProvider(bottom_up_operational(values=(0, 0, 0)))
    )
    assert result.baseline_effort_estimation.total_effort_per_parent_output.value == 0
    assert result.baseline_effort_allocations == ()


def test_missing_bottom_up_estimates_are_rejected():
    operational = bottom_up_operational().model_copy(
        update={"baseline_effort_estimates": ()}
    )

    with pytest.raises(
        StageValidationError,
        match="canonical operational decomposition requires bottom-up baseline effort estimates",
    ):
        validate_operational_decomposition(operational)


def test_bottom_up_products_override_provider_relative_weights():
    base = bottom_up_operational()
    operational = base.model_copy(
        update={
            "operational_subtasks": tuple(
                subtask.model_copy(
                    update={"relative_effort_weight": weight}
                )
                for subtask, weight in zip(
                    base.operational_subtasks, ("0.90", "0.05", "0.05")
                )
            )
        }
    )

    result = decompose_task(request(), BaselineProvider(operational))

    assert [row.weight_ratio for row in result.baseline_effort_allocations] == [
        Decimal("0.5"),
        Decimal("0.25"),
        Decimal("0.25"),
    ]


def test_public_absolute_allocation_uses_bottom_up_products():
    result = decompose_task(
        request(baseline=120, unit=EffortUnit.MINUTES),
        BaselineProvider(occurrence_based_operational(conflicting_weights=True)),
    )

    allocations = result.baseline_effort_allocations
    assert [row.effort.value for row in allocations] == [
        Decimal(40),
        Decimal(20),
        Decimal(60),
    ]
    assert sum(row.effort.value for row in allocations) == Decimal(120)
    assert [row.weight_ratio for row in allocations] == [
        Decimal(1) / Decimal(3),
        Decimal(1) / Decimal(6),
        Decimal(1) / Decimal(2),
    ]
    assert all(row.effort.unit is EffortUnit.MINUTES for row in allocations)
    assert all(
        row.effort.time_basis is TimeBasis.PER_OPERATION for row in allocations
    )


def test_invalid_baseline_coverage_is_rejected():
    operational = bottom_up_operational()
    estimates = operational.baseline_effort_estimates
    with pytest.raises(StageValidationError, match="missing baseline effort"):
        validate_operational_decomposition(
            operational.model_copy(update={"baseline_effort_estimates": estimates[:-1]})
        )


def test_inconsistent_provider_product_is_rejected():
    operational = bottom_up_operational()
    bad = operational.baseline_effort_estimates[0].model_copy(
        update={
            "expected_effort_per_parent_output": EffortQuantity(
                value=99, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
            )
        }
    )
    with pytest.raises(StageValidationError, match="does not equal"):
        validate_operational_decomposition(
            operational.model_copy(
                update={
                    "baseline_effort_estimates": (
                        bad,
                        *operational.baseline_effort_estimates[1:],
                    )
                }
            )
        )
