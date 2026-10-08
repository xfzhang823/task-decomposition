"""Application capability for evaluating a fixed task decomposition."""

from task_decomposition.application._provider_stage import (
    call_stage,
    provider_id,
    validate_added_response,
    validate_classification_response,
)
from task_decomposition.application.staged_pipeline import run_staged_pipeline
from task_decomposition.contracts.accounting import AccountingMode
from task_decomposition.contracts.effort import AbsoluteEffortInput
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    RetainRemoveClassificationRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.contracts.stages import (
    TransformationDecompositionResult,
)
from task_decomposition.errors import ProviderOutputError
from task_decomposition.ports.provider import TransformationDecompositionProvider
from task_decomposition.tracing import TraceLogger


def decompose_transformation(
    request: TransformationDecompositionRequest,
    provider: TransformationDecompositionProvider,
) -> TransformationDecompositionResult:
    """Classify and account for a supplied, reusable task decomposition."""
    if not isinstance(provider, TransformationDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TransformationDecompositionProvider capability"
        )
    provider_name = provider_id(provider)
    tracer = getattr(provider, "tracer", None) or TraceLogger.from_env()
    with tracer.session(request.request_id):
        return _decompose_transformation(request, provider, provider_name)


def _decompose_transformation(request, provider, provider_name):
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
    staged = run_staged_pipeline(
        baseline,
        classification,
        added,
        request.accounting_input,
        support_work_override=request.accounting_input.support_work,
    )
    provider_provenance = (
        *request.task_decomposition.provider_provenance,
        classification_response.provenance,
        added_response.provenance,
    )
    portable_refs = tuple(
        ref for provenance in provider_provenance for ref in provenance.references
    )
    return TransformationDecompositionResult(
        task_decomposition=request.task_decomposition,
        retain_remove_classification=staged.retain_remove_classification,
        added_work_classification=staged.added_work_classification,
        accounting=staged.accounting,
        provenance_refs=(
            *request.task_decomposition.provenance_refs,
            *staged.provenance_refs,
            *portable_refs,
        ),
        provider_provenance=provider_provenance,
    )


def _apply_baseline_allocation(classification, request):
    allocations = {
        item.subtask_id: item
        for item in request.task_decomposition.baseline_effort_allocations
    }
    if not allocations:
        return classification
    mode = (
        AccountingMode.ABSOLUTE
        if isinstance(request.accounting_input, AbsoluteEffortInput)
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
