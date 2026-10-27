"""Provider-assisted normalized transformation estimation."""

from decimal import Decimal

from task_decomposition.application._provider_stage import provider_id
from task_decomposition.application.provider_factory import resolve_provider
from task_decomposition.application.transformation_decomposition import (
    _assemble_transformation_result,
    _classify_transformation,
)
from task_decomposition.contracts.effort import NormalizedAccountingInput
from task_decomposition.contracts.provider import (
    TransformationDecompositionRequest,
    TransformationProposalRequest,
)
from task_decomposition.contracts.stages import (
    NormalizedWorkEstimate,
    SupportWorkMode,
    TransformationDecompositionResult,
)
from task_decomposition.domain.allocation import DEFAULT_TOLERANCE
from task_decomposition.errors import (
    AccountingInvariantError,
    MissingEffortAllocationError,
    ProviderContractValidationError,
    ProviderOutputError,
)
from task_decomposition.interfaces.provider import TransformationDecompositionProvider
from task_decomposition.tracing import TraceLogger, current_tracer

NORMALIZED_BASELINE_WORK_UNITS = Decimal(100)
NORMALIZED_ESTIMATE_ASSUMPTION = (
    "Baseline work units are a relative-effort normalization for comparison, "
    "not measured hours, capacity, or productivity."
)


def normalized_accounting_from_classification(
    task_decomposition, classification
) -> tuple[NormalizedAccountingInput, tuple[NormalizedWorkEstimate, ...]]:
    """Build normalized accounting from frozen baseline weights and labels."""

    allocations = {
        item.subtask_id: item for item in task_decomposition.baseline_effort_allocations
    }
    subtasks = {
        item.subtask_id: item
        for item in task_decomposition.operational_decomposition.operational_subtasks
    }
    if not allocations or set(allocations) != {
        item.subtask_id for item in classification.classified_subtasks
    }:
        raise MissingEffortAllocationError(
            "normalized transformation estimation requires a complete task baseline allocation"
        )

    estimates = []
    retained = Decimal(0)
    removed = Decimal(0)
    for item in classification.classified_subtasks:
        allocation = allocations[item.subtask_id]
        if allocation.weight_ratio is None:
            raise MissingEffortAllocationError(
                f"subtask {item.subtask_id!r} has no relative-effort weight"
            )
        if not item.rationale or not item.rationale.strip():
            raise ProviderContractValidationError(
                f"subtask {item.subtask_id!r} has no transformation classification rationale"
            )
        baseline = allocation.weight_ratio * NORMALIZED_BASELINE_WORK_UNITS
        if item.classification.value == "retain":
            retained += allocation.weight_ratio
            retained_units, removed_units = baseline, Decimal(0)
        else:
            removed += allocation.weight_ratio
            retained_units, removed_units = Decimal(0), baseline
        estimates.append(
            NormalizedWorkEstimate(
                subtask_id=item.subtask_id,
                subtask_name=subtasks[item.subtask_id].subtask_name,
                baseline_work_units=baseline,
                retained_work_units=retained_units,
                gross_removed_work_units=removed_units,
                estimate_source="model_classification",
                assumption=NORMALIZED_ESTIMATE_ASSUMPTION,
                rationale=item.rationale,
            )
        )

    if abs(retained + removed - Decimal(1)) > DEFAULT_TOLERANCE:
        raise AccountingInvariantError(
            "task baseline relative-effort weights must sum to 1 before normalization"
        )
    return (
        NormalizedAccountingInput(
            retained_work_ratio=retained,
            gross_removed_work_ratio=removed,
        ),
        tuple(estimates),
    )


def estimate_transformation(
    task_decomposition,
    provider,
    *,
    transformation_context: dict[str, str] | None = None,
    model: str | None = None,
    max_output_tokens: int | None = None,
    request_id: str | None = None,
) -> TransformationDecompositionResult:
    """Classify a task and account for it using a normalized 100-unit baseline.

    This is intentionally separate from ``decompose_transformation``. The
    canonical API remains strict and requires host-supplied accounting input;
    this opt-in path derives that input from the completed task allocation and
    the provider's RETAIN/REMOVE classifications.
    """

    provider = resolve_provider(
        provider, model=model, max_output_tokens=max_output_tokens
    )
    if not isinstance(provider, TransformationDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TransformationDecompositionProvider capability"
        )
    proposal_request = TransformationProposalRequest(
        task_decomposition=task_decomposition,
        transformation_context=transformation_context or {},
        request_id=request_id,
    )
    provider_name = provider_id(provider)
    tracer = (
        current_tracer() or getattr(provider, "tracer", None) or TraceLogger.from_env()
    )
    with tracer.session(request_id):
        classification, added, responses = _classify_transformation(
            proposal_request, provider, provider_name
        )
        accounting_input, estimates = normalized_accounting_from_classification(
            task_decomposition, classification
        )
        request = TransformationDecompositionRequest(
            task_decomposition=task_decomposition,
            transformation_context=proposal_request.transformation_context,
            accounting_input=accounting_input,
            support_work_mode=SupportWorkMode.AUTO,
            request_id=request_id,
        )
        return _assemble_transformation_result(
            request,
            provider,
            provider_name,
            classification,
            added,
            responses,
            normalized_work_estimates=estimates,
            estimation_assumptions=(NORMALIZED_ESTIMATE_ASSUMPTION,),
        )


__all__ = [
    "NORMALIZED_BASELINE_WORK_UNITS",
    "NORMALIZED_ESTIMATE_ASSUMPTION",
    "estimate_transformation",
    "normalized_accounting_from_classification",
]
