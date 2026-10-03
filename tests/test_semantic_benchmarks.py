from decimal import Decimal

import pytest

from task_decomposition import (
    AbsoluteEffortInput,
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkItem,
    BaselineEffortAllocation,
    ClassifiedSubtask,
    EffortQuantity,
    EffortUnit,
    OperationalDecomposition,
    OperationalSubtask,
    ProviderProvenance,
    RetainRemoveClassification,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecomposition,
    TaskReference,
    TimeBasis,
    TransformationClassification,
    TransformationDecompositionResult,
    account_absolute,
)
from task_decomposition.contracts.provenance import ProviderStage

from benchmark_support import (
    BenchmarkCase,
    check_hard_validity,
    load_benchmark_cases,
    render_review_artifact,
    review_task_semantics,
    review_transformation_semantics,
)


def effort(value: int | str) -> EffortQuantity:
    return EffortQuantity(
        value=value, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION
    )


def support(value: int | str) -> SupportWorkInput:
    return SupportWorkInput(
        value=value,
        basis="absolute_effort",
        unit=EffortUnit.EFFORT,
        time_basis=TimeBasis.PER_OPERATION,
    )


def fixture_result() -> TransformationDecompositionResult:
    task = TaskReference(
        task_id="benchmark-task",
        task_name="Handle customer support ticket",
        task_description="Receive and resolve a customer support ticket.",
    )
    subtasks = (
        OperationalSubtask(
            sequence_index=1,
            subtask_id="receive",
            subtask_name="Receive ticket",
            description="Receive the customer ticket.",
        ),
        OperationalSubtask(
            sequence_index=2,
            subtask_id="verify",
            subtask_name="Verify account",
            description="Verify the customer account.",
            depends_on=("receive",),
        ),
        OperationalSubtask(
            sequence_index=3,
            subtask_id="diagnose",
            subtask_name="Review issue evidence",
            description="Review evidence and diagnose the reported issue.",
            depends_on=("verify",),
        ),
        OperationalSubtask(
            sequence_index=4,
            subtask_id="communicate",
            subtask_name="Communicate resolution",
            description="Send the approved resolution to the customer.",
            depends_on=("diagnose",),
        ),
        OperationalSubtask(
            sequence_index=5,
            subtask_id="escalate",
            subtask_name="Escalate exception",
            description="Escalate exceptions for human review.",
            depends_on=("diagnose",),
        ),
    )
    operational = OperationalDecomposition(task=task, operational_subtasks=subtasks)
    allocations = tuple(
        BaselineEffortAllocation(subtask_id=subtask.subtask_id, weight_ratio=weight)
        for subtask, weight in zip(subtasks, ("0.15", "0.20", "0.30", "0.20", "0.15"))
    )
    task_decomposition = TaskDecomposition(
        operational_decomposition=operational,
        baseline_effort_allocations=allocations,
    )
    classification = RetainRemoveClassification(
        task=task,
        classified_subtasks=(
            ClassifiedSubtask(
                subtask_id="receive",
                classification=TransformationClassification.RETAIN,
                rationale="The agent still receives the request.",
            ),
            ClassifiedSubtask(
                subtask_id="verify",
                classification=TransformationClassification.RETAIN,
                rationale="The agent must verify identity and account context.",
            ),
            ClassifiedSubtask(
                subtask_id="diagnose",
                classification=TransformationClassification.REMOVE,
                rationale="The model drafts a diagnosis for review.",
            ),
            ClassifiedSubtask(
                subtask_id="communicate",
                classification=TransformationClassification.RETAIN,
                rationale="The agent approves and sends the final response.",
            ),
            ClassifiedSubtask(
                subtask_id="escalate",
                classification=TransformationClassification.RETAIN,
                rationale="Exception escalation remains human-owned.",
            ),
        ),
    )
    added = AddedWorkClassification(
        task=task,
        added_work_rows=(
            AddedWorkItem(
                work_id="governance-review",
                workload_name="Review model responses",
                category=AddedWorkCategory.GOVERNANCE,
                description="Review a sample of model-assisted responses.",
                amount=support(4),
            ),
        ),
    )
    accounting = account_absolute(
        AbsoluteEffortInput(
            baseline_human_effort=effort(100),
            retained_human_work=effort(70),
            gross_removed_work=effort(30),
            support_work=SupportWorkInputs(
                governance=support(4),
                operational_support=support(0),
                lifecycle_support=support(0),
            ),
        )
    )
    return TransformationDecompositionResult(
        task_decomposition=task_decomposition,
        retain_remove_classification=classification,
        added_work_classification=added,
        accounting=accounting,
        provider_provenance=(
            ProviderProvenance(
                provider_id="fixture", stage=ProviderStage.OPERATIONAL_DECOMPOSITION
            ),
        ),
    )


def test_benchmark_corpus_definitions_are_valid_and_diverse():
    cases = load_benchmark_cases()

    assert 10 <= len(cases) <= 15
    assert len({case.process_name for case in cases}) == len(cases)
    assert len({case.transformation_context["description"] for case in cases}) == len(
        cases
    )
    assert all(
        case.expected_task_count.min <= case.expected_task_count.max for case in cases
    )


def test_benchmark_case_rejects_missing_structured_expectations():
    with pytest.raises(ValueError):
        BenchmarkCase(
            id="invalid",
            process_name="Invalid process",
            process_description="A process.",
            task_context={"domain": "test"},
            transformation_context={"description": "A concrete change."},
            expected_task_count={"min": 5, "max": 2},
            must_contain=["work"],
            expected_net_substitution_range={"min": 0, "max": 1},
        )


def test_hard_validity_is_separate_from_semantic_review():
    case = load_benchmark_cases()[0]
    result = fixture_result()

    hard = check_hard_validity(result)
    task_review = review_task_semantics(case, result.task_decomposition)
    transformation_review = review_transformation_semantics(case, result)

    assert hard.valid
    assert not hard.errors
    assert task_review["task_count"] == 5
    assert task_review["missing_expected_work_terms"] == ()
    assert transformation_review["retained_count"] == 4
    assert transformation_review["removed_count"] == 1
    assert transformation_review["added_work_count"] == 1
    assert transformation_review["net_substitution"] == Decimal("0.26")


def test_hard_validity_reports_invalid_stage_identity():
    result = fixture_result()
    invalid = result.model_copy(
        update={
            "retain_remove_classification": result.retain_remove_classification.model_copy(
                update={
                    "classified_subtasks": result.retain_remove_classification.classified_subtasks[
                        :-1
                    ]
                }
            )
        }
    )

    report = check_hard_validity(invalid)

    assert not report.valid
    assert any("stage validation failed" in error for error in report.errors)


def test_human_review_artifact_contains_all_required_sections():
    artifact = render_review_artifact(load_benchmark_cases()[0], fixture_result())

    assert "## TASK DECOMPOSITION" in artifact
    assert "## TRANSFORMATION" in artifact
    assert "## ADDED HUMAN WORK" in artifact
    assert "## RESULT" in artifact
    assert "Gross removed ratio:" in artifact
    assert "Net substitution ratio:" in artifact
    assert "GAIN" in artifact
