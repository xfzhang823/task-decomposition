"""Small provider-adapter helpers with no vendor SDK dependencies."""

import json
from collections.abc import Mapping
from typing import Any

from task_transmorph.contracts.provenance import ProviderProvenance, ProviderStage
from task_transmorph.contracts.provider import (
    ActivityEffortEstimationRequest,
    AgenticTaskSynthesisRequest,
    HumanAgentActivityModelingRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
    TaskDecompositionRequest,
    TransformationDecompositionRequest,
    TransformationProposalRequest,
)
from task_transmorph.errors import (
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
)

OUTPUT_TOKEN_STAGES = frozenset(
    {
        ProviderStage.OPERATIONAL_DECOMPOSITION.value,
        ProviderStage.RETAIN_REMOVE_CLASSIFICATION.value,
        ProviderStage.AGENTIC_TASK_SYNTHESIS.value,
        ProviderStage.HUMAN_AGENT_ACTIVITY_MODELING.value,
        ProviderStage.ACTIVITY_EFFORT_ESTIMATION.value,
        "semantic_evaluation",
    }
)


def validate_stage_output_tokens(values: Mapping[Any, Any] | None) -> None:
    if values is None:
        return
    if not isinstance(values, Mapping):
        raise TypeError("stage_output_tokens must be a mapping")
    for stage, budget in values.items():
        stage_name = stage.value if isinstance(stage, ProviderStage) else stage
        if stage_name not in OUTPUT_TOKEN_STAGES:
            raise ValueError(f"unsupported stage_output_tokens key: {stage!r}")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise ValueError(
                f"stage_output_tokens[{stage_name!r}] must be a positive integer"
            )


def stage_output_tokens(
    values: Mapping[Any, int] | None, stage: ProviderStage | str, fallback: int | None
) -> int | None:
    if values is None:
        return fallback
    stage_name = stage.value if isinstance(stage, ProviderStage) else stage
    return values.get(stage_name, values.get(stage, fallback))


def stage_payload(stage_request: Any) -> dict[str, Any]:
    """Serialize the shared host-neutral context for a provider stage."""

    request = stage_request.request
    if isinstance(request, TaskDecompositionRequest):
        context = request.task_context
        payload: dict[str, Any] = {
            "task": request.task.model_dump(mode="json"),
            "task_context": context,
            "parent_output_contract": (
                request.parent_output_contract.model_dump(mode="json")
                if request.parent_output_contract
                else None
            ),
        }
    elif isinstance(
        request, (TransformationDecompositionRequest, TransformationProposalRequest)
    ):
        context = request.transformation_context
        payload = {
            "task": request.task_decomposition.operational_decomposition.task.model_dump(
                mode="json"
            ),
            "transformation_context": context,
        }
    if isinstance(
        stage_request,
        (
            RetainRemoveClassificationRequest,
            AgenticTaskSynthesisRequest,
            HumanAgentActivityModelingRequest,
            ActivityEffortEstimationRequest,
        ),
    ):
        payload["operational_decomposition"] = (
            stage_request.operational_decomposition.model_dump(mode="json")
        )
    if isinstance(
        stage_request,
        (
            AgenticTaskSynthesisRequest,
            HumanAgentActivityModelingRequest,
            ActivityEffortEstimationRequest,
        ),
    ):
        payload["retain_remove_classification"] = (
            stage_request.retain_remove_classification.model_dump(mode="json")
        )
    if isinstance(stage_request, HumanAgentActivityModelingRequest):
        payload["agentic_task_synthesis"] = (
            stage_request.agentic_task_synthesis.model_dump(mode="json")
        )
    if isinstance(stage_request, ActivityEffortEstimationRequest):
        payload["accounting_input"] = getattr(request, "accounting_input", None)
        if payload["accounting_input"] is not None:
            payload["accounting_input"] = payload["accounting_input"].model_dump(
                mode="json"
            )
        payload["agentic_task_synthesis"] = (
            stage_request.agentic_task_synthesis.model_dump(mode="json")
        )
        payload["human_agent_activity_modeling"] = (
            stage_request.human_agent_activity_modeling.model_dump(mode="json")
        )
        payload["parent_output_contract"] = (
            request.task_decomposition.parent_output_contract.model_dump(mode="json")
            if request.task_decomposition.parent_output_contract
            else None
        )
        payload["baseline_effort_estimation"] = (
            request.task_decomposition.baseline_effort_estimation.model_dump(
                mode="json"
            )
            if request.task_decomposition.baseline_effort_estimation
            else None
        )
    return payload


def request_metadata(stage_request: Any):
    request = stage_request.request
    return request.request_id, request.provenance_refs


def output_schema_text(schema) -> str:
    """Render a stage contract as explicit generation guidance."""

    return (
        "OUTPUT JSON SCHEMA (return exactly this object; use these exact field "
        "names and do not add extra keys):\n"
        + json.dumps(
            schema.model_json_schema(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def stage_text(prompt: str, payload: dict[str, Any], *, schema=None) -> str:
    """Combine stage instructions, optional contract schema, and input payload."""

    sections = [prompt]
    if schema is not None:
        sections.append(output_schema_text(schema))
    sections.append(f"INPUT JSON:\n{json.dumps(payload, ensure_ascii=False)}")
    return "\n\n".join(sections)


def make_stage_response(
    *,
    provider_id: str,
    model_id: str,
    stage: ProviderStage,
    request_id: str | None,
    references,
    payload: Any,
) -> ProviderStageResponse:
    return ProviderStageResponse(
        stage=stage,
        payload=payload,
        provenance=ProviderProvenance(
            provider_id=provider_id,
            stage=stage,
            model_id=model_id,
            request_id=request_id,
            references=tuple(references),
        ),
    )


def parse_model_payload(raw: Any, schema, *, provider_name: str, stage: ProviderStage):
    """Map parsed/dict/JSON text to an existing stage contract."""

    if raw is None or raw == "":
        raise ProviderOutputError(
            f"{provider_name} returned no structured output for {stage.value}"
        )
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProviderOutputError(
            f"{provider_name} returned malformed JSON for {stage.value}"
        ) from exc
    try:
        return schema.model_validate(raw)
    except Exception as exc:
        raise ProviderOutputError(
            f"{provider_name} structured output failed contract mapping for "
            f"{stage.value}{_validation_summary(exc)}"
        ) from exc


def _validation_summary(exc: Exception) -> str:
    """Summarize field locations and messages without echoing provider values."""

    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return ""
    try:
        details = []
        for error in errors()[:5]:
            location = ".".join(str(part) for part in error.get("loc", ()))
            details.append(
                f"{location or '<root>'}: {error.get('msg', 'invalid value')}"
            )
    except Exception:  # noqa: BLE001 - diagnostics must not mask the mapping failure
        return ""
    return f" ({'; '.join(details)})" if details else ""


def _stage_name(stage: ProviderStage | str) -> str:
    return stage.value if isinstance(stage, ProviderStage) else stage


def raise_provider_failure(
    provider_name: str, stage: ProviderStage | str, exc: Exception
):
    stage_name = _stage_name(stage)
    name = type(exc).__name__.lower()
    if "auth" in name or "permission" in name or "credential" in name:
        raise ProviderAuthenticationError(
            f"{provider_name} authentication failed during {stage_name}"
        ) from exc
    detail = str(exc).strip()
    raise ProviderExecutionError(
        f"{provider_name} request failed during {stage_name} "
        f"({type(exc).__name__})" + (f": {detail}" if detail else "")
    ) from exc


__all__ = [
    "make_stage_response",
    "output_schema_text",
    "parse_model_payload",
    "raise_provider_failure",
    "request_metadata",
    "stage_payload",
    "stage_text",
]
