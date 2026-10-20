from decimal import Decimal

import pytest

from task_decomposition import (
    AbsoluteEffortInput,
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkEstimate,
    AddedWorkItem,
    EffortQuantity,
    EffortUnit,
    EstimateRange,
    ExternalReference,
    RetainRemoveClassification,
    SupportWorkInput,
    SupportWorkInputs,
    SupportWorkMode,
    TaskReference,
    TimeBasis,
    validate_added_work_classification,
)
from task_decomposition.application.added_work_estimation import resolve_support_work
from task_decomposition.contracts.stages import (
    ClassifiedSubtask,
    OperationalDecomposition,
    OperationalSubtask,
)
from task_decomposition.errors import AddedWorkEstimationError, StageValidationError

TASK = TaskReference(task_id="estimate", task_name="Process request")
UNIT = EffortUnit.EFFORT
PER_OPERATION = TimeBasis.PER_OPERATION


def accounting(support=None):
    return AbsoluteEffortInput(
        baseline_human_effort=EffortQuantity(
            value=100, unit=UNIT, time_basis=PER_OPERATION
        ),
        retained_human_work=EffortQuantity(
            value=40, unit=UNIT, time_basis=PER_OPERATION
        ),
        gross_removed_work=EffortQuantity(
            value=60, unit=UNIT, time_basis=PER_OPERATION
        ),
        support_work=support,
    )


def support(interaction=0, verification=0):
    def amount(value):
        return SupportWorkInput(
            value=value,
            basis="absolute_effort",
            unit=UNIT,
            time_basis=PER_OPERATION,
        )

    return SupportWorkInputs(
        ai_interaction=amount(interaction), ai_verification=amount(verification)
    )


def operational():
    return OperationalDecomposition(
        task=TASK,
        operational_subtasks=tuple(
            OperationalSubtask(
                sequence_index=i, subtask_id=f"s{i}", subtask_name=f"Subtask {i}"
            )
            for i in range(1, 4)
        ),
    )


def classification():
    return RetainRemoveClassification(
        task=TASK,
        classified_subtasks=(
            ClassifiedSubtask(
                subtask_id="s1",
                classification="remove",
                effort=EffortQuantity(value=20, unit=UNIT, time_basis=PER_OPERATION),
            ),
            ClassifiedSubtask(
                subtask_id="s2",
                classification="retain",
                effort=EffortQuantity(value=40, unit=UNIT, time_basis=PER_OPERATION),
            ),
            ClassifiedSubtask(
                subtask_id="s3",
                classification="remove",
                effort=EffortQuantity(value=40, unit=UNIT, time_basis=PER_OPERATION),
            ),
        ),
    )


def estimate(reference="s2"):
    return AddedWorkEstimate(
        occurrences_per_parent_execution=EstimateRange(low=1, typical=2, high=3),
        reference_occurrences_per_parent_execution=EstimateRange(
            low=2, typical=2, high=2
        ),
        relative_effort_per_occurrence=EstimateRange(
            low="0.1", typical="0.25", high="0.5"
        ),
        reference_subtask_id=reference,
        rationale="Incremental AI-specific review.",
        estimate_basis="assumed",
    )


def test_repeated_reference_is_normalized_and_retained_reference_is_valid():
    added = AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="w1",
                workload_name="Guide AI",
                category=AddedWorkCategory.AI_INTERACTION,
                source_removed_subtask_ids=("s1", "s3"),
                estimate=estimate(),
            ),
        ),
    )
    resolved, diagnostic = resolve_support_work(
        added, classification(), accounting(), mode=SupportWorkMode.ESTIMATE
    )
    assert resolved.ai_interaction.value == Decimal(10)
    assert resolved.ai_verification.value == Decimal(0)
    assert diagnostic.estimated_support_work == resolved


def test_causal_validation_rejects_missing_and_retain_sources():
    base = operational()
    classified = classification()
    missing = AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(work_id="w", workload_name="x", category="AI_INTERACTION"),
        ),
    )
    with pytest.raises(StageValidationError):
        validate_added_work_classification(base, classified, missing)
    wrong = missing.model_copy(
        update={
            "added_work_rows": (
                AddedWorkItem(
                    work_id="w",
                    workload_name="x",
                    category="AI_INTERACTION",
                    source_removed_subtask_ids=("s2",),
                ),
            )
        }
    )
    with pytest.raises(StageValidationError):
        validate_added_work_classification(base, classified, wrong)


def test_external_reference_requires_quantitative_anchor():
    row = AddedWorkItem(
        work_id="w",
        workload_name="Verify AI",
        category="AI_VERIFICATION",
        source_removed_subtask_ids=("s1",),
        estimate=AddedWorkEstimate(
            occurrences_per_parent_execution=EstimateRange(low=1, typical=1, high=1),
            relative_effort_per_occurrence=EstimateRange(low=1, typical=1, high=1),
            external_reference=ExternalReference(activity="Document review"),
            rationale="Comparable review.",
            estimate_basis="assumed",
        ),
    )
    with pytest.raises(AddedWorkEstimationError):
        resolve_support_work(
            AddedWorkClassification(task=TASK, added_work_rows=(row,)),
            classification(),
            accounting(),
            mode=SupportWorkMode.ESTIMATE,
        )


def test_host_zero_is_preserved_and_auto_prefers_host():
    added = AddedWorkClassification(task=TASK, added_work_rows=())
    host = support(0, 0)
    resolved, diagnostic = resolve_support_work(
        added,
        classification(),
        accounting(host),
        mode=SupportWorkMode.AUTO,
    )
    assert resolved == host
    assert diagnostic.source_by_category[AddedWorkCategory.AI_INTERACTION] == "host"
