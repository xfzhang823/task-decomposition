from decimal import Decimal

import pytest
from test_task_transformation_boundaries import (
    BoundaryProvider,
    task_request,
    transform_request,
)

from task_decomposition import (
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SemanticFinding,
    SemanticFindingCategory,
    SemanticFindingCode,
    SemanticFindingSeverity,
    TransformationSemanticCriterion,
    TransformationSemanticEvaluationRequest,
    decompose_task,
    decompose_transformation,
)
from task_decomposition.evaluation.rubric import (
    TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
)


class StubTransformationEvaluator:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def evaluate(self, request):
        self.requests.append(request)
        return self.result


def finding(criterion, message, references=("HAA001",)):
    return SemanticFinding(
        code=SemanticFindingCode.CLARIFY_WORK_DESCRIPTION,
        category=SemanticFindingCategory.COMPLETENESS,
        severity=SemanticFindingSeverity.REPAIRABLE,
        criterion=criterion,
        affected_references=references,
        message=message,
    )


def evaluation(*findings):
    return SemanticEvaluation(
        decision=(
            SemanticEvaluationDecision.REPAIR
            if findings
            else SemanticEvaluationDecision.ACCEPT
        ),
        findings=findings,
        rubric_version=TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )


def run(result):
    provider = BoundaryProvider()
    baseline = decompose_task(task_request(), provider)
    evaluator = StubTransformationEvaluator(result)
    transformed = decompose_transformation(
        transform_request(baseline), provider, evaluator=evaluator
    )
    return transformed, evaluator.requests[0]


@pytest.mark.parametrize(
    ("criterion", "message"),
    [
        (
            TransformationSemanticCriterion.HUMAN_RESPONSIBILITY_COMPLETENESS,
            "Invoice authorization decision effort is not represented in W1.",
        ),
        (
            TransformationSemanticCriterion.HUMAN_RESPONSIBILITY_COMPLETENESS,
            "Constraint adjustment judgment is omitted; only communication is counted.",
        ),
        (
            TransformationSemanticCriterion.DOUBLE_COUNTING,
            "The added verification duplicates retained baseline review effort.",
        ),
        (
            TransformationSemanticCriterion.ACTIVE_HUMAN_EFFORT,
            "The estimate includes passive waiting for autonomous agent execution.",
        ),
        (
            TransformationSemanticCriterion.TASK_BOUNDARY,
            "The activity includes downstream adjudication excluded by the parent contract.",
        ),
    ],
)
def test_transformation_findings_are_exposed_without_mutating_accounting(
    criterion, message
):
    transformed, request = run(evaluation(finding(criterion, message)))

    assert transformed.accounting.w0 == Decimal(100)
    assert transformed.accounting.w1 == Decimal(74)
    assert transformed.semantic_evaluation.findings[0].criterion is criterion
    assert transformed.semantic_evaluation.findings[0].message == message
    assert request.task == transformed.task_decomposition.operational_decomposition.task
    assert (
        request.parent_output_contract
        == transformed.task_decomposition.parent_output_contract
    )
    assert request.accounting == transformed.accounting
    assert isinstance(request, TransformationSemanticEvaluationRequest)


def test_valid_transformation_is_evaluated_once_and_accepted():
    transformed, _ = run(evaluation())

    assert transformed.semantic_evaluation.decision is SemanticEvaluationDecision.ACCEPT
    assert transformed.semantic_evaluation.findings == ()


def test_reasonable_model_generated_occurrence_assumptions_are_not_rejected():
    transformed, request = run(evaluation())

    estimate = request.activity_effort_estimation.activity_effort_estimates[0]
    assert estimate.expected_occurrences_per_parent_output == Decimal(1)
    assert transformed.semantic_evaluation.decision is SemanticEvaluationDecision.ACCEPT
