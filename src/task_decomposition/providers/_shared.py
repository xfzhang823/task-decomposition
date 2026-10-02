"""Small provider-adapter helpers with no vendor SDK dependencies."""

import json
from typing import Any

from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
from task_decomposition.contracts.provenance import ProviderProvenance, ProviderStage
from task_decomposition.errors import (
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
)


def stage_payload(stage_request: Any) -> dict[str, Any]:
    """Serialize the shared host-neutral context for a provider stage."""

    request = stage_request.request
    payload: dict[str, Any] = {
        "task": request.task.model_dump(mode="json"),
        "transformation_intent": request.transformation_intent,
        "context": request.context,
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


def raise_provider_failure(provider_name: str, stage: ProviderStage, exc: Exception):
    name = type(exc).__name__.lower()
    if "auth" in name or "permission" in name or "credential" in name:
        raise ProviderAuthenticationError(
            f"{provider_name} authentication failed during {stage.value}"
        ) from exc
    raise ProviderExecutionError(
        f"{provider_name} request failed during {stage.value} ({type(exc).__name__})"
    ) from exc


__all__ = [
    "make_stage_response",
    "parse_model_payload",
    "raise_provider_failure",
    "stage_payload",
    "stage_text",
]
