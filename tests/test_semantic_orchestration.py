import pytest
from test_provider_application import FakeProvider, request
from test_staged_pipeline import make_operational

from task_decomposition import (
    ProviderContractValidationError,
    ProviderExecutionError,
    ProviderSemanticValidationError,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SemanticEvaluatorContractError,
    SemanticEvaluatorUnavailableError,
    SemanticFinding,
    SemanticFindingCategory,
    SemanticFindingCode,
    SemanticFindingSeverity,
    decompose_task,
)
from task_decomposition.contracts.provenance import ProviderProvenance, ProviderStage
from task_decomposition.contracts.provider import ProviderStageResponse
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION


def finding(subtask_id="sub-1", severity=SemanticFindingSeverity.REPAIRABLE):
    return SemanticFinding(
        subtask_id=subtask_id,
        code=SemanticFindingCode.INSUFFICIENT_OPERATIONAL_SPECIFICITY,
        category=SemanticFindingCategory.ABSTRACTION,
        severity=severity,
        message="Clarify the work performed.",
    )


def evaluation(decision, findings=()):
    return SemanticEvaluation(
        decision=decision,
        findings=findings,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )


class FakeEvaluator:
    def __init__(self, results):
        self.results = iter(results)
        self.requests = []

    def evaluate(self, request):
        self.requests.append(request)
        return next(self.results)


def stage_response(provider, payload):
    return ProviderStageResponse(
        stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
        payload=payload,
        provenance=ProviderProvenance(
            provider_id=provider.provider_id,
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            model_id="test",
            request_id="request-1",
        ),
    )


class RepairingProvider(FakeProvider):
    def __init__(self, repaired):
        super().__init__()
        self.repaired = repaired
        self.repair_calls = []

    def repair_operational_decomposition(
        self, request, *, rejected_response, validation_errors
    ):
        self.repair_calls.append(tuple(validation_errors))
        return stage_response(self, self.repaired)


def test_acceptance_with_suggestion_continues_to_allocation():
    evaluator = FakeEvaluator(
        [
            evaluation(
                SemanticEvaluationDecision.ACCEPT,
                (finding(severity=SemanticFindingSeverity.SUGGESTION),),
            )
        ]
    )
    result = decompose_task(request(), FakeProvider(), evaluator=evaluator)
    assert result.baseline_effort_allocations
    assert len(evaluator.requests) == 1


@pytest.mark.parametrize(
    "name",
    [
        "Develop Production Schedule",
        "Draft Production Schedule",
        "Outline Preliminary Production Schedule",
        "Plan the review approach",
        "Analyze the submitted evidence",
        "Decide whether the invoice meets approval criteria",
        "Prepare the customer communication",
    ],
)
def test_legitimate_cognitive_work_is_not_lexically_rejected(name):
    operational = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(update={"subtask_name": name, "description": None}),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    evaluator = FakeEvaluator([evaluation(SemanticEvaluationDecision.ACCEPT)])
    result = decompose_task(
        request(), FakeProvider(operational=operational), evaluator=evaluator
    )
    assert result.operational_decomposition.operational_subtasks[0].subtask_name == name


def test_repair_revalidates_and_evaluates_complete_repaired_decomposition():
    provider = RepairingProvider(make_operational())
    evaluator = FakeEvaluator(
        [
            evaluation(SemanticEvaluationDecision.REPAIR, (finding(),)),
            evaluation(SemanticEvaluationDecision.ACCEPT),
        ]
    )
    result = decompose_task(request(), provider, evaluator=evaluator)
    assert result.operational_decomposition == make_operational()
    assert len(provider.repair_calls) == 1
    assert len(evaluator.requests) == 2
    assert all(
        req.operational_decomposition == make_operational()
        for req in evaluator.requests
    )
    assert "insufficient_operational_specificity" in provider.repair_calls[0][0]
    assert "subtask=sub-1" in provider.repair_calls[0][0]


def test_reject_does_not_repair():
    provider = RepairingProvider(make_operational())
    evaluator = FakeEvaluator(
        [
            evaluation(
                SemanticEvaluationDecision.REJECT,
                (finding(severity=SemanticFindingSeverity.BLOCKING),),
            )
        ]
    )
    with pytest.raises(ProviderSemanticValidationError) as exc:
        decompose_task(request(), provider, evaluator=evaluator)
    assert not provider.repair_calls
    assert exc.value.semantic_findings[0].subtask_id == "sub-1"


def test_repair_decision_without_repair_hook_fails_explicitly():
    evaluator = FakeEvaluator(
        [evaluation(SemanticEvaluationDecision.REPAIR, (finding(),))]
    )
    with pytest.raises(
        ProviderSemanticValidationError, match="repair capability unavailable"
    ):
        decompose_task(request(), FakeProvider(), evaluator=evaluator)


def test_two_repairs_are_the_maximum():
    provider = RepairingProvider(make_operational())
    evaluator = FakeEvaluator(
        [
            evaluation(SemanticEvaluationDecision.REPAIR, (finding(),)),
            evaluation(SemanticEvaluationDecision.REPAIR, (finding(),)),
            evaluation(SemanticEvaluationDecision.REPAIR, (finding(),)),
        ]
    )
    with pytest.raises(ProviderSemanticValidationError) as exc:
        decompose_task(request(), provider, evaluator=evaluator)
    assert exc.value.repair_attempts == 2
    assert len(provider.repair_calls) == 2
    assert len(evaluator.requests) == 3


def test_unavailable_evaluator_is_explicit():
    class NoEvaluatorProvider(FakeProvider):
        evaluate = None

    with pytest.raises(SemanticEvaluatorUnavailableError):
        decompose_task(request(), NoEvaluatorProvider())


def test_malformed_evaluator_result_is_not_a_semantic_rejection():
    class Malformed:
        def evaluate(self, request):
            return {"decision": "accept"}

    with pytest.raises(SemanticEvaluatorContractError):
        decompose_task(request(), FakeProvider(), evaluator=Malformed())


def test_evaluator_transport_failure_is_not_a_decision():
    class Broken:
        def evaluate(self, request):
            raise TimeoutError("timed out")

    with pytest.raises(ProviderExecutionError):
        decompose_task(request(), FakeProvider(), evaluator=Broken())


def test_structural_failure_precedes_evaluator():
    bad = make_operational().model_copy(
        update={"operational_subtasks": (make_operational().operational_subtasks[0],)}
    )
    # The payload still has a valid Pydantic shape but has a missing dependency target.
    bad = bad.model_copy(
        update={
            "operational_subtasks": (
                bad.operational_subtasks[0].model_copy(
                    update={"depends_on": ("missing",)}
                ),
            )
        }
    )
    evaluator = FakeEvaluator([evaluation(SemanticEvaluationDecision.ACCEPT)])
    provider = FakeProvider(operational=bad)
    with pytest.raises(ProviderContractValidationError):
        decompose_task(request(), provider, evaluator=evaluator)
    assert not evaluator.requests
