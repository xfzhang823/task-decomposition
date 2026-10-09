"""Small provider-adapter helpers with no vendor SDK dependencies."""

import json
from typing import Any

from task_decomposition.contracts.provenance import ProviderProvenance, ProviderStage
from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
    TaskDecompositionRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.errors import (
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
)


def stage_payload(stage_request: Any) -> dict[str, Any]:
    """Serialize the shared host-neutral context for a provider stage."""

    request = stage_request.request
    if isinstance(request, TaskDecompositionRequest):
        context = request.task_context
        payload: dict[str, Any] = {
            "task": request.task.model_dump(mode="json"),
            "task_context": context,
        }
    elif isinstance(request, TransformationDecompositionRequest):
        context = request.transformation_context
        payload = {
            "task": request.task_decomposition.operational_decomposition.task.model_dump(
                mode="json"
            ),
            "transformation_context": context,
        }
    if isinstance(
        stage_request,
        (RetainRemoveClassificationRequest, AddedWorkClassificationRequest),
    ):
        payload["operational_decomposition"] = (
            stage_request.operational_decomposition.model_dump(mode="json")
        )
    if isinstance(stage_request, AddedWorkClassificationRequest):
        payload["retain_remove_classification"] = (
            stage_request.retain_remove_classification.model_dump(mode="json")
        )
    return payload


def request_metadata(stage_request: Any):
    request = stage_request.request
    return request.request_id, request.provenance_refs


def stage_text(prompt: str, payload: dict[str, Any]) -> str:
    return f"{prompt}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=False)}"


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
        return schema.model_validate(raw)
    except Exception as exc:
        raise ProviderOutputError(
            f"{provider_name} structured output failed contract mapping for {stage.value}"
        ) from exc


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
    raise ProviderExecutionError(
        f"{provider_name} request failed during {stage_name} ({type(exc).__name__})"
    ) from exc


__all__ = [
    "make_stage_response",
    "parse_model_payload",
    "raise_provider_failure",
    "request_metadata",
    "stage_payload",
    "stage_text",
]
