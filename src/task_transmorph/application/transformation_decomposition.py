"""Evaluate a specified transformation against an existing task decomposition.

This module implements the second half of the library's canonical flow. It
receives an already-validated ``TaskDecomposition`` -- the baseline of finished
human work, ``W0`` -- and answers one question: what happens to that work under
the specified transformation?

The work is split into provider-facing semantic stages and one deterministic
assembly step:

1. Classify every baseline subtask as ``RETAIN`` or ``REMOVE``.
2. Synthesise the agentic tasks that the transformation leaves behind.
3. Model the added human/agent activity the transformation introduces.
4. Estimate the effort carried by those activities, including support work.

Providers only supply semantic judgements. The numeric outcome is produced by
deterministic code: a single baseline calibration is selected, support work is
resolved, and all arithmetic is delegated to
``task_transmorph.domain.accounting``. A semantic evaluation runs last as a
diagnostic checkpoint; its findings never mutate the accounting result.

The baseline is consumed, never regenerated. Transformation decomposition must
not re-derive the operational decomposition it was given.
"""

from task_transmorph.application._provider_stage import (
    call_stage,
    provider_id,
    validate_activity_effort_response,
    validate_agentic_response,
    validate_classification_response,
    validate_human_activity_response,
)
from task_transmorph.application._semantic_evaluation import (
    execute_semantic_evaluation,
)
from task_transmorph.application.activity_effort_estimation import (
    resolve_activity_support_work,
)
from task_transmorph.application.provider_factory import resolve_provider
from task_transmorph.application.staged_pipeline import _run_staged_pipeline
from task_transmorph.contracts.accounting import AccountingMode
from task_transmorph.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    convert_effort_quantity,
)
from task_transmorph.contracts.provenance import ProviderStage
from task_transmorph.contracts.provider import (
    ActivityEffortEstimationRequest,
    AgenticTaskSynthesisRequest,
    HumanAgentActivityModelingRequest,
    RetainRemoveClassificationRequest,
    TransformationDecompositionRequest,
)
from task_transmorph.contracts.stages import TransformationDecompositionResult
from task_transmorph.errors import (
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
    ProviderOutputError,
    SemanticEvaluatorUnavailableError,
)
from task_transmorph.evaluation.contracts import (
    SemanticEvaluationDecision,
    TransformationSemanticEvaluationRequest,
)
from task_transmorph.evaluation.rubric import (
    TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
)
from task_transmorph.interfaces.provider import TransformationDecompositionProvider
from task_transmorph.tracing import TraceLogger, current_tracer


def decompose_transformation(
    request: TransformationDecompositionRequest,
    provider: TransformationDecompositionProvider | str,
    *,
    evaluator=None,
    model: str | None = None,
    max_output_tokens: int | None = None,
) -> TransformationDecompositionResult:
    """Evaluate a transformation against an existing, reusable baseline.

    This is the public entry point for the second half of the canonical flow. It
    accepts a finished baseline (``request.task_decomposition``) plus the
    transformation description, drives the provider through classification,
    synthesis, activity modelling, and effort estimation, then returns a fully
    assembled :class:`TransformationDecompositionResult` with deterministic
    accounting attached.

    Two relationships are preserved in the result:

    * the baseline partition stays intact, ``W0 = retained + gross_removed``;
    * post-transformation effort is ``W1 = retained + resolved_support_work``,
      so gross removal is never reported as a net reduction by itself.

    Accounting may be normalized (``W0 = 1``) or absolute with an explicit
    effort unit and time basis. This function does not infer missing ratios or
    regenerate the supplied baseline.

    Args:
        request: Baseline decomposition, transformation context, and the
            accounting input that says how absolute effort is known.
        provider: A constructed ``TransformationDecompositionProvider``, or one
            of the built-in provider names (``"openai"``, ``"gemini"``,
            ``"deepseek"``).
        evaluator: Optional semantic evaluator for the post-accounting
            checkpoint. When omitted, the provider's own ``evaluate()``
            capability is used; if neither exists the checkpoint fails loudly
            instead of being skipped.
        model: Model override for a named provider. Cannot be combined with an
            already-constructed provider object. If omitted, the provider's
            configured default is used; OpenAI may route transformation
            semantic evaluation through its dedicated evaluator model.
        max_output_tokens: Optional output-token cap applied to every stage of
            this run.

    Returns:
        The transformation result: classification, agentic task synthesis,
        activity model, effort estimation, accounting, provenance, and semantic
        evaluation.

    Raises:
        ProviderOutputError: The provider lacks the required capability.
        MissingAccountingInputError: Neither supplied absolute effort nor a
            bottom-up baseline estimate is available.
        SemanticEvaluatorUnavailableError: No evaluator is available for the
            post-accounting checkpoint.
    """
    provider = resolve_provider(
        provider, model=model, max_output_tokens=max_output_tokens
    )
    if not isinstance(provider, TransformationDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TransformationDecompositionProvider capability"
        )
    provider_name = provider_id(provider)
    tracer = (
        current_tracer() or getattr(provider, "tracer", None) or TraceLogger.from_env()
    )
    with tracer.session(request.request_id):
        return _decompose_transformation(
            request, provider, provider_name, evaluator=evaluator
        )


def _decompose_transformation(request, provider, provider_name, *, evaluator=None):
    """Run the semantic stages first, then assemble the deterministic result."""
    classification, synthesis, activities, estimation, responses = (
        _classify_transformation(request, provider, provider_name)
    )
    return _assemble_transformation_result(
        request,
        provider,
        provider_name,
        classification,
        synthesis,
        activities,
        estimation,
        responses,
        evaluator=evaluator,
    )


def _classify_transformation(request, provider, provider_name):
    """Drive the four semantic provider stages, validating each output in turn.

    The order is fixed because every request embeds the accepted output of the
    previous stage: RETAIN/REMOVE classification, agentic task synthesis,
    human/agent activity modelling, and activity effort estimation. Provider
    responses are untrusted, so each one is validated against the baseline
    before it is passed downstream.

    Returns:
        A tuple of ``(classification, synthesis, activities, estimation,
        responses)`` where ``responses`` keeps the raw provider responses so
        their provenance survives into the final result.
    """
    baseline = request.task_decomposition.operational_decomposition
    classification_response = call_stage(
        provider_name,
        ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
        provider.classify_retain_remove,
        RetainRemoveClassificationRequest(
            request=request,
            operational_decomposition=baseline,
        ),
    )
    classification = validate_classification_response(baseline, classification_response)
    classification = _apply_baseline_allocation(classification, request)
    synthesis_response = call_stage(
        provider_name,
        ProviderStage.AGENTIC_TASK_SYNTHESIS,
        provider.synthesize_agentic_tasks,
        AgenticTaskSynthesisRequest(
            request=request,
            operational_decomposition=baseline,
            retain_remove_classification=classification,
        ),
    )
    synthesis = validate_agentic_response(baseline, classification, synthesis_response)
    activity_response = call_stage(
        provider_name,
        ProviderStage.HUMAN_AGENT_ACTIVITY_MODELING,
        provider.model_human_agent_activities,
        HumanAgentActivityModelingRequest(
            request=request,
            operational_decomposition=baseline,
            retain_remove_classification=classification,
            agentic_task_synthesis=synthesis,
        ),
    )
    activities = validate_human_activity_response(
        baseline, classification, synthesis, activity_response
    )
    estimation_response = call_stage(
        provider_name,
        ProviderStage.ACTIVITY_EFFORT_ESTIMATION,
        provider.estimate_activity_effort,
        ActivityEffortEstimationRequest(
            request=request,
            operational_decomposition=baseline,
            retain_remove_classification=classification,
            agentic_task_synthesis=synthesis,
            human_agent_activity_modeling=activities,
        ),
    )
    estimation = validate_activity_effort_response(
        baseline, activities, estimation_response
    )
    return (
        classification,
        synthesis,
        activities,
        estimation,
        (
            classification_response,
            synthesis_response,
            activity_response,
            estimation_response,
        ),
    )


def _assemble_transformation_result(
    request,
    provider,
    provider_name,
    classification,
    synthesis,
    activities,
    estimation,
    responses,
    *,
    evaluator=None,
    normalized_work_estimates=(),
    estimation_assumptions=(),
):
    """Turn validated stage outputs into the final result and its accounting.

    Support work is resolved from the activity model first, then the baseline
    calibration (``W0``) is chosen once and reused so that every downstream
    value shares a single unit and time basis. The arithmetic itself is
    delegated to ``domain.accounting`` through the staged pipeline. Provenance
    from the baseline and every provider stage is concatenated rather than
    reinterpreted. The semantic evaluation runs after accounting and is
    attached without changing any number.
    """
    (
        classification_response,
        synthesis_response,
        activity_response,
        estimation_response,
    ) = responses
    baseline = request.task_decomposition.operational_decomposition
    calibration, calibration_source = _select_baseline_calibration(request)
    support_work = resolve_activity_support_work(
        estimation,
        activities,
        request.accounting_input,
        baseline_effort=calibration,
    )
    accounting_input = request.accounting_input.model_copy(
        update={"support_work": support_work}
    )
    accounting_input = _apply_calibrated_partition(accounting_input, classification)
    accounting = _run_staged_pipeline(
        baseline,
        classification,
        accounting_input,
        support_work=support_work,
    )
    provider_provenance = (
        *request.task_decomposition.provider_provenance,
        classification_response.provenance,
        *((synthesis_response.provenance,) if synthesis_response else ()),
        *((activity_response.provenance,) if activity_response else ()),
        *((estimation_response.provenance,) if estimation_response else ()),
    )
    portable_refs = tuple(
        ref for provenance in provider_provenance for ref in provenance.references
    )
    result = TransformationDecompositionResult(
        task_decomposition=request.task_decomposition,
        retain_remove_classification=classification,
        agentic_task_synthesis=synthesis,
        human_agent_activity_modeling=activities,
        activity_effort_estimation=estimation,
        baseline_calibration_source=calibration_source,
        accounting=accounting,
        provenance_refs=(
            *request.task_decomposition.provenance_refs,
            *baseline.provenance_refs,
            *classification.provenance_refs,
            *(synthesis.provenance_refs if synthesis else ()),
            *(activities.provenance_refs if activities else ()),
            *(estimation.provenance_refs if estimation else ()),
            *portable_refs,
        ),
        provider_provenance=provider_provenance,
        normalized_work_estimates=normalized_work_estimates,
        estimation_assumptions=estimation_assumptions,
    )
    evaluation = _evaluate_transformation(
        request,
        result,
        provider,
        evaluator=evaluator,
    )
    return result.model_copy(update={"semantic_evaluation": evaluation})


def _evaluate_transformation(request, result, provider, *, evaluator=None):
    """Run the single post-accounting semantic transformation checkpoint."""

    selected = (
        evaluator if evaluator is not None else getattr(provider, "evaluate", None)
    )
    if not callable(selected) and not callable(getattr(selected, "evaluate", None)):
        raise SemanticEvaluatorUnavailableError(
            "transformation semantic evaluation requires an evaluator; inject one "
            "or use a provider with an evaluate() capability"
        )

    tracer = (
        current_tracer() or getattr(provider, "tracer", None) or TraceLogger.from_env()
    )
    evaluation_request = TransformationSemanticEvaluationRequest(
        task=request.task_decomposition.operational_decomposition.task,
        transformation_context=request.transformation_context,
        parent_output_contract=request.task_decomposition.parent_output_contract,
        task_decomposition=request.task_decomposition,
        retain_remove_classification=result.retain_remove_classification,
        agentic_task_synthesis=result.agentic_task_synthesis,
        human_agent_activity_modeling=result.human_agent_activity_modeling,
        activity_effort_estimation=result.activity_effort_estimation,
        accounting=result.accounting,
        rubric_version=TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
        request_id=request.request_id,
        correlation_id=tracer.current_correlation_id(request.request_id),
    )
    evaluation = execute_semantic_evaluation(
        selected,
        evaluation_request,
        tracer=tracer,
        stage="transformation_semantic_evaluation",
        execution_error=(
            "semantic evaluator failed during transformation_semantic_evaluation"
        ),
        contract_error=(
            "transformation semantic evaluator returned an invalid evaluation"
        ),
        validation=_validate_transformation_evaluation,
    )
    if evaluation.decision is not SemanticEvaluationDecision.ACCEPT:
        # This phase is diagnostic-only: findings are exposed, but no repair or
        # output mutation is attempted.
        return evaluation
    return evaluation


def _validate_transformation_evaluation(evaluation):
    """Apply transformation-only evidence and criterion constraints."""
    if any(finding.criterion is None for finding in evaluation.findings):
        raise ValueError("transformation findings must identify a criterion")
    if any(
        not finding.evidence
        or not finding.evidence.strip()
        or not finding.affected_references
        for finding in evaluation.findings
    ):
        raise ValueError(
            "transformation findings must include evidence and affected references"
        )


def _apply_baseline_allocation(classification, request):
    """Attach baseline effort to each classified subtask for accounting.

    In absolute mode the subtask carries a calibrated (or directly allocated)
    effort value; in normalized mode it carries the provider's
    ``weight_ratio`` so accounting can scale it against ``W0``. Subtasks with no
    usable allocation are passed through untouched.
    """
    allocations = {
        item.subtask_id: item
        for item in request.task_decomposition.baseline_effort_allocations
    }
    if not allocations:
        return classification
    accounting_input = getattr(request, "accounting_input", None)
    mode = (
        AccountingMode.ABSOLUTE
        if isinstance(accounting_input, AbsoluteEffortInput)
        else AccountingMode.NORMALIZED
    )
    calibrated = _calibrated_subtask_efforts(request, allocations)
    updated = []
    for item in classification.classified_subtasks:
        allocation = allocations[item.subtask_id]
        if mode is AccountingMode.ABSOLUTE and calibrated is not None:
            updated.append(
                item.model_copy(
                    update={
                        "effort": calibrated[item.subtask_id],
                        "baseline_effort_ratio": None,
                    }
                )
            )
        elif mode is AccountingMode.ABSOLUTE and allocation.effort is not None:
            updated.append(
                item.model_copy(
                    update={
                        "effort": allocation.effort,
                        "baseline_effort_ratio": None,
                    }
                )
            )
        elif mode is AccountingMode.NORMALIZED and allocation.weight_ratio is not None:
            updated.append(
                item.model_copy(
                    update={
                        "effort": None,
                        "baseline_effort_ratio": allocation.weight_ratio,
                    }
                )
            )
        else:
            updated.append(item)
    return classification.model_copy(update={"classified_subtasks": tuple(updated)})


def _calibrated_subtask_efforts(request, allocations):
    """Scale baseline subtask proportions to the authoritative absolute W0."""
    accounting_input = getattr(request, "accounting_input", None)
    if not isinstance(accounting_input, AbsoluteEffortInput):
        return None
    baseline = accounting_input.baseline_human_effort
    estimates = request.task_decomposition.baseline_effort_estimation
    ratios = {}
    if estimates is not None:
        estimate_ids = [estimate.subtask_id for estimate in estimates.estimates]
        if len(estimate_ids) != len(set(estimate_ids)):
            raise MissingAccountingInputError(
                "bottom-up baseline estimates must have unique subtask IDs"
            )
        if set(estimate_ids) != set(allocations):
            raise MissingAccountingInputError(
                "bottom-up baseline estimates must cover every allocated subtask"
            )
        total = estimates.total_effort_per_parent_output
        total = convert_effort_quantity(total, baseline.unit)
        if total.time_basis is not baseline.time_basis:
            raise IncompatibleEffortUnitError(
                "bottom-up baseline and supplied calibration must share a time basis"
            )
        if total.value <= 0:
            raise MissingAccountingInputError(
                "cannot calibrate absolute baseline effort from a zero bottom-up total"
            )
        converted_total = 0
        for estimate in estimates.estimates:
            effort = convert_effort_quantity(
                estimate.expected_effort_per_parent_output, baseline.unit
            )
            if effort.time_basis is not baseline.time_basis:
                raise IncompatibleEffortUnitError(
                    "bottom-up subtask effort and supplied calibration must share a time basis"
                )
            converted_total += effort.value
            ratios[estimate.subtask_id] = effort.value / total.value
        if converted_total != total.value:
            raise MissingAccountingInputError(
                "bottom-up baseline total must equal the sum of subtask effort"
            )
    else:
        ratios = {
            subtask_id: allocation.weight_ratio
            for subtask_id, allocation in allocations.items()
            if allocation.weight_ratio is not None
        }
    if set(ratios) != set(allocations):
        return None
    return {
        subtask_id: EffortQuantity(
            value=baseline.value * ratio,
            unit=baseline.unit,
            time_basis=baseline.time_basis,
        )
        for subtask_id, ratio in ratios.items()
    }


def _apply_calibrated_partition(accounting_input, classification):
    """Use classified calibrated subtask effort as the absolute W0 partition."""
    if not isinstance(accounting_input, AbsoluteEffortInput):
        return accounting_input
    items = classification.classified_subtasks
    if not items or any(item.effort is None for item in items):
        return accounting_input
    retained = sum(
        (item.effort.value for item in items if item.classification.value == "retain"),
        0,
    )
    removed = sum(
        (item.effort.value for item in items if item.classification.value == "remove"),
        0,
    )
    return accounting_input.model_copy(
        update={
            "retained_human_work": EffortQuantity(
                value=retained,
                unit=accounting_input.baseline_human_effort.unit,
                time_basis=accounting_input.baseline_human_effort.time_basis,
            ),
            "gross_removed_work": EffortQuantity(
                value=removed,
                unit=accounting_input.baseline_human_effort.unit,
                time_basis=accounting_input.baseline_human_effort.time_basis,
            ),
        }
    )


def _select_baseline_calibration(request):
    """Select supplied, bottom-up, or provider baseline calibration once."""
    accounting_input = request.accounting_input
    if isinstance(accounting_input, AbsoluteEffortInput):
        return accounting_input.baseline_human_effort, "supplied"
    bottom_up = request.task_decomposition.baseline_effort_estimation
    if bottom_up is not None:
        return bottom_up.total_effort_per_parent_output, "baseline_bottom_up"
    raise MissingAccountingInputError(
        "activity-based transformation requires supplied or bottom-up baseline effort"
    )


__all__ = ["decompose_transformation"]
