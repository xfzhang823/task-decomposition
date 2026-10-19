from decimal import Decimal

import pytest
from test_provider_application import FakeProvider, request
from test_staged_pipeline import make_operational

from task_decomposition import (
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


def test_estimated_weights_create_shares_without_baseline_effort():
    task_request = request().model_copy(
        update={"baseline_effort": None, "effort_weights": None}
    )
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
    task_request = request().model_copy(update={"effort_weights": None})
    result = decompose_task(
        task_request,
        FakeProvider(operational=weighted_operational()),
    )

    assert [item.effort.value for item in result.baseline_effort_allocations] == [
        Decimal(20),
        Decimal(30),
        Decimal(50),
    ]


def test_host_weights_override_estimated_weights():
    result = decompose_task(
        request(),
        FakeProvider(operational=weighted_operational()),
    )

    assert [item.weight_ratio for item in result.baseline_effort_allocations] == [
        Decimal("0.3"),
        Decimal("0.4"),
        Decimal("0.3"),
    ]
    assert all(
        item.allocation_source == "host" for item in result.baseline_effort_allocations
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
        request().model_copy(update={"baseline_effort": None, "effort_weights": None}),
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
