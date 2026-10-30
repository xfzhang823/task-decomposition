from decimal import Decimal

from task_transmorph import (
    AbsoluteEffortInput,
    AgenticTask,
    AgenticTaskSynthesis,
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
    ParentOutputContract,
    RetainRemoveClassification,
    SupportWorkInput,
    SupportWorkInputs,
    TaskReference,
    TimeBasis,
    TransformationClassification,
)
from task_transmorph.application.staged_pipeline import _run_staged_pipeline

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
        basis="absolute_effort",
        unit=UNIT,
        time_basis=PER_OPERATION,
    )


def normalized_amount(value):
    return SupportWorkInput(value=value, basis="normalized_contribution")


def make_operational():
    return OperationalDecomposition(
        task=TASK,
        parent_output_contract=ParentOutputContract(
            output_unit="One account update processed",
            completion_boundary="The account record is updated.",
            source="provider_inferred",
        ),
        baseline_effort_estimates=tuple(
            BaselineSubtaskEffortEstimate(
                subtask_id=f"sub-{index}",
                expected_occurrences_per_parent_output=1,
                active_effort_per_occurrence=EffortQuantity(
                    value=value, unit=UNIT, time_basis=PER_OPERATION
                ),
                expected_effort_per_parent_output=EffortQuantity(
                    value=value, unit=UNIT, time_basis=PER_OPERATION
                ),
                rationale="Usually occurs once.",
            )
            for index, value in enumerate((30, 40, 30), start=1)
        ),
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="sub-1",
                subtask_name="Receive account request",
                description="Log the incoming customer request.",
                effort_rationale="Usually occurs once.",
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="sub-2",
                subtask_name="Verify requester identity",
                description="Confirm the requester is authorized.",
                effort_rationale="Usually occurs once.",
                depends_on=("sub-1",),
            ),
            OperationalSubtask(
                sequence_index=3,
                subtask_id="sub-3",
                subtask_name="Update account record",
                description="Apply the approved account change.",
                effort_rationale="Usually occurs once.",
                depends_on=("sub-2",),
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
    )


def make_normalized_accounting():
    return NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.60"),
        gross_removed_work_ratio=Decimal("0.40"),
    )


def make_agentic():
    return AgenticTaskSynthesis(
        task=TASK,
        agentic_tasks=(
            AgenticTask(
                agentic_task_id="AGT001",
                agentic_task_name="Prepare account assessment",
                description="Assess the account update request.",
                source_subtask_ids=("sub-2",),
                required_inputs=("account request",),
                expected_outputs=("assessment",),
            ),
        ),
    )


def make_human_activities():
    return HumanAgentActivityModel(
        task=TASK,
        activities=(
            HumanAgentActivity(
                activity_id="HAA001",
                activity_name="Verify assessment",
                description="Review the agent assessment.",
                category=HumanAgentActivityCategory.AI_VERIFICATION,
                agentic_task_ids=("AGT001",),
                trigger="The agent completes the assessment.",
                expected_action="Accept or correct the assessment.",
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


def test_staged_pipeline_preserves_canonical_absolute_accounting():
    result = _run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_absolute_accounting(),
        support_work=SupportWorkInputs(
            ai_interaction=absolute_amount(8),
            ai_verification=absolute_amount(6),
        ),
    )
    assert result.w0 == Decimal(100)
    assert result.w1 == Decimal(74)


def test_staged_pipeline_preserves_canonical_normalized_accounting():
    result = _run_staged_pipeline(
        make_operational(),
        make_classification(with_effort=False),
        make_normalized_accounting(),
        support_work=SupportWorkInputs(
            ai_interaction=normalized_amount("0.08"),
            ai_verification=normalized_amount("0.06"),
        ),
    )
    assert result.w0 == Decimal(1)
    assert result.w1 == Decimal("0.74")
