from decimal import Decimal

import pytest

from task_decomposition import (
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkEstimate,
    AddedWorkItem,
    EstimateRange,
    ExternalReference,
    NormalizedWorkEstimate,
    OperationalDecomposition,
    OperationalSubtask,
    ProviderProvenance,
    ProviderStage,
    ProviderStageResponse,
    RetainRemoveClassification,
    TaskDecomposition,
    TaskReference,
    TransformationClassification,
    estimate_transformation,
)
from task_decomposition.contracts.provider import TransformationProposalRequest
from task_decomposition.contracts.stages import BaselineEffortAllocation
from task_decomposition.errors import (
    AddedWorkEstimationError,
    MissingEffortAllocationError,
    ProviderContractValidationError,
)

TASK = TaskReference(task_name="Review claim", task_description="Review a claim.")


def response(stage, payload):
    return ProviderStageResponse(
        stage=stage,
        payload=payload,
        provenance=ProviderProvenance(
            provider_id="normalized-fake", stage=stage, model_id="test-model"
        ),
    )


def baseline(*, allocations=True):
    task = OperationalDecomposition(
        task=TASK,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="sub-1",
                subtask_name="Check claim",
                effort_rationale="Requires claim review.",
                relative_effort_weight=Decimal(1),
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="sub-2",
                subtask_name="Route claim",
                effort_rationale="Requires routing judgment.",
                relative_effort_weight=Decimal(3),
            ),
        ),
    )
    return TaskDecomposition(
        operational_decomposition=task,
        baseline_effort_allocations=(
            BaselineEffortAllocation(subtask_id="sub-1", weight_ratio=Decimal(".25")),
            BaselineEffortAllocation(subtask_id="sub-2", weight_ratio=Decimal(".75")),
        )
        if allocations
        else (),
    )


def classification(*, rationale=True):
    return RetainRemoveClassification(
        task=TASK,
        classified_subtasks=(
            {
                "subtask_id": "sub-1",
                "classification": TransformationClassification.RETAIN,
                "rationale": "Human judgment remains necessary.",
            },
            {
                "subtask_id": "sub-2",
                "classification": TransformationClassification.REMOVE,
                "rationale": "Automation can perform the routing step."
                if rationale
                else None,
            },
        ),
    )


class FakeProvider:
    provider_id = "normalized-fake"

    def __init__(self, *, rationale=True, added=None):
        self.rationale = rationale
        self.added = added or AddedWorkClassification(task=TASK)
        self.requests = []

    def classify_retain_remove(self, request):
        self.requests.append(request)
        return response(
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            classification(rationale=self.rationale),
        )

    def classify_added_work(self, request):
        self.requests.append(request)
        return response(ProviderStage.ADDED_WORK_CLASSIFICATION, self.added)


def test_normalized_estimation_scales_weights_to_100_and_reconciles():
    result = estimate_transformation(baseline(), FakeProvider())
    estimates = result.normalized_work_estimates

    assert all(isinstance(item, NormalizedWorkEstimate) for item in estimates)
    assert sum(item.baseline_work_units for item in estimates) == Decimal(100)
    assert sum(item.retained_work_units for item in estimates) == Decimal(25)
    assert sum(item.gross_removed_work_units for item in estimates) == Decimal(75)
    assert result.accounting.w0 == Decimal(1)
    assert result.accounting.gross_removed_work_ratio == Decimal(".75")
    assert result.accounting.net_remaining_work_ratio == Decimal(".25")


def test_estimation_uses_qualitative_stage_requests_before_accounting():
    provider = FakeProvider()
    estimate_transformation(baseline(), provider)

    assert all(
        isinstance(item.request, TransformationProposalRequest)
        for item in provider.requests
    )


def test_added_work_is_post_transformation_and_not_double_counted():
    added = AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="verify",
                workload_name="Verify automation output",
                category=AddedWorkCategory.AI_VERIFICATION,
                source_removed_subtask_ids=("sub-2",),
                estimate=AddedWorkEstimate(
                    occurrences_per_parent_execution=EstimateRange(
                        low=1, typical=1, high=1
                    ),
                    relative_effort_per_occurrence=EstimateRange(
                        low=Decimal(".02"), typical=Decimal(".02"), high=Decimal(".02")
                    ),
                    external_reference=ExternalReference(
                        activity="verification",
                        effort_per_occurrence={
                            "value": Decimal(1),
                            "basis": "normalized_contribution",
                        },
                    ),
                    rationale="Verify automated output.",
                    estimate_basis="assumed",
                ),
            ),
        ),
    )
    result = estimate_transformation(baseline(), FakeProvider(added=added))

    assert result.accounting.gross_removed_work_ratio == Decimal(".75")
    assert result.accounting.added_human_work_ratio == Decimal(".02")
    assert result.accounting.net_remaining_work_ratio == Decimal(".27")


def test_normalized_estimation_rejects_missing_rationale():
    with pytest.raises(ProviderContractValidationError, match="rationale"):
        estimate_transformation(baseline(), FakeProvider(rationale=False))


def test_normalized_estimation_rejects_incomplete_added_work_estimate():
    added = AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="missing-estimate",
                workload_name="Verify automation output",
                category=AddedWorkCategory.AI_VERIFICATION,
                source_removed_subtask_ids=("sub-2",),
            ),
        ),
    )
    with pytest.raises(AddedWorkEstimationError, match="no computable estimate"):
        estimate_transformation(baseline(), FakeProvider(added=added))


def test_normalized_estimation_rejects_missing_baseline_allocation():
    with pytest.raises(MissingEffortAllocationError):
        estimate_transformation(baseline(allocations=False), FakeProvider())
