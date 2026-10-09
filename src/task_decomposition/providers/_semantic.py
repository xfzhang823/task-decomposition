"""Shared provider-adapter helpers for semantic evaluation."""

import json
from typing import Any

from pydantic import ValidationError

from task_decomposition.errors import ProviderOutputError
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
    SemanticEvaluatorProvenance,
)

SEMANTIC_EVALUATION_STAGE = "semantic_evaluation"


def semantic_payload(request: SemanticEvaluationRequest) -> dict[str, Any]:
    """Serialize the complete evaluator input without provider-specific fields."""

    return {
        "task": request.task.model_dump(mode="json"),
        "task_context": request.task_context,
        "operational_decomposition": request.operational_decomposition.model_dump(
            mode="json"
        ),
        "rubric_version": request.rubric_version,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
    }


def parse_semantic_evaluation(
    raw: Any,
    request: SemanticEvaluationRequest,
    *,
    provider_name: str,
    model_id: str,
) -> SemanticEvaluation:
    """Validate provider output and evaluator-specific cross-field invariants."""

    if raw is None or raw == "":
        raise ProviderOutputError(
            f"{provider_name} returned no structured output for "
            f"{SEMANTIC_EVALUATION_STAGE}"
        )
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        evaluation = SemanticEvaluation.model_validate(raw)
    except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise ProviderOutputError(
            f"{provider_name} structured output failed contract mapping for "
            f"{SEMANTIC_EVALUATION_STAGE}"
        ) from exc

    if evaluation.rubric_version != request.rubric_version:
        raise ProviderOutputError(
            f"{provider_name} returned rubric version "
            f"{evaluation.rubric_version!r}; expected {request.rubric_version!r}"
        )

    subtask_ids = {
        subtask.subtask_id
        for subtask in request.operational_decomposition.operational_subtasks
    }
    unknown_ids = {
        finding.subtask_id
        for finding in evaluation.findings
        if finding.subtask_id is not None
    } - subtask_ids
    if unknown_ids:
        unknown = ", ".join(sorted(unknown_ids))
        raise ProviderOutputError(
            f"{provider_name} returned findings for unknown subtask IDs: {unknown}"
        )

    return evaluation.model_copy(
        update={
            "evaluator_provenance": SemanticEvaluatorProvenance(
                provider_id=provider_name.lower(),
                model_id=model_id,
                request_id=request.request_id,
                correlation_id=request.correlation_id,
            )
        }
    )


__all__ = [
    "SEMANTIC_EVALUATION_STAGE",
    "parse_semantic_evaluation",
    "semantic_payload",
]
