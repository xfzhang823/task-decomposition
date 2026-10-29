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
from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    convert_effort_quantity,
)
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
from task_decomposition.errors import (
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
    ProviderOutputError,
)
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
        calibration, calibration_source = _select_baseline_calibration(
            request, estimation
        )
        support_work = resolve_activity_support_work(
            estimation,
            activities,
            request.accounting_input,
            baseline_effort=calibration,
        )
        support_resolution = None
        estimate_details = ()
        estimation_method = "activity_based"
    else:
        calibration_source = _calibration_source(request, None)
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
    accounting_input = _apply_calibrated_partition(accounting_input, classification)
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
        baseline_calibration_source=calibration_source,
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


def _select_baseline_calibration(request, estimation):
    """Select supplied, bottom-up, or provider baseline calibration once."""
    accounting_input = request.accounting_input
    if isinstance(accounting_input, AbsoluteEffortInput):
        return accounting_input.baseline_human_effort, "supplied"
    bottom_up = request.task_decomposition.baseline_effort_estimation
    if bottom_up is not None:
        return bottom_up.total_effort_per_parent_output, "baseline_bottom_up"
    if estimation.estimated_baseline_effort_per_parent_output is not None:
        return (
            estimation.estimated_baseline_effort_per_parent_output,
            "provider_estimated",
        )
    return None, None


def _calibration_source(request, estimation):
    """Return the calibration source used by this transformation result."""
    if isinstance(request.accounting_input, AbsoluteEffortInput):
        return "supplied"
    if request.task_decomposition.baseline_effort_estimation is not None:
        return "baseline_bottom_up"
    if (
        estimation is not None
        and estimation.estimated_baseline_effort_per_parent_output is not None
    ):
        return "provider_estimated"
    return None


__all__ = ["decompose_transformation"]
