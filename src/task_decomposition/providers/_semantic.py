"""Shared provider-adapter helpers for semantic evaluation."""

import json
from typing import Any

from pydantic import ValidationError

from task_decomposition.errors import ProviderOutputError
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
    SemanticEvaluatorProvenance,
    TransformationSemanticEvaluationRequest,
)
from task_decomposition.providers.prompts import (
    SEMANTIC_EVALUATION_PROMPT,
    TRANSFORMATION_SEMANTIC_EVALUATION_PROMPT,
)

SEMANTIC_EVALUATION_STAGE = "semantic_evaluation"


def semantic_evaluation_prompt(request) -> str:
    """Select the rubric prompt for a baseline or transformation request."""

    if isinstance(request, TransformationSemanticEvaluationRequest):
        return TRANSFORMATION_SEMANTIC_EVALUATION_PROMPT
    return SEMANTIC_EVALUATION_PROMPT


def semantic_payload(
    request: SemanticEvaluationRequest | TransformationSemanticEvaluationRequest,
) -> dict[str, Any]:
    """Serialize the complete evaluator input without provider-specific fields."""

    if isinstance(request, TransformationSemanticEvaluationRequest):
        return {
            "task": request.task.model_dump(mode="json"),
            "transformation_context": request.transformation_context,
            "parent_output_contract": (
                request.parent_output_contract.model_dump(mode="json")
                if request.parent_output_contract
                else None
            ),
            "task_decomposition": request.task_decomposition.model_dump(mode="json"),
            "retain_remove_classification": request.retain_remove_classification.model_dump(
                mode="json"
            ),
            "agentic_task_synthesis": request.agentic_task_synthesis.model_dump(
                mode="json"
            ),
            "human_agent_activity_modeling": request.human_agent_activity_modeling.model_dump(
                mode="json"
            ),
            "activity_effort_estimation": request.activity_effort_estimation.model_dump(
                mode="json"
            ),
            "accounting": request.accounting.model_dump(mode="json"),
            "rubric_version": request.rubric_version,
        }

    return {
        "task": request.task.model_dump(mode="json"),
        "task_context": request.task_context,
        "operational_decomposition": request.operational_decomposition.model_dump(
            mode="json"
        ),
        "rubric_version": request.rubric_version,
    }


def parse_semantic_evaluation(
    raw: Any,
    request: SemanticEvaluationRequest | TransformationSemanticEvaluationRequest,
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

    operational = (
        request.task_decomposition.operational_decomposition
        if isinstance(request, TransformationSemanticEvaluationRequest)
        else request.operational_decomposition
    )
    subtask_ids = {subtask.subtask_id for subtask in operational.operational_subtasks}
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
    if isinstance(request, TransformationSemanticEvaluationRequest) and any(
        finding.criterion is None for finding in evaluation.findings
    ):
        raise ProviderOutputError(
            f"{provider_name} transformation findings must identify a criterion"
        )
    if isinstance(request, TransformationSemanticEvaluationRequest) and any(
        not finding.evidence
        or not finding.evidence.strip()
        or not finding.affected_references
        for finding in evaluation.findings
    ):
        raise ProviderOutputError(
            f"{provider_name} transformation findings must include evidence and "
            "affected references"
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
    "semantic_evaluation_prompt",
    "semantic_payload",
]
