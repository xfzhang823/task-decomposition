import importlib
import sys

import pytest
from pydantic import ValidationError

from task_decomposition.contracts import (
    OperationalDecomposition,
    OperationalSubtask,
    TaskReference,
)
from task_decomposition.evaluation import (
    SEMANTIC_EVALUATION_RUBRIC,
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SemanticEvaluationRequest,
    SemanticEvaluator,
    SemanticEvaluatorProvenance,
    SemanticFinding,
    SemanticFindingCategory,
    SemanticFindingCode,
    SemanticFindingSeverity,
)


def operational_decomposition():
    task = TaskReference(
        task_name="Review an invoice",
        task_description="Validate the invoice and approve or reject it.",
    )
    return OperationalDecomposition(
        task=task,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="review",
                subtask_name="Review invoice against purchase order",
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="decide",
                subtask_name="Determine whether the invoice meets approval criteria",
                depends_on=("review",),
            ),
        ),
    )


def evaluation_request():
    decomposition = operational_decomposition()
    return SemanticEvaluationRequest(
        task=decomposition.task,
        task_context={"department": "accounts payable"},
        operational_decomposition=decomposition,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
        request_id="request-1",
        correlation_id="correlation-1",
    )


def finding(
    *,
    code=SemanticFindingCode.INSUFFICIENT_OPERATIONAL_SPECIFICITY,
    category=SemanticFindingCategory.ABSTRACTION,
    severity=SemanticFindingSeverity.REPAIRABLE,
    subtask_id="decide",
):
    return SemanticFinding(
        subtask_id=subtask_id,
        code=code,
        category=category,
        severity=severity,
        message="Describe what is evaluated or determined.",
        evidence="operational_subtasks[1].subtask_name",
    )


def test_request_and_evaluation_round_trip_with_provenance():
    request = evaluation_request()
    result = SemanticEvaluation(
        decision=SemanticEvaluationDecision.ACCEPT,
        findings=(
            finding(
                code=SemanticFindingCode.CLARIFY_WORK_DESCRIPTION,
                severity=SemanticFindingSeverity.SUGGESTION,
            ),
        ),
        rubric_version=request.rubric_version,
        evaluator_provenance=SemanticEvaluatorProvenance(
            provider_id="mock-evaluator",
            model_id="mock-model",
            request_id=request.request_id,
            correlation_id=request.correlation_id,
        ),
    )

    restored_request = SemanticEvaluationRequest.model_validate(
        request.model_dump(mode="json")
    )
    restored_result = SemanticEvaluation.model_validate(result.model_dump(mode="json"))
    assert restored_request == request
    assert restored_result == result
    assert result.evaluator_provenance is not None


@pytest.mark.parametrize(
    ("decision", "severity"),
    [
        (SemanticEvaluationDecision.ACCEPT, SemanticFindingSeverity.SUGGESTION),
        (SemanticEvaluationDecision.REPAIR, SemanticFindingSeverity.REPAIRABLE),
        (SemanticEvaluationDecision.REJECT, SemanticFindingSeverity.BLOCKING),
    ],
)
def test_each_decision_and_severity_is_representable(decision, severity):
    result = SemanticEvaluation(
        decision=decision,
        findings=(finding(severity=severity),),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert result.decision is decision
    assert result.findings[0].severity is severity


@pytest.mark.parametrize(
    ("decision", "findings"),
    [
        (
            SemanticEvaluationDecision.ACCEPT,
            (finding(severity=SemanticFindingSeverity.REPAIRABLE),),
        ),
        (
            SemanticEvaluationDecision.ACCEPT,
            (finding(severity=SemanticFindingSeverity.BLOCKING),),
        ),
        (
            SemanticEvaluationDecision.REPAIR,
            (finding(severity=SemanticFindingSeverity.SUGGESTION),),
        ),
        (
            SemanticEvaluationDecision.REPAIR,
            (
                finding(severity=SemanticFindingSeverity.REPAIRABLE),
                finding(severity=SemanticFindingSeverity.BLOCKING),
            ),
        ),
        (
            SemanticEvaluationDecision.REJECT,
            (finding(severity=SemanticFindingSeverity.REPAIRABLE),),
        ),
        (SemanticEvaluationDecision.REJECT, ()),
    ],
)
def test_invalid_decision_finding_combinations_fail(decision, findings):
    with pytest.raises(ValidationError):
        SemanticEvaluation(
            decision=decision,
            findings=findings,
            rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
        )


def test_findings_support_subtask_and_decomposition_level_references():
    subtask_finding = finding(subtask_id="review")
    decomposition_finding = finding(subtask_id=None)
    result = SemanticEvaluation(
        decision=SemanticEvaluationDecision.REPAIR,
        findings=(subtask_finding, decomposition_finding),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert result.findings[0].subtask_id == "review"
    assert result.findings[1].subtask_id is None


def test_finding_codes_and_categories_are_stable_enums():
    assert SemanticFindingCode.OVERLAPPING_SUBTASKS.value == "overlapping_subtasks"
    assert SemanticFindingCategory.COMPLETENESS.value == "completeness"
    assert SemanticFindingSeverity.BLOCKING.value == "blocking"


def test_rubric_is_versioned_and_contains_representative_guidance():
    assert SEMANTIC_EVALUATION_RUBRIC_VERSION == "1.1"
    for phrase in (
        "Authority and scope",
        "assigned operational responsibility",
        "reasonable alternative decompositions",
        "overlap, duplication, fragmentation",
        "Do not use keyword matching",
        "A missing activity is blocking only when",
        "explicitly required by the assigned task or operationally necessary",
        "task boundary",
        "semantic equivalence before reporting",
        "Do not require procedures",
        "cannot be resolved through local repair",
        "presume it is acceptable unless a demonstrable defect",
        "missing activity is blocking only when",
    ):
        assert phrase in SEMANTIC_EVALUATION_RUBRIC


def test_production_scheduling_activities_are_acceptable_without_procedures():
    """The rubric must not turn activity-level descriptions into procedures."""
    task = TaskReference(
        task_name="Production Scheduling",
        task_description=(
            "Develop a feasible production schedule and resolve scheduling conflicts."
        ),
    )
    decomposition = OperationalDecomposition(
        task=task,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="schedule",
                subtask_name="Develop Production Schedule",
                description=(
                    "Create a feasible production schedule based on reviewed orders, "
                    "inventory, machine capacity, and workforce availability."
                ),
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="conflicts",
                subtask_name="Resolve Scheduling Conflicts",
                description="Identify and address conflicts in the proposed schedule.",
                depends_on=("schedule",),
            ),
        ),
    )
    result = SemanticEvaluation(
        decision=SemanticEvaluationDecision.ACCEPT,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    request = SemanticEvaluationRequest(
        task=task,
        operational_decomposition=decomposition,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert result.decision is SemanticEvaluationDecision.ACCEPT
    assert request.operational_decomposition == decomposition


def test_production_scheduling_scope_does_not_require_feedback_or_criteria():
    """Core activities remain valid without optional implementation detail."""
    assert (
        "procedures, exception handling, feedback, monitoring"
        in SEMANTIC_EVALUATION_RUBRIC
    )
    assert (
        "unless the original task requires that work as a distinct activity"
        in SEMANTIC_EVALUATION_RUBRIC
    )


def test_production_scheduling_scope_preserves_out_of_scope_detection():
    """Monitoring or reporting is not silently treated as required work."""
    assert (
        "Flag an unsupported responsibility only when it materially expands"
        in SEMANTIC_EVALUATION_RUBRIC
    )
    assert (
        "Do not add activities merely to make the decomposition appear"
        in SEMANTIC_EVALUATION_RUBRIC
    )


@pytest.mark.parametrize(
    ("task_description", "include_close"),
    [
        (
            "Plan and coordinate manufacturing production within available resources.",
            False,
        ),
        (
            "Fulfill customer orders end to end, including closing completed orders.",
            True,
        ),
    ],
)
def test_scope_regressions_accept_required_activity_structures(
    task_description, include_close
):
    """Valid alternative structures are representable without procedural detail."""
    task = TaskReference(
        task_name="Production Planning",
        task_description=task_description,
    )
    subtasks = [
        OperationalSubtask(
            sequence_index=1,
            subtask_id="plan",
            subtask_name="Plan production to meet customer demand",
        )
    ]
    if include_close:
        subtasks.append(
            OperationalSubtask(
                sequence_index=2,
                subtask_id="close",
                subtask_name="Close completed customer orders",
                depends_on=("plan",),
            )
        )
    decomposition = OperationalDecomposition(
        task=task, operational_subtasks=tuple(subtasks)
    )
    result = SemanticEvaluation(
        decision=SemanticEvaluationDecision.ACCEPT,
        findings=(),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert len(decomposition.operational_subtasks) == (2 if include_close else 1)
    assert result.decision is SemanticEvaluationDecision.ACCEPT


def test_explicit_order_closure_omission_remains_material():
    task = TaskReference(
        task_name="Order fulfillment",
        task_description="Fulfill orders end to end, including closing completed orders.",
    )
    decomposition = OperationalDecomposition(
        task=task,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="fulfill",
                subtask_name="Coordinate order fulfillment",
            ),
        ),
    )
    finding_result = SemanticEvaluation(
        decision=SemanticEvaluationDecision.REJECT,
        findings=(
            finding(
                code=SemanticFindingCode.INCOMPLETE_COVERAGE,
                category=SemanticFindingCategory.COMPLETENESS,
                severity=SemanticFindingSeverity.BLOCKING,
                subtask_id=None,
            ),
        ),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert decomposition.operational_subtasks[0].subtask_id == "fulfill"
    assert finding_result.findings[0].severity is SemanticFindingSeverity.BLOCKING


@pytest.mark.parametrize(
    ("description", "activity_wording"),
    [
        (
            "Plan and coordinate manufacturing production within constraints.",
            "Tell stakeholders the finalized production plan",
        ),
        (
            "Review orders, capacity, and inventory; create and distribute the final schedule.",
            "Communicate the completed schedule to relevant teams",
        ),
    ],
)
def test_semantic_coverage_accepts_equivalent_activity_wording(
    description, activity_wording
):
    task = TaskReference(
        task_name="Production Scheduling",
        task_description=description,
    )
    decomposition = OperationalDecomposition(
        task=task,
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="communicate",
                subtask_name=activity_wording,
                description=activity_wording + ".",
            ),
        ),
    )
    request = SemanticEvaluationRequest(
        task=task,
        operational_decomposition=decomposition,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert request.operational_decomposition.operational_subtasks[0].description


def test_rubric_preserves_blocking_for_missing_required_activity():
    assert "A missing activity is blocking only when" in SEMANTIC_EVALUATION_RUBRIC
    assert "Reserve reject for blocking findings" in SEMANTIC_EVALUATION_RUBRIC


def test_scope_regression_cases_preserve_acceptance_and_blocking_boundaries():
    accepted = SemanticEvaluation(
        decision=SemanticEvaluationDecision.ACCEPT,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert accepted.decision is SemanticEvaluationDecision.ACCEPT

    out_of_scope = SemanticEvaluation(
        decision=SemanticEvaluationDecision.REJECT,
        findings=(
            finding(
                code=SemanticFindingCode.INCOMPLETE_COVERAGE,
                category=SemanticFindingCategory.POLICY,
                severity=SemanticFindingSeverity.BLOCKING,
                subtask_id=None,
            ),
        ),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    missing_required = SemanticEvaluation(
        decision=SemanticEvaluationDecision.REJECT,
        findings=(
            finding(
                code=SemanticFindingCode.INCOMPLETE_COVERAGE,
                category=SemanticFindingCategory.COMPLETENESS,
                severity=SemanticFindingSeverity.BLOCKING,
            ),
        ),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    assert out_of_scope.findings[0].category is SemanticFindingCategory.POLICY
    assert missing_required.findings[0].severity is SemanticFindingSeverity.BLOCKING


def test_provider_failure_is_not_encoded_as_semantic_rejection():
    class FailingEvaluator:
        def evaluate(self, request):
            raise TimeoutError("evaluator unavailable")

    evaluator = FailingEvaluator()
    assert isinstance(evaluator, SemanticEvaluator)
    with pytest.raises(TimeoutError, match="evaluator unavailable"):
        evaluator.evaluate(evaluation_request())


def test_evaluation_package_imports_without_provider_sdks():
    imported = set(sys.modules)
    importlib.import_module("task_decomposition.evaluation")
    added = set(sys.modules) - imported
    assert not any(
        module_name.startswith(("openai", "google.genai")) for module_name in added
    )
