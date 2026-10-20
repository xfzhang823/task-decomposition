"""Provider-independent semantic evaluation interface."""

from typing import Protocol, runtime_checkable

from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
)


@runtime_checkable
class SemanticEvaluator(Protocol):
    """Evaluate a complete operational decomposition."""

    def evaluate(self, request: SemanticEvaluationRequest) -> SemanticEvaluation:
        """Return a validated semantic decision for the complete decomposition."""
        ...


__all__ = ["SemanticEvaluator"]
