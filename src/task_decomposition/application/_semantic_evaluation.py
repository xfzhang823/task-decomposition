"""Shared application mechanics for semantic-evaluation checkpoints."""

from collections.abc import Callable

from task_decomposition.errors import (
    ProviderError,
    ProviderExecutionError,
    SemanticEvaluatorContractError,
)
from task_decomposition.evaluation.contracts import SemanticEvaluation


def execute_semantic_evaluation(
    evaluator,
    request,
    *,
    tracer,
    stage: str,
    execution_error: str,
    contract_error: str,
    validation: Callable[[SemanticEvaluation], None] | None = None,
    validation_errors: Callable[[SemanticEvaluation], tuple[str, ...]] | None = None,
    attempt: int | None = None,
) -> SemanticEvaluation:
    """Invoke an evaluator and apply shared contract and tracing mechanics."""
    try:
        raw = (
            evaluator.evaluate(request)
            if hasattr(evaluator, "evaluate")
            else evaluator(request)
        )
    except ProviderError:
        raise
    except Exception as exc:
        tracer.emit(
            "evaluator.exception",
            stage=stage,
            attempt=attempt,
            data={"exception_type": type(exc).__name__, "message": str(exc)},
        )
        raise ProviderExecutionError(f"{execution_error}: {exc}") from exc

    try:
        result = SemanticEvaluation.model_validate(raw)
        if result.rubric_version != request.rubric_version:
            raise ValueError("evaluator returned an unexpected rubric version")
        if validation is not None:
            validation(result)
    except Exception as exc:
        raise SemanticEvaluatorContractError(f"{contract_error}: {exc}") from exc

    tracer.validation(
        phase="evaluation",
        stage=stage,
        result=result.decision.value,
        attempt=attempt,
        errors=(
            validation_errors(result)
            if validation_errors is not None
            else tuple(finding.message for finding in result.findings)
        ),
        response=result,
    )
    return result


__all__ = ["execute_semantic_evaluation"]
