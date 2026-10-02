from decimal import Decimal

import pytest
from pydantic import ValidationError

from task_decomposition import (
    AbsoluteEffortInput,
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkItem,
    ClassifiedSubtask,
    EffortQuantity,
    EffortUnit,
    NormalizedAccountingInput,
    OperationalDecomposition,
    OperationalSubtask,
    RatioBasis,
    RetainRemoveClassification,
    SupportWorkInput,
    SupportWorkInputs,
    TaskReference,
    TimeBasis,
    TransformationClassification,
    run_staged_pipeline,
    validate_operational_decomposition,
    validate_stage_chain,
)
from task_decomposition.errors import (
    CardinalityError,
    IdentityMismatchError,
    MissingAccountingInputError,
    SemanticAssertionError,
    StageDependencyError,
    SupportBasisConflictError,
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
    amount = normalized_amount if normalized else absolute_amount
    return AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="work-gov",
                workload_name="Review sampled account changes",
                category=AddedWorkCategory.GOVERNANCE,
                amount=amount("0.04" if normalized else 4),
                sequence_index=1,
            ),
            AddedWorkItem(
                work_id="work-ops",
                workload_name="Handle low-confidence exceptions",
                category=AddedWorkCategory.OPERATIONAL_SUPPORT,
                amount=amount("0.08" if normalized else 8),
                sequence_index=2,
            ),
            AddedWorkItem(
                work_id="work-life",
                workload_name="Maintain account update rules",
                category=AddedWorkCategory.LIFECYCLE_SUPPORT,
                amount=amount("0.02" if normalized else 2),
                sequence_index=3,
            ),
        ),
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
            governance=absolute_amount(0),
            operational_support=absolute_amount(0),
            lifecycle_support=absolute_amount(0),
        ),
    )


def make_normalized_accounting():
    return NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.60"),
        gross_removed_work_ratio=Decimal("0.40"),
        support_work=SupportWorkInputs(
            governance=normalized_amount(0),
            operational_support=normalized_amount(0),
            lifecycle_support=normalized_amount(0),
        ),
    )


def test_end_to_end_absolute_pipeline_delegates_to_wave1_accounting():
    result = run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_added(),
        make_absolute_accounting(),
    )

    assert result.accounting.w0 == Decimal("100")
    assert result.accounting.w1 == Decimal("74")
    assert result.accounting.gross_removed_work_ratio == Decimal("0.4")
    assert result.accounting.added_human_work_ratio == Decimal("0.14")
    assert result.accounting.net_remaining_work_ratio == Decimal("0.74")
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert result.accounting.effect.value == "gain"


def test_same_stages_support_normalized_accounting():
    result = run_staged_pipeline(
        make_operational(),
        make_classification(with_effort=False),
        make_added(normalized=True),
        make_normalized_accounting(),
    )
    assert result.accounting.w1 == Decimal("0.74")
    assert result.accounting.net_substitution_ratio == Decimal("0.26")


def test_effort_bearing_classification_can_be_normalized_without_duplicate_semantics():
    result = run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_added(normalized=True),
        make_normalized_accounting(),
    )
    assert result.accounting.net_remaining_work_ratio == Decimal("0.74")


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


def test_semantic_assertions_reject_meta_and_readiness_output():
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
    with pytest.raises(SemanticAssertionError):
        validate_operational_decomposition(bad)


def test_added_work_requires_explicit_basis_and_amount_for_accounting():
    missing_amount = make_added().model_copy(
        update={
            "added_work_rows": (
                make_added().added_work_rows[0].model_copy(update={"amount": None}),
                *make_added().added_work_rows[1:],
            )
        }
    )
    with pytest.raises(MissingAccountingInputError):
        run_staged_pipeline(
            make_operational(),
            make_classification(),
            missing_amount,
            make_absolute_accounting(),
        )

    mixed_basis = make_added().model_copy(
        update={
            "added_work_rows": (
                make_added()
                .added_work_rows[0]
                .model_copy(update={"sequence_index": None}),
                make_added()
                .added_work_rows[0]
                .model_copy(
                    update={
                        "work_id": "work-gov-2",
                        "amount": normalized_amount("0.04"),
                        "sequence_index": None,
                    }
                ),
                make_added()
                .added_work_rows[1]
                .model_copy(
                    update={"amount": normalized_amount("0.08"), "sequence_index": None}
                ),
                make_added()
                .added_work_rows[2]
                .model_copy(update={"sequence_index": None}),
            )
        }
    )
    with pytest.raises(SupportBasisConflictError):
        run_staged_pipeline(
            make_operational(),
            make_classification(),
            mixed_basis,
            make_absolute_accounting(),
        )


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
        run_staged_pipeline(
            make_operational(), classification, make_added(), make_absolute_accounting()
        )
