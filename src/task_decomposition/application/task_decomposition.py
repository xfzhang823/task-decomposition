"""Application capability for reusable task decomposition."""

from decimal import Decimal

from task_decomposition.application._provider_stage import (
    call_stage,
    provider_id,
    validate_operational_response,
)
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.provider import (
    OperationalDecompositionRequest,
    TaskDecompositionRequest,
)
from task_decomposition.contracts.stages import (
    BaselineEffortAllocation,
    TaskDecomposition,
)
from task_decomposition.errors import (
    MissingEffortAllocationError,
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
from task_decomposition.ports.effort_allocator import (
    EffortAllocationRequest,
    EffortAllocator,
)
from task_decomposition.ports.provider import TaskDecompositionProvider
from task_decomposition.tracing import TraceLogger, current_tracer


def decompose_task(
    request: TaskDecompositionRequest,
    provider: TaskDecompositionProvider,
    *,
    effort_allocator: EffortAllocator | None = None,
    evaluator=None,
) -> TaskDecomposition:
    """Generate and validate a reusable task decomposition.

    Transformation context and accounting are deliberately absent. Baseline
    effort is either supplied through explicit weights, allocated by the
    optional host-neutral allocator, or omitted when the caller wants only an
    operational decomposition.
    """
    if not isinstance(provider, TaskDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TaskDecompositionProvider capability"
        )
    provider_name = provider_id(provider)
    tracer = getattr(provider, "tracer", None) or TraceLogger.from_env()
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
        allocations = _allocate_baseline(
            request, operational, effort_allocator=effort_allocator
        )
        return TaskDecomposition(
            operational_decomposition=operational,
            baseline_effort_allocations=allocations,
            provenance_refs=operational.provenance_refs
            + response.provenance.references,
            provider_provenance=(response.provenance,),
        )


def _validate_or_repair_operational(
    provider, provider_name, request, response, *, evaluator=None
):
    tracer = current_tracer() or getattr(provider, "tracer", TraceLogger.from_env())
    operational = validate_operational_response(response)
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
        try:
            operational = validate_operational_response(repaired)
        except ProviderContractValidationError:
            tracer.validation(
                phase="structural",
                stage=ProviderStage.OPERATIONAL_DECOMPOSITION.value,
                result="failure",
                attempt=attempt,
                errors=("repaired response failed structural validation",),
                response=repaired.payload,
            )
            raise
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


def _allocate_baseline(request, operational, *, effort_allocator):
    subtasks = operational.operational_subtasks
    if effort_allocator is not None:
        if request.baseline_effort is None:
            raise MissingEffortAllocationError(
                "an effort allocator requires explicit baseline_effort"
            )
        result = effort_allocator.allocate(
            EffortAllocationRequest(
                task=operational.task,
                operational_subtasks=subtasks,
                parent_effort=request.baseline_effort,
            )
        )
        by_id = {item.subtask_id: item for item in result.allocations}
        if set(by_id) != {item.subtask_id for item in subtasks}:
            raise MissingEffortAllocationError(
                "effort allocator must return one allocation per subtask"
            )
        total_effort = sum(
            (by_id[subtask.subtask_id].effort.value for subtask in subtasks),
            Decimal(0),
        )
        if total_effort <= 0:
            raise MissingEffortAllocationError(
                "effort allocator must return a positive total effort"
            )
        return tuple(
            BaselineEffortAllocation(
                subtask_id=subtask.subtask_id,
                effort=by_id[subtask.subtask_id].effort,
                weight_ratio=(
                    Decimal(str(by_id[subtask.subtask_id].weight_ratio))
                    if by_id[subtask.subtask_id].weight_ratio is not None
                    else by_id[subtask.subtask_id].effort.value / total_effort
                ),
                provenance_refs=by_id[subtask.subtask_id].provenance_refs,
            )
            for subtask in subtasks
        )
    if request.effort_weights is None and request.baseline_effort is None:
        return ()
    if request.effort_weights is None:
        raise MissingEffortAllocationError(
            "baseline_effort requires explicit effort_weights or an effort_allocator"
        )
    expected = {item.subtask_id for item in subtasks}
    if set(request.effort_weights) != expected:
        raise MissingEffortAllocationError(
            "effort_weights must contain exactly one weight per subtask"
        )
    total = sum(request.effort_weights.values(), Decimal(0))
    if total <= 0:
        raise MissingEffortAllocationError("effort_weights must have a positive total")
    allocated = {}
    if request.baseline_effort is not None:
        allocated = {
            subtask_id: request.baseline_effort.model_copy(
                update={"value": request.baseline_effort.value * weight / total}
            )
            for subtask_id, weight in request.effort_weights.items()
        }
    return tuple(
        BaselineEffortAllocation(
            subtask_id=subtask.subtask_id,
            effort=allocated.get(subtask.subtask_id),
            weight_ratio=request.effort_weights[subtask.subtask_id] / total,
        )
        for subtask in subtasks
    )


__all__ = ["decompose_task"]
