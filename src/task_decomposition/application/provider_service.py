"""Clean one-call composition of the two canonical application capabilities."""

from task_decomposition.application.provider_factory import resolve_provider
from task_decomposition.application.task_decomposition import decompose_task
from task_decomposition.application.transformation_decomposition import (
    decompose_transformation,
)
from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    NormalizedAccountingInput,
)
from task_decomposition.contracts.provider import (
    TaskDecompositionRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.contracts.stages import TransformationDecompositionResult
from task_decomposition.errors import MissingAccountingInputError, ProviderOutputError
from task_decomposition.interfaces.provider import DecompositionProvider
from task_decomposition.tracing import TraceLogger, current_tracer


def decompose(
    request: TaskDecompositionRequest,
    provider: DecompositionProvider | str,
    *,
    transformation_context: dict[str, str],
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    model: str | None = None,
    max_output_tokens: int | None = None,
) -> TransformationDecompositionResult:
    """Compose task decomposition and transformation decomposition directly."""
    if accounting_input is None:
        raise MissingAccountingInputError(
            "provider-driven decomposition requires explicit Wave 1 accounting input"
        )
    provider = resolve_provider(
        provider, model=model, max_output_tokens=max_output_tokens
    )
    if not isinstance(provider, DecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the DecompositionProvider protocol"
        )
    tracer = (
        current_tracer() or getattr(provider, "tracer", None) or TraceLogger.from_env()
    )
    with tracer.session(request.request_id):
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
