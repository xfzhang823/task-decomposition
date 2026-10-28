"""Application capability for evaluating a fixed task decomposition."""

from task_decomposition.application._provider_stage import (
    call_stage,
    provider_id,
    validate_activity_effort_response,
    validate_added_response,
    validate_agentic_response,
    validate_classification_response,
    validate_human_activity_response,
)
from task_decomposition.application.activity_effort_estimation import (
    resolve_activity_support_work,
)
from task_decomposition.application.added_work_estimation import (
    resolve_support_work_with_details,
)
from task_decomposition.application.provider_factory import resolve_provider
from task_decomposition.application.staged_pipeline import _run_staged_pipeline
from task_decomposition.contracts.accounting import AccountingMode
from task_decomposition.contracts.effort import AbsoluteEffortInput
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.provider import (
    ActivityEffortEstimationRequest,
    AddedWorkClassificationRequest,
    AgenticTaskSynthesisRequest,
    HumanAgentActivityModelingRequest,
    RetainRemoveClassificationRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.contracts.stages import (
    AddedWorkClassification,
    TransformationDecompositionResult,
)
from task_decomposition.errors import ProviderOutputError
from task_decomposition.interfaces.provider import (
    ActivityEffortEstimationProvider,
    AgenticTaskSynthesisProvider,
    HumanAgentActivityModelingProvider,
    TransformationDecompositionProvider,
)
from task_decomposition.tracing import TraceLogger, current_tracer


def decompose_transformation(
    request: TransformationDecompositionRequest,
    provider: TransformationDecompositionProvider | str,
    *,
    model: str | None = None,
    max_output_tokens: int | None = None,
) -> TransformationDecompositionResult:
    """Classify and account for a supplied, reusable task decomposition."""
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
        return _decompose_transformation(request, provider, provider_name)


def _decompose_transformation(request, provider, provider_name):
    classification, synthesis, activities, estimation, added, responses = (
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
        added,
        responses,
    )


def _classify_transformation(request, provider, provider_name):
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
    synthesis = None
    synthesis_response = None
    if isinstance(provider, AgenticTaskSynthesisProvider):
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
        synthesis = validate_agentic_response(
            baseline, classification, synthesis_response
        )
    activities = None
    activity_response = None
    if synthesis is not None and isinstance(
        provider, HumanAgentActivityModelingProvider
    ):
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
    estimation = None
    estimation_response = None
    activity_based = (
        synthesis is not None
        and activities is not None
        and isinstance(provider, ActivityEffortEstimationProvider)
    )
    if activity_based:
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
        added_response = None
        added = AddedWorkClassification(task=baseline.task, added_work_rows=())
    else:
        estimation_response = None
    if not activity_based:
        added_response = call_stage(
            provider_name,
            ProviderStage.ADDED_WORK_CLASSIFICATION,
            provider.classify_added_work,
            AddedWorkClassificationRequest(
                request=request,
                operational_decomposition=baseline,
                retain_remove_classification=classification,
            ),
        )
        added = validate_added_response(baseline, classification, added_response)
    return (
        classification,
        synthesis,
        activities,
        estimation,
        added,
        (
            classification_response,
            synthesis_response,
            activity_response,
            estimation_response,
            added_response,
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
    added,
    responses,
    *,
    normalized_work_estimates=(),
    estimation_assumptions=(),
):
    (
        classification_response,
        synthesis_response,
        activity_response,
        estimation_response,
        added_response,
    ) = responses
    baseline = request.task_decomposition.operational_decomposition
    if estimation is not None:
        support_work = resolve_activity_support_work(
            estimation,
            activities,
            request.accounting_input,
        )
        support_resolution = None
        estimate_details = ()
        estimation_method = "activity_based"
    else:
        support_work, support_resolution, estimate_details = (
            resolve_support_work_with_details(
                added,
                classification,
                request.accounting_input,
                mode=request.support_work_mode,
            )
        )
        estimation_method = "legacy_reference_based"
    accounting_input = request.accounting_input.model_copy(
        update={"support_work": support_work}
    )
    accounting = _run_staged_pipeline(
        baseline,
        classification,
        added,
        accounting_input,
        support_work=support_work,
    )
    provider_provenance = (
        *request.task_decomposition.provider_provenance,
        classification_response.provenance,
        *((synthesis_response.provenance,) if synthesis_response else ()),
        *((activity_response.provenance,) if activity_response else ()),
        *((estimation_response.provenance,) if estimation_response else ()),
        *((added_response.provenance,) if added_response else ()),
    )
    portable_refs = tuple(
        ref for provenance in provider_provenance for ref in provenance.references
    )
    return TransformationDecompositionResult(
        task_decomposition=request.task_decomposition,
        retain_remove_classification=classification,
        agentic_task_synthesis=synthesis,
        human_agent_activity_modeling=activities,
        activity_effort_estimation=estimation,
        estimation_method=estimation_method,
        added_work_classification=added,
        accounting=accounting,
        provenance_refs=(
            *request.task_decomposition.provenance_refs,
            *baseline.provenance_refs,
            *classification.provenance_refs,
            *(synthesis.provenance_refs if synthesis else ()),
            *(activities.provenance_refs if activities else ()),
            *added.provenance_refs,
            *(estimation.provenance_refs if estimation else ()),
            *portable_refs,
        ),
        provider_provenance=provider_provenance,
        support_work_resolution=support_resolution,
        added_work_estimate_details=estimate_details,
        normalized_work_estimates=normalized_work_estimates,
        estimation_assumptions=estimation_assumptions,
    )


def _apply_baseline_allocation(classification, request):
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
    updated = []
    for item in classification.classified_subtasks:
        allocation = allocations[item.subtask_id]
        if mode is AccountingMode.ABSOLUTE and allocation.effort is not None:
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


__all__ = ["decompose_transformation"]
