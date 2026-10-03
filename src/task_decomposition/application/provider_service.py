"""Clean one-call composition of the two canonical application capabilities."""

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    NormalizedAccountingInput,
)
from task_decomposition.contracts.provider import (
    TaskDecompositionRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.contracts.stages import TransformationDecompositionResult
from task_decomposition.application.task_decomposition import decompose_task
from task_decomposition.application.transformation_decomposition import (
    decompose_transformation,
)
from task_decomposition.errors import MissingAccountingInputError, ProviderOutputError
from task_decomposition.ports.provider import DecompositionProvider


def decompose(
    request: TaskDecompositionRequest,
    provider: DecompositionProvider,
    *,
    transformation_context: dict[str, str],
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
) -> TransformationDecompositionResult:
    """Compose task decomposition and transformation decomposition directly."""
    if accounting_input is None:
        raise MissingAccountingInputError(
            "provider-driven decomposition requires explicit Wave 1 accounting input"
        )
    if not isinstance(provider, DecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the DecompositionProvider protocol"
        )
    task = decompose_task(request, provider)
    return decompose_transformation(
        TransformationDecompositionRequest(
            task_decomposition=task,
            transformation_context=transformation_context,
            accounting_input=accounting_input,
            request_id=request.request_id,
            provenance_refs=request.provenance_refs,
        ),
        provider,
    )


__all__ = ["decompose"]
