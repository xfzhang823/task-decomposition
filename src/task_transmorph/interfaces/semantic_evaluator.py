"""Provider-independent semantic evaluation interface."""

from typing import Protocol, runtime_checkable

from task_transmorph.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
    TransformationSemanticEvaluationRequest,
)


@runtime_checkable
class SemanticEvaluator(Protocol):
    """Evaluate a complete operational decomposition."""

    def evaluate(
        self,
        request: SemanticEvaluationRequest | TransformationSemanticEvaluationRequest,
    ) -> SemanticEvaluation:
        """Return a validated semantic decision for a complete decomposition."""
        ...


__all__ = ["SemanticEvaluator"]
