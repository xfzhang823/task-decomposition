"""Provider-independent semantic evaluation capability."""

from typing import Protocol, runtime_checkable

from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
)


@runtime_checkable
class SemanticEvaluator(Protocol):
    """Evaluate a complete operational decomposition.

    Provider adapters implement this capability. It is intentionally separate
    from ``TaskDecompositionProvider`` so existing providers are not required
    to support semantic evaluation until the integration phase.
    """

    def evaluate(self, request: SemanticEvaluationRequest) -> SemanticEvaluation:
        """Return a validated semantic decision for the complete decomposition."""
        ...


__all__ = ["SemanticEvaluator"]
