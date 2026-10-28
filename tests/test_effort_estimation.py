from decimal import Decimal

import pytest
from test_provider_application import FakeProvider, request
from test_staged_pipeline import make_operational

from task_decomposition import (
    BaselineSubtaskEffortEstimate,
    EffortQuantity,
    EffortUnit,
    ParentOutputContract,
    ProviderStage,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    StageValidationError,
    decompose_task,
    validate_operational_decomposition,
)
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION


def weighted_operational():
    operational = make_operational()
    weights = (Decimal(2), Decimal(3), Decimal(5))
    return operational.model_copy(
        update={
            "operational_subtasks": tuple(
                subtask.model_copy(update={"relative_effort_weight": weight})
                for subtask, weight in zip(operational.operational_subtasks, weights)
            )
        }
    )


def bottom_up_operational(values=("1", "30", "0.5"), units=None):
    units = units or (EffortUnit.HOURS, EffortUnit.MINUTES, EffortUnit.HOURS)
    operational = make_operational()
    estimates = tuple(
        BaselineSubtaskEffortEstimate(
            subtask_id=subtask.subtask_id,
            expected_occurrences_per_parent_output=1,
            active_effort_per_occurrence=EffortQuantity(
                value=value,
                unit=units[index],
                time_basis="per_operation",
            ),
            rationale="Planning estimate for one parent output.",
            assumptions=("Model-generated planning assumption.",),
        )
        for index, (subtask, value) in enumerate(
            zip(operational.operational_subtasks, values)
        )
    )
    return operational.model_copy(update={"baseline_effort_estimates": estimates})


def test_estimated_weights_create_shares_without_baseline_effort():
    task_request = request().model_copy(update={"baseline_effort": None})
    result = decompose_task(
        task_request,
        FakeProvider(operational=weighted_operational()),
    )

    allocations = result.baseline_effort_allocations
    assert [item.weight_ratio for item in allocations] == [
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("0.5"),
    ]
    assert sum((item.weight_ratio for item in allocations), Decimal(0)) == Decimal(1)
    assert all(item.allocation_source == "estimated" for item in allocations)
    assert all(item.effort is None for item in allocations)


def test_estimated_weights_allocate_supplied_baseline_effort():
    task_request = request()
    result = decompose_task(
        task_request,
        FakeProvider(operational=weighted_operational()),
    )

    assert [item.effort.value for item in result.baseline_effort_allocations] == [
        Decimal(20),
        Decimal(30),
        Decimal(50),
    ]


def test_measured_parent_baseline_calibrates_normalized_shares_without_changing_them():
    relative = decompose_task(
        request().model_copy(update={"baseline_effort": None}),
        FakeProvider(operational=weighted_operational()),
    )
    absolute = decompose_task(
        request().model_copy(update={"baseline_effort": request().baseline_effort}),
        FakeProvider(operational=weighted_operational()),
    )

    assert [row.weight_ratio for row in relative.baseline_effort_allocations] == [
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("0.5"),
    ]
    assert [
        row.effort.value / absolute.baseline_effort_allocations[0].effort.value
        for row in absolute.baseline_effort_allocations
    ] == [Decimal(1), Decimal("1.5"), Decimal("2.5")]


def test_bottom_up_estimates_are_calculated_and_derive_relative_weights():
    result = decompose_task(
        request().model_copy(update={"baseline_effort": None}),
        FakeProvider(operational=bottom_up_operational()),
    )

    assert result.parent_output_contract.source == "application_inferred"
    assert (
        result.baseline_effort_estimation.total_effort_per_parent_output.value
        == Decimal(2)
    )
    assert (
        result.baseline_effort_estimation.total_effort_per_parent_output.unit
        is EffortUnit.HOURS
    )
    assert [row.weight_ratio for row in result.baseline_effort_allocations] == [
        Decimal("0.5"),
        Decimal("0.25"),
        Decimal("0.25"),
    ]
    assert [
        item.expected_effort_per_parent_output.value
        for item in result.baseline_effort_estimation.estimates
    ] == [Decimal(1), Decimal("0.5"), Decimal("0.5")]


def test_supplied_parent_output_contract_is_preserved():
    contract = ParentOutputContract(
        output_unit="One claim triaged and routed",
        completion_boundary="Claim handed to the appropriate claims team",
        scope_exclusions=("Final coverage decisions",),
        source="supplied",
    )
    result = decompose_task(
        request().model_copy(update={"parent_output_contract": contract}),
        FakeProvider(operational=weighted_operational()),
    )

    assert result.parent_output_contract == contract


def test_zero_bottom_up_effort_is_explicit_without_fabricated_weights():
    result = decompose_task(
        request().model_copy(update={"baseline_effort": None}),
        FakeProvider(operational=bottom_up_operational(values=(0, 0, 0))),
    )

    assert result.baseline_effort_estimation.total_effort_per_parent_output.value == 0
    assert result.baseline_effort_allocations == ()
    assert all(
        item.relative_effort_weight is None
        for item in result.operational_decomposition.operational_subtasks
    )


@pytest.mark.parametrize("weight", [0, -1, "not-a-number"])
def test_relative_effort_weights_must_be_positive_numbers(weight):
    with pytest.raises(ValueError):
        type(make_operational().operational_subtasks[0]).model_validate(
            make_operational().operational_subtasks[0].model_dump()
            | {"relative_effort_weight": weight}
        )


def test_partial_relative_effort_weights_are_rejected():
    operational = weighted_operational().model_copy(
        update={
            "operational_subtasks": (
                weighted_operational()
                .operational_subtasks[0]
                .model_copy(update={"relative_effort_weight": None}),
                *weighted_operational().operational_subtasks[1:],
            )
        }
    )
    with pytest.raises(StageValidationError):
        validate_operational_decomposition(operational)


def test_baseline_estimates_require_complete_unique_subtask_coverage():
    operational = bottom_up_operational()
    estimates = operational.baseline_effort_estimates
    with pytest.raises(StageValidationError, match="missing baseline effort"):
        validate_operational_decomposition(
            operational.model_copy(update={"baseline_effort_estimates": estimates[:-1]})
        )
    with pytest.raises(StageValidationError, match="duplicate"):
        validate_operational_decomposition(
            operational.model_copy(
                update={
                    "baseline_effort_estimates": (
                        estimates[0],
                        estimates[0],
                        estimates[2],
                    )
                }
            )
        )


def test_inconsistent_provider_product_is_rejected():
    operational = bottom_up_operational()
    bad = operational.baseline_effort_estimates[0].model_copy(
        update={
            "expected_effort_per_parent_output": EffortQuantity(
                value=99, unit=EffortUnit.HOURS, time_basis="per_operation"
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


class RepairingWeightedProvider(FakeProvider):
    def __init__(self, repaired):
        super().__init__(operational=weighted_operational())
        self.repaired = repaired
        self.evaluation_requests = []

    def evaluate(self, request):
        self.evaluation_requests.append(request)
        decision = (
            SemanticEvaluationDecision.REPAIR
            if len(self.evaluation_requests) == 1
            else SemanticEvaluationDecision.ACCEPT
        )
        findings = ()
        if decision is SemanticEvaluationDecision.REPAIR:
            from test_semantic_orchestration import finding

            findings = (finding(),)
        return SemanticEvaluation(
            decision=decision,
            findings=findings,
            rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
        )

    def repair_operational_decomposition(
        self, request, *, rejected_response, validation_errors
    ):
        return self._response(ProviderStage.OPERATIONAL_DECOMPOSITION, self.repaired)


def test_repaired_subtasks_preserve_relative_effort_weights():
    repaired = weighted_operational().model_copy(
        update={
            "operational_subtasks": (
                weighted_operational()
                .operational_subtasks[0]
                .model_copy(update={"subtask_name": "Review the request"}),
                *weighted_operational().operational_subtasks[1:],
            )
        }
    )
    provider = RepairingWeightedProvider(repaired)

    result = decompose_task(
        request().model_copy(update={"baseline_effort": None}),
        provider,
    )

    assert [item.weight_ratio for item in result.baseline_effort_allocations] == [
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("0.5"),
    ]
    assert all(
        subtask.relative_effort_weight is not None
        for subtask in provider.evaluation_requests[
            -1
        ].operational_decomposition.operational_subtasks
    )
