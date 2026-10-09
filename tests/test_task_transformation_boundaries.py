from decimal import Decimal

import pytest

from task_decomposition import (
    AbsoluteEffortInput,
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkItem,
    EffortQuantity,
    EffortUnit,
    OperationalDecomposition,
    OperationalSubtask,
    ProviderProvenance,
    ProviderStage,
    ProviderStageResponse,
    RatioBasis,
    RetainRemoveClassification,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    TransformationClassification,
    TransformationDecompositionRequest,
    decompose,
    decompose_task,
    decompose_transformation,
)
from task_decomposition.ports import (
    DecompositionProvider,
    TaskDecompositionProvider,
    TransformationDecompositionProvider,
)

TASK = TaskReference(
    task_id="task-boundary",
    task_name="Process account update",
    task_description="Process a customer account update request.",
)
UNIT = EffortUnit.EFFORT
TIME = TimeBasis.PER_OPERATION


def amount(value):
    return SupportWorkInput(
        value=value,
        basis=RatioBasis.ABSOLUTE_EFFORT,
        unit=UNIT,
        time_basis=TIME,
    )


def accounting(*, retained=60, removed=40):
    return AbsoluteEffortInput(
        baseline_human_effort=EffortQuantity(value=100, unit=UNIT, time_basis=TIME),
        retained_human_work=EffortQuantity(value=retained, unit=UNIT, time_basis=TIME),
        gross_removed_work=EffortQuantity(value=removed, unit=UNIT, time_basis=TIME),
        support_work=SupportWorkInputs(
            governance=amount(4),
            operational_support=amount(8),
            lifecycle_support=amount(2),
        ),
    )


def operational():
    return OperationalDecomposition(
        task=TASK,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="sub-1",
                subtask_name="Receive account request",
                description="Log the incoming customer request.",
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="sub-2",
                subtask_name="Verify requester identity",
                description="Confirm the requester is authorized.",
                depends_on=("sub-1",),
            ),
            OperationalSubtask(
                sequence_index=3,
                subtask_id="sub-3",
                subtask_name="Update account record",
                description="Apply the approved account change.",
                depends_on=("sub-2",),
            ),
        ),
    )


def added_work():
    return AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="work-governance",
                workload_name="Review account changes",
                category=AddedWorkCategory.GOVERNANCE,
                amount=amount(4),
                sequence_index=1,
            ),
            AddedWorkItem(
                work_id="work-support",
                workload_name="Handle exceptions",
                category=AddedWorkCategory.OPERATIONAL_SUPPORT,
                amount=amount(8),
                sequence_index=2,
            ),
            AddedWorkItem(
                work_id="work-lifecycle",
                workload_name="Maintain update rules",
                category=AddedWorkCategory.LIFECYCLE_SUPPORT,
                amount=amount(2),
                sequence_index=3,
            ),
        ),
    )


def classification(*, all_retain=False):
    labels = (
        (TransformationClassification.RETAIN,) * 3
        if all_retain
        else (
            TransformationClassification.RETAIN,
            TransformationClassification.REMOVE,
            TransformationClassification.RETAIN,
        )
    )
    return RetainRemoveClassification(
        task=TASK,
        classified_subtasks=tuple(
            {
                "subtask_id": f"sub-{index}",
                "classification": label,
            }
            for index, label in enumerate(labels, start=1)
        ),
    )


class BoundaryProvider:
    provider_id = "boundary-fake"

    def __init__(self):
        self.calls = []
        self.all_retain = False
        self.task_request = None

    def _response(self, stage, payload):
        return ProviderStageResponse(
            stage=stage,
            payload=payload,
            provenance=ProviderProvenance(
                provider_id=self.provider_id,
                stage=stage,
                model_id="boundary-model",
            ),
        )

    def evaluate(self, request):
        return SemanticEvaluation(
            decision=SemanticEvaluationDecision.ACCEPT,
            rubric_version="1.0",
        )

    def generate_operational_decomposition(self, request):
        self.calls.append("task")
        self.task_request = request.request
        return self._response(
            ProviderStage.OPERATIONAL_DECOMPOSITION,
            operational(),
        )

    def classify_retain_remove(self, request):
        self.calls.append("retain-remove")
        return self._response(
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            classification(all_retain=self.all_retain),
        )

    def classify_added_work(self, request):
        self.calls.append("added-work")
        return self._response(
            ProviderStage.ADDED_WORK_CLASSIFICATION,
            added_work(),
        )


def task_request():
    return TaskDecompositionRequest(
        task=TASK,
        task_context={"domain": "customer_support"},
        baseline_effort=EffortQuantity(value=100, unit=UNIT, time_basis=TIME),
        effort_weights={
            "sub-1": Decimal("0.30"),
            "sub-2": Decimal("0.40"),
            "sub-3": Decimal("0.30"),
        },
    )


def transform_request(baseline, *, retained=60, removed=40):
    return TransformationDecompositionRequest(
        task_decomposition=baseline,
        transformation_context={"target": "assisted account updates"},
        accounting_input=accounting(retained=retained, removed=removed),
    )


def test_task_decomposition_is_independent_and_allocates_baseline():
    provider = BoundaryProvider()
    baseline = decompose_task(task_request(), provider)

    assert isinstance(provider, TaskDecompositionProvider)
    assert not hasattr(provider.task_request, "transformation_intent")
    assert provider.calls == ["task"]
    assert len(baseline.operational_decomposition.operational_subtasks) == 3
    assert [item.effort.value for item in baseline.baseline_effort_allocations] == [
        Decimal(30),
        Decimal(40),
        Decimal(30),
    ]


def test_transformation_decomposition_consumes_fixed_baseline():
    provider = BoundaryProvider()
    baseline = decompose_task(task_request(), provider)
    original = baseline

    result = decompose_transformation(transform_request(baseline), provider)

    assert isinstance(provider, TransformationDecompositionProvider)
    assert result.task_decomposition is original
    assert provider.calls == ["task", "retain-remove", "added-work"]
    assert result.accounting.w0 == Decimal(100)
    assert result.accounting.w1 == Decimal(74)
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert baseline == original


def test_frozen_baseline_is_reused_for_multiple_transformations():
    provider = BoundaryProvider()
    baseline = decompose_task(task_request(), provider)
    allocations = baseline.baseline_effort_allocations

    result_a = decompose_transformation(transform_request(baseline), provider)
    provider.all_retain = True
    result_b = decompose_transformation(
        transform_request(baseline, retained=100, removed=0), provider
    )

    assert provider.calls.count("task") == 1
    assert result_a.task_decomposition is baseline
    assert result_b.task_decomposition is baseline
    assert baseline.baseline_effort_allocations == allocations
    assert result_a.accounting.w1 == Decimal(74)
    assert result_b.accounting.w1 == Decimal(114)
    assert result_b.accounting.effect.value == "degradation"


def test_convenience_facade_composes_the_two_capabilities():
    provider = BoundaryProvider()
    result = decompose(
        task_request(),
        provider,
        transformation_context={"target": "assisted account updates"},
        accounting_input=accounting(),
    )

    assert isinstance(provider, DecompositionProvider)
    assert provider.calls == ["task", "retain-remove", "added-work"]
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert len(result.provider_provenance) == 3


def test_new_task_request_rejects_transformation_intent():
    with pytest.raises(ValueError):
        TaskDecompositionRequest(
            task=TASK,
            transformation_intent="not part of task decomposition",
        )
