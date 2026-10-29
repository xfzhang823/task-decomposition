from decimal import Decimal

import pytest
from pydantic import ValidationError

from task_decomposition import (
    AbsoluteEffortInput,
    ActivityEffortEstimate,
    ActivityEffortEstimation,
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkItem,
    AgenticTask,
    AgenticTaskSynthesis,
    BaselineEffortAllocation,
    BaselineEffortEstimation,
    BaselineSubtaskEffortEstimate,
    ClassifiedSubtask,
    EffortQuantity,
    EffortUnit,
    HumanAgentActivity,
    HumanAgentActivityCategory,
    HumanAgentActivityModel,
    NormalizedAccountingInput,
    OperationalDecomposition,
    OperationalSubtask,
    RatioBasis,
    RetainRemoveClassification,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecomposition,
    TaskReference,
    TimeBasis,
    TransformationClassification,
    validate_operational_decomposition,
    validate_stage_chain,
)
from task_decomposition.application.staged_pipeline import _run_staged_pipeline
from task_decomposition.application.transformation_decomposition import (
    _apply_baseline_allocation,
    _apply_calibrated_partition,
)
from task_decomposition.contracts.provider import TransformationDecompositionRequest
from task_decomposition.errors import (
    CardinalityError,
    IdentityMismatchError,
    MissingAccountingInputError,
    StageDependencyError,
    UnknownReferenceError,
)

TASK = TaskReference(
    task_id="task-1",
    task_name="Process account update",
    task_description="Process a customer account update request.",
)
UNIT = EffortUnit.EFFORT
PER_OPERATION = TimeBasis.PER_OPERATION


def absolute_amount(value):
    return SupportWorkInput(
        value=value,
        basis=RatioBasis.ABSOLUTE_EFFORT,
        unit=UNIT,
        time_basis=PER_OPERATION,
    )


def normalized_amount(value):
    return SupportWorkInput(value=value, basis=RatioBasis.NORMALIZED_CONTRIBUTION)


def make_operational():
    return OperationalDecomposition(
        task=TASK,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="sub-1",
                subtask_name="Receive account request",
                description="Log the incoming customer request.",
                effort_rationale="Usually occurs once; straightforward logging requires limited effort.",
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="sub-2",
                subtask_name="Verify requester identity",
                description="Confirm the requester is authorized.",
                effort_rationale="Usually occurs once; checking authorization is moderately complex.",
                depends_on=("sub-1",),
            ),
            OperationalSubtask(
                sequence_index=3,
                subtask_id="sub-3",
                subtask_name="Update account record",
                description="Apply the approved account change.",
                effort_rationale="Usually occurs once; applying the change requires focused system interaction.",
                depends_on=("sub-2",),
            ),
        ),
    )


def make_classification(*, with_effort=True):
    def quantity(value):
        return EffortQuantity(value=value, unit=UNIT, time_basis=PER_OPERATION)

    return RetainRemoveClassification(
        task=TASK,
        classified_subtasks=(
            ClassifiedSubtask(
                subtask_id="sub-1",
                classification=TransformationClassification.RETAIN,
                effort=quantity(30) if with_effort else None,
                baseline_effort_ratio=Decimal("0.30") if not with_effort else None,
            ),
            ClassifiedSubtask(
                subtask_id="sub-2",
                classification=TransformationClassification.REMOVE,
                effort=quantity(40) if with_effort else None,
                baseline_effort_ratio=Decimal("0.40") if not with_effort else None,
            ),
            ClassifiedSubtask(
                subtask_id="sub-3",
                classification=TransformationClassification.RETAIN,
                effort=quantity(30) if with_effort else None,
                baseline_effort_ratio=Decimal("0.30") if not with_effort else None,
            ),
        ),
    )


def make_added(*, normalized=False):
    return AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="work-gov",
                workload_name="Review sampled account changes",
                category=AddedWorkCategory.AI_VERIFICATION,
                source_removed_subtask_ids=("sub-2",),
                sequence_index=1,
            ),
            AddedWorkItem(
                work_id="work-ops",
                workload_name="Handle low-confidence exceptions",
                category=AddedWorkCategory.AI_INTERACTION,
                source_removed_subtask_ids=("sub-2",),
                sequence_index=2,
            ),
            AddedWorkItem(
                work_id="work-life",
                workload_name="Maintain account update rules",
                category=AddedWorkCategory.AI_VERIFICATION,
                source_removed_subtask_ids=("sub-2",),
                sequence_index=3,
            ),
        ),
    )


def make_agentic():
    return AgenticTaskSynthesis(
        task=TASK,
        agentic_tasks=(
            AgenticTask(
                agentic_task_id="AGT001",
                agentic_task_name="Prepare account update assessment",
                description="Assess the account update request for automated processing.",
                source_subtask_ids=("sub-2",),
                required_inputs=("account update request",),
                expected_outputs=("validated update assessment",),
            ),
        ),
    )


def make_human_activities():
    return HumanAgentActivityModel(
        task=TASK,
        activities=(
            HumanAgentActivity(
                activity_id="HAA001",
                activity_name="Verify account assessment",
                description="Review the agent assessment for material errors.",
                category=HumanAgentActivityCategory.AI_VERIFICATION,
                agentic_task_ids=("AGT001",),
                trigger="The agent completes its assessment.",
                expected_action="Accept the assessment or flag discrepancies.",
            ),
        ),
    )


def make_activity_effort_estimation():
    return ActivityEffortEstimation(
        task=TASK,
        activity_effort_estimates=(
            ActivityEffortEstimate(
                activity_id="HAA001",
                expected_occurrences_per_parent_output=1,
                active_effort_per_occurrence=EffortQuantity(
                    value=14, unit=UNIT, time_basis=PER_OPERATION
                ),
                expected_effort_per_parent_output=EffortQuantity(
                    value=14, unit=UNIT, time_basis=PER_OPERATION
                ),
                rationale="One review per parent output.",
            ),
        ),
        estimated_baseline_effort_per_parent_output=EffortQuantity(
            value=100, unit=UNIT, time_basis=PER_OPERATION
        ),
        baseline_rationale="Planning calibration for the parent output.",
    )


def make_absolute_accounting():
    return AbsoluteEffortInput(
        baseline_human_effort=EffortQuantity(
            value=100, unit=UNIT, time_basis=PER_OPERATION
        ),
        retained_human_work=EffortQuantity(
            value=60, unit=UNIT, time_basis=PER_OPERATION
        ),
        gross_removed_work=EffortQuantity(
            value=40, unit=UNIT, time_basis=PER_OPERATION
        ),
        support_work=SupportWorkInputs(
            ai_interaction=absolute_amount(0),
            ai_verification=absolute_amount(0),
        ),
    )


def make_normalized_accounting():
    return NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.60"),
        gross_removed_work_ratio=Decimal("0.40"),
        support_work=SupportWorkInputs(
            ai_interaction=normalized_amount(0),
            ai_verification=normalized_amount(0),
        ),
    )


def test_bottom_up_subtask_effort_is_scaled_to_supplied_baseline():
    estimates = tuple(
        BaselineSubtaskEffortEstimate(
            subtask_id=subtask.subtask_id,
            expected_occurrences_per_parent_output=1,
            active_effort_per_occurrence=EffortQuantity(
                value=value, unit=EffortUnit.MINUTES, time_basis=PER_OPERATION
            ),
            expected_effort_per_parent_output=EffortQuantity(
                value=value, unit=EffortUnit.MINUTES, time_basis=PER_OPERATION
            ),
            rationale="Bottom-up baseline fixture.",
        )
        for subtask, value in zip(make_operational().operational_subtasks, (8, 12, 7))
    )
    task_decomposition = TaskDecomposition(
        operational_decomposition=make_operational(),
        baseline_effort_estimation=BaselineEffortEstimation(
            task=TASK,
            estimates=estimates,
            total_effort_per_parent_output=EffortQuantity(
                value=27, unit=EffortUnit.MINUTES, time_basis=PER_OPERATION
            ),
        ),
        baseline_effort_allocations=tuple(
            BaselineEffortAllocation(
                subtask_id=subtask.subtask_id,
                weight_ratio=Decimal(str(value)) / Decimal(27),
            )
            for subtask, value in zip(
                make_operational().operational_subtasks, (8, 12, 7)
            )
        ),
    )
    accounting = AbsoluteEffortInput(
        baseline_human_effort=EffortQuantity(
            value=30, unit=EffortUnit.MINUTES, time_basis=PER_OPERATION
        ),
        retained_human_work=EffortQuantity(
            value=0, unit=EffortUnit.MINUTES, time_basis=PER_OPERATION
        ),
        gross_removed_work=EffortQuantity(
            value=0, unit=EffortUnit.MINUTES, time_basis=PER_OPERATION
        ),
    )
    request = TransformationDecompositionRequest(
        task_decomposition=task_decomposition,
        accounting_input=accounting,
    )

    classification = _apply_baseline_allocation(
        make_classification(with_effort=False), request
    )
    calibrated = _apply_calibrated_partition(accounting, classification)

    expected = (
        Decimal(240) / Decimal(27),
        Decimal(360) / Decimal(27),
        Decimal(210) / Decimal(27),
    )
    assert all(
        abs(item.effort.value - expected_value) < Decimal("1e-24")
        for item, expected_value in zip(classification.classified_subtasks, expected)
    )
    assert abs(
        calibrated.retained_human_work.value - Decimal(450) / Decimal(27)
    ) < Decimal("1e-24")
    assert abs(
        calibrated.gross_removed_work.value - Decimal(360) / Decimal(27)
    ) < Decimal("1e-24")


def make_absolute_support():
    return SupportWorkInputs(
        ai_interaction=absolute_amount(8),
        ai_verification=absolute_amount(6),
    )


def make_normalized_support():
    return SupportWorkInputs(
        ai_interaction=normalized_amount("0.08"),
        ai_verification=normalized_amount("0.06"),
    )


def test_end_to_end_absolute_pipeline_delegates_to_wave1_accounting():
    result = _run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_added(),
        make_absolute_accounting(),
        support_work=make_absolute_support(),
    )

    assert result.w0 == Decimal(100)
    assert result.w1 == Decimal(74)
    assert result.gross_removed_work_ratio == Decimal("0.4")
    assert result.added_human_work_ratio == Decimal("0.14")
    assert result.net_remaining_work_ratio == Decimal("0.74")
    assert result.net_substitution_ratio == Decimal("0.26")
    assert result.effect.value == "gain"


def test_same_stages_support_normalized_accounting():
    result = _run_staged_pipeline(
        make_operational(),
        make_classification(with_effort=False),
        make_added(normalized=True),
        make_normalized_accounting(),
        support_work=make_normalized_support(),
    )
    assert result.w1 == Decimal("0.74")
    assert result.net_substitution_ratio == Decimal("0.26")


def test_effort_bearing_classification_can_be_normalized_without_duplicate_semantics():
    result = _run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_added(normalized=True),
        make_normalized_accounting(),
        support_work=make_normalized_support(),
    )
    assert result.net_remaining_work_ratio == Decimal("0.74")


def test_wire_case_is_normalized_but_identity_is_preserved():
    operational = make_operational().model_dump(mode="python")
    classification = make_classification().model_dump(mode="python")
    for item in classification["classified_subtasks"]:
        item["classification"] = item["classification"].upper()
    added = make_added().model_dump(mode="python")
    for item in added["added_work_rows"]:
        item["category"] = item["category"].upper()
    validated = validate_stage_chain(operational, classification, added)
    assert [item.subtask_id for item in validated[1].classified_subtasks] == [
        "sub-1",
        "sub-2",
        "sub-3",
    ]


def test_classification_uses_frozen_task_and_subtask_descriptions():
    operational = make_operational()
    classification = make_classification().model_copy(
        update={
            "task": TASK.model_copy(
                update={"task_description": "Provider paraphrase."}
            ),
            "classified_subtasks": tuple(
                row.model_copy(
                    update={
                        "subtask_name": f"Provider label for {row.subtask_id}",
                        "sequence_index": None,
                    }
                )
                for row in make_classification().classified_subtasks
            ),
        }
    )
    _, validated, _ = validate_stage_chain(operational, classification, make_added())
    assert validated.task == operational.task
    assert [row.subtask_name for row in validated.classified_subtasks] == [
        item.subtask_name for item in operational.operational_subtasks
    ]
    assert [row.sequence_index for row in validated.classified_subtasks] == [1, 2, 3]


def test_missing_extra_and_duplicate_classifications_are_rejected():
    operational = make_operational()
    classification = make_classification().model_copy(
        update={"classified_subtasks": make_classification().classified_subtasks[:-1]}
    )
    with pytest.raises(CardinalityError, match="missing classifications"):
        validate_stage_chain(operational, classification, make_added())

    extra = ClassifiedSubtask(
        subtask_id="unknown",
        classification=TransformationClassification.RETAIN,
    )
    with pytest.raises(UnknownReferenceError, match="unknown classified"):
        validate_stage_chain(
            operational,
            RetainRemoveClassification(
                task=TASK,
                classified_subtasks=make_classification().classified_subtasks
                + (extra,),
            ),
            make_added(),
        )

    duplicate = make_classification().classified_subtasks[:2] + (
        make_classification().classified_subtasks[0],
    )
    with pytest.raises(CardinalityError, match="duplicate"):
        validate_stage_chain(
            operational,
            RetainRemoveClassification(task=TASK, classified_subtasks=duplicate),
            make_added(),
        )


def test_task_identity_and_dependency_integrity_are_rejected():
    wrong_task = TaskReference(task_id="other", task_name=TASK.task_name)
    with pytest.raises(IdentityMismatchError):
        validate_stage_chain(
            make_operational(),
            make_classification().model_copy(update={"task": wrong_task}),
            make_added(),
        )

    bad_dependency = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(update={"depends_on": ("missing",)}),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    with pytest.raises(UnknownReferenceError):
        validate_operational_decomposition(bad_dependency)

    forward_dependency = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(update={"depends_on": ("sub-2",)}),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    with pytest.raises(StageDependencyError):
        validate_operational_decomposition(forward_dependency)


def test_sequence_duplicate_added_work_and_bad_category_are_rejected():
    rows = make_added().added_work_rows
    with pytest.raises(CardinalityError, match="added-work sequence"):
        validate_stage_chain(
            make_operational(),
            make_classification(),
            AddedWorkClassification(
                task=TASK,
                added_work_rows=(
                    rows[0].model_copy(update={"sequence_index": 1}),
                    rows[1].model_copy(update={"sequence_index": 1}),
                ),
            ),
        )
    with pytest.raises(ValidationError):
        AddedWorkItem(
            work_id="bad",
            workload_name="Bad category",
            category="OTHER",
        )


def test_operational_structure_does_not_apply_lexical_semantic_rejection():
    bad = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(
                    update={
                        "subtask_name": "Analyze request intake",
                        "description": "Provide a readiness score.",
                    }
                ),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    validate_operational_decomposition(bad)


def test_staged_pipeline_uses_resolved_support_inputs():
    result = _run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_added(),
        make_absolute_accounting(),
        support_work=make_absolute_support(),
    )
    assert result.added_human_work.value == Decimal(14)


def test_partial_classification_effort_is_not_invented():
    classification = make_classification().model_copy(
        update={
            "classified_subtasks": (
                make_classification()
                .classified_subtasks[0]
                .model_copy(update={"effort": None}),
                *make_classification().classified_subtasks[1:],
            )
        }
    )
    with pytest.raises(MissingAccountingInputError):
        _run_staged_pipeline(
            make_operational(),
            classification,
            make_added(),
            make_absolute_accounting(),
            support_work=make_absolute_support(),
        )
