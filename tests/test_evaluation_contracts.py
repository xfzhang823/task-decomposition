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
    assert SEMANTIC_EVALUATION_RUBRIC_VERSION == "1.0"
    for phrase in (
        "Production scheduling",
        "Invoice review",
        "Customer onboarding",
        "Pure outcome",
        "Internal meta-task",
        "overlapping",
        "missing work",
        "Do not use keyword matching",
    ):
        assert phrase in SEMANTIC_EVALUATION_RUBRIC


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
