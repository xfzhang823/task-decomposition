"""Clean one-call composition of the two canonical application capabilities."""

from task_transmorph.application.provider_factory import resolve_provider
from task_transmorph.application.task_decomposition import decompose_task
from task_transmorph.application.transformation_decomposition import (
    decompose_transformation,
)
from task_transmorph.contracts.effort import (
    AbsoluteEffortInput,
    NormalizedAccountingInput,
)
from task_transmorph.contracts.provider import (
    TaskDecompositionRequest,
    TransformationDecompositionRequest,
)
from task_transmorph.contracts.stages import TransformationDecompositionResult
from task_transmorph.errors import MissingAccountingInputError, ProviderOutputError
from task_transmorph.interfaces.provider import DecompositionProvider
from task_transmorph.tracing import TraceLogger, current_tracer


def decompose(
    request: TaskDecompositionRequest,
    provider: DecompositionProvider | str,
    *,
    transformation_context: dict[str, str],
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    model: str | None = None,
    max_output_tokens: int | None = None,
) -> TransformationDecompositionResult:
    """Run the canonical baseline-to-transformation flow in one call.

    ``decompose`` first creates a reusable baseline with ``decompose_task``
    and then evaluates the requested transformation with
    ``decompose_transformation``. Unlike ``estimate_transformation``, this
    strict composition requires the caller to provide the authoritative
    absolute or normalized accounting input.

    Args:
        request: Task identity, description, context, and optional parent
            output contract used to create the baseline.
        provider: A provider object or ``"openai"``, ``"gemini"``, or
            ``"deepseek"``.
        transformation_context: The requested change to apply to the frozen
            baseline; it does not change the task identity.
        accounting_input: Absolute or normalized accounting basis. The
            deterministic accounting domain uses this input for W0/W1.
        model: Optional model override when ``provider`` is a provider name.
            If omitted, the provider's configured default is used.
        max_output_tokens: Optional output-token cap for provider stages.

    Returns:
        A ``TransformationDecompositionResult`` containing the frozen
        baseline, transformation stages, accounting impact, and provenance.

    Raises:
        MissingAccountingInputError: If ``accounting_input`` is ``None``.
        ProviderOutputError: If the selected provider lacks both capabilities.

    The provider object is not mutated. A model or token override cannot be
    combined with an already-constructed provider object.
    """
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
