from decimal import Decimal

import pytest
from test_staged_pipeline import TASK, make_operational

from task_decomposition import (
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
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION


def request(*, baseline=None):
    return TaskDecompositionRequest(
        task=TASK,
        baseline_effort=(
            EffortQuantity(
                value=baseline,
                unit=EffortUnit.EFFORT,
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
