"""Application capability for reusable task decomposition."""

from task_decomposition.application._provider_stage import (
    call_stage,
    provider_id,
    validate_operational_response,
)
from task_decomposition.application.provider_factory import resolve_provider
from task_decomposition.contracts.effort import EffortQuantity, EffortUnit, TimeBasis
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.provider import (
    OperationalDecompositionRequest,
    TaskDecompositionRequest,
)
from task_decomposition.contracts.stages import (
    BaselineEffortAllocation,
    BaselineEffortEstimation,
    ParentOutputContract,
    TaskDecomposition,
)
from task_decomposition.domain.allocation import allocate_effort
from task_decomposition.errors import (
    ProviderContractValidationError,
    ProviderError,
    ProviderExecutionError,
    ProviderOutputError,
    ProviderSemanticValidationError,
    SemanticEvaluatorContractError,
    SemanticEvaluatorUnavailableError,
)
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SemanticEvaluationRequest,
    SemanticFinding,
)
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION
from task_decomposition.interfaces.provider import TaskDecompositionProvider
from task_decomposition.tracing import TraceLogger, current_tracer


def decompose_task(
    request: TaskDecompositionRequest,
    provider: TaskDecompositionProvider | str,
    *,
    evaluator=None,
    model: str | None = None,
    max_output_tokens: int | None = None,
) -> TaskDecomposition:
    """Generate and validate a reusable task decomposition.

    Transformation context and accounting are deliberately absent. Baseline
    Provider-generated relative effort weights are normalized into baseline
    shares. A measured ``baseline_effort`` is optional; when supplied, the
    same normalized shares are also materialized as absolute allocations.
    """
    provider = resolve_provider(
        provider, model=model, max_output_tokens=max_output_tokens
    )
    if not isinstance(provider, TaskDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TaskDecompositionProvider capability"
        )
    provider_name = provider_id(provider)
    tracer = (
        current_tracer() or getattr(provider, "tracer", None) or TraceLogger.from_env()
    )
    with tracer.session(request.request_id):
        response = call_stage(
            provider_name,
            ProviderStage.OPERATIONAL_DECOMPOSITION,
            provider.generate_operational_decomposition,
            OperationalDecompositionRequest(request=request),
        )
        operational, response = _validate_or_repair_operational(
            provider,
            provider_name,
            request,
            response,
            evaluator=evaluator,
        )
        baseline_estimation = _baseline_effort_estimation(operational)
        allocations = _allocate_baseline(request, operational)
        return TaskDecomposition(
            operational_decomposition=operational,
            parent_output_contract=_parent_output_contract(request, operational),
            baseline_effort_estimation=baseline_estimation,
            baseline_effort_allocations=allocations,
            provenance_refs=operational.provenance_refs
            + response.provenance.references,
            provider_provenance=(response.provenance,),
        )


def _validate_or_repair_operational(
    provider, provider_name, request, response, *, evaluator=None
):
    tracer = current_tracer() or getattr(provider, "tracer", TraceLogger.from_env())
    operational = _prepare_operational(request, validate_operational_response(response))
    requires_relative_weights = all(
        item.relative_effort_weight is not None
        for item in operational.operational_subtasks
    )
    selected = _resolve_evaluator(provider, evaluator)
    evaluation = _evaluate(selected, request, operational, tracer=tracer)
    if evaluation.decision is SemanticEvaluationDecision.ACCEPT:
        return operational, response
    if evaluation.decision is SemanticEvaluationDecision.REJECT:
        raise _semantic_failure(evaluation, response, response, 0)

    repair = getattr(provider, "repair_operational_decomposition", None)
    if not callable(repair):
        raise _semantic_failure(evaluation, response, response, 0, unavailable=True)

    last_response = response
    last_evaluation = evaluation
    for attempt in range(1, 3):
        feedback = _finding_feedback(last_evaluation.findings)

        def do_repair(
            stage_request,
            rejected_response=last_response,
            validation_errors=feedback,
        ):
            return repair(
                stage_request,
                rejected_response=rejected_response,
                validation_errors=validation_errors,
            )

        tracer.repair(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION.value,
            attempt=attempt,
            feedback=feedback,
            rejected_output=last_response.payload,
        )
        repaired = call_stage(
            provider_name,
            ProviderStage.OPERATIONAL_DECOMPOSITION,
            do_repair,
            OperationalDecompositionRequest(request=request),
        )
        operational = _prepare_operational(
            request, validate_operational_response(repaired, attempt=attempt)
        )
        if requires_relative_weights and any(
            item.relative_effort_weight is None
            for item in operational.operational_subtasks
        ):
            raise ProviderContractValidationError(
                "repaired operational decomposition must preserve a positive "
                "relative_effort_weight for every subtask"
            )
        tracer.repair(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION.value,
            attempt=attempt,
            feedback=feedback,
            rejected_output=last_response.payload,
            repaired_output=repaired.payload,
        )
        evaluation = _evaluate(
            selected, request, operational, tracer=tracer, attempt=attempt
        )
        if evaluation.decision is SemanticEvaluationDecision.ACCEPT:
            return operational, repaired
        if evaluation.decision is SemanticEvaluationDecision.REJECT:
            raise _semantic_failure(evaluation, response, repaired, attempt)
        last_response = repaired
        last_evaluation = evaluation

    raise _semantic_failure(last_evaluation, response, last_response, 2)


def _resolve_evaluator(provider, evaluator):
    selected = (
        evaluator if evaluator is not None else getattr(provider, "evaluate", None)
    )
    if not callable(selected) and not callable(getattr(selected, "evaluate", None)):
        raise SemanticEvaluatorUnavailableError(
            "operational semantic evaluation requires an evaluator; inject one "
            "or use a provider with an evaluate() capability"
        )
    return selected


def _evaluate(evaluator, request, operational, *, tracer, attempt=None):
    evaluation_request = SemanticEvaluationRequest(
        task=request.task,
        task_context=request.task_context,
        operational_decomposition=operational,
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
        request_id=request.request_id,
        correlation_id=tracer.current_correlation_id(request.request_id),
    )
    try:
        result = (
            evaluator.evaluate(evaluation_request)
            if hasattr(evaluator, "evaluate")
            else evaluator(evaluation_request)
        )
    except ProviderError:
        raise
    except Exception as exc:
        tracer.emit(
            "evaluator.exception",
            stage="semantic_evaluation",
            attempt=attempt,
            data={"exception_type": type(exc).__name__, "message": str(exc)},
        )
        raise ProviderExecutionError(
            f"semantic evaluator failed during semantic_evaluation: {exc}"
        ) from exc
    try:
        result = SemanticEvaluation.model_validate(result)
        if result.rubric_version != evaluation_request.rubric_version:
            raise ValueError("evaluator returned an unexpected rubric version")
        known_ids = {item.subtask_id for item in operational.operational_subtasks}
        if any(
            finding.subtask_id is not None and finding.subtask_id not in known_ids
            for finding in result.findings
        ):
            raise ValueError("evaluator returned a finding for an unknown subtask")
    except Exception as exc:
        raise SemanticEvaluatorContractError(
            f"semantic evaluator returned an invalid evaluation: {exc}"
        ) from exc
    tracer.validation(
        phase="evaluation",
        stage="semantic_evaluation",
        result=result.decision.value,
        attempt=attempt,
        errors=_finding_feedback(result.findings),
        response=result,
    )
    return result


def _finding_feedback(findings: tuple[SemanticFinding, ...]) -> tuple[str, ...]:
    return tuple(
        f"[{finding.code.value}] [{finding.severity.value}] "
        f"subtask={finding.subtask_id or 'decomposition'}: {finding.message}"
        for finding in findings
    )


def _semantic_failure(
    evaluation, rejected_response, final_response, attempts, *, unavailable=False
):
    feedback = _finding_feedback(evaluation.findings)
    suffix = "; repair capability unavailable" if unavailable else ""
    return ProviderSemanticValidationError(
        f"operational decomposition semantic decision {evaluation.decision.value!r}"
        f"{suffix}: {'; '.join(feedback)}",
        validation_errors=feedback,
        semantic_findings=evaluation.findings,
        rejected_response=rejected_response,
        repair_attempts=attempts,
        final_response=final_response,
    )


def _allocate_baseline(request, operational):
    subtasks = operational.operational_subtasks
    raw_weights = tuple(subtask.relative_effort_weight for subtask in subtasks)
    if any(weight is None for weight in raw_weights):
        return ()
    normalized_parent = EffortQuantity(
        value=1,
        unit=EffortUnit.EFFORT,
        time_basis=TimeBasis.PER_OPERATION,
    )
    normalized = allocate_effort(
        normalized_parent,
        {subtask.subtask_id: weight for subtask, weight in zip(subtasks, raw_weights)},
    )
    absolute = (
        allocate_effort(
            request.baseline_effort,
            {
                subtask.subtask_id: weight
                for subtask, weight in zip(subtasks, raw_weights)
            },
        )
        if request.baseline_effort is not None
        else {}
    )
    return tuple(
        BaselineEffortAllocation(
            subtask_id=subtask.subtask_id,
            effort=absolute.get(subtask.subtask_id),
            weight_ratio=normalized[subtask.subtask_id].value,
            allocation_source="estimated",
        )
        for subtask in subtasks
    )


def _prepare_operational(request, operational):
    """Derive relative weights from validated absolute estimates."""
    estimates = operational.baseline_effort_estimates
    if not estimates:
        return operational
    total = sum(
        estimate.expected_effort_per_parent_output.value for estimate in estimates
    )
    if total == 0:
        return operational.model_copy(
            update={
                "operational_subtasks": tuple(
                    subtask.model_copy(update={"relative_effort_weight": None})
                    for subtask in operational.operational_subtasks
                )
            }
        )
    estimate_by_id = {estimate.subtask_id: estimate for estimate in estimates}
    return operational.model_copy(
        update={
            "operational_subtasks": tuple(
                subtask.model_copy(
                    update={
                        "relative_effort_weight": estimate_by_id[
                            subtask.subtask_id
                        ].expected_effort_per_parent_output.value
                        / total
                    }
                )
                for subtask in operational.operational_subtasks
            )
        }
    )


def _parent_output_contract(request, operational):
    """Resolve additive parent-output metadata without rewriting provider output."""
    if request.parent_output_contract is not None:
        return request.parent_output_contract.model_copy(update={"source": "supplied"})
    if operational.parent_output_contract is not None:
        return operational.parent_output_contract
    return ParentOutputContract(
        output_unit=f"One completed {request.task.task_name}",
        completion_boundary=(
            request.task.task_description or f"Completion of {request.task.task_name}."
        ),
        source="application_inferred",
    )


def _baseline_effort_estimation(operational):
    """Build the public bottom-up estimate record from validated subtasks."""
    estimates = operational.baseline_effort_estimates
    if not estimates:
        return None
    first = estimates[0].expected_effort_per_parent_output
    total = sum(
        estimate.expected_effort_per_parent_output.value for estimate in estimates
    )
    return BaselineEffortEstimation(
        task=operational.task,
        estimates=estimates,
        total_effort_per_parent_output=first.model_copy(update={"value": total}),
        estimation_method="bottom_up",
        provenance_refs=tuple(
            ref for estimate in estimates for ref in estimate.provenance_refs
        ),
    )


__all__ = ["decompose_task"]
