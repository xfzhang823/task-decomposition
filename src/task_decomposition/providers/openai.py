"""Optional OpenAI adapter for the standalone decomposition provider port."""

from dataclasses import dataclass, field
import json
from typing import Any

from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
from task_decomposition.contracts.provenance import ProviderProvenance, ProviderStage
from task_decomposition.contracts.stages import (
    AddedWorkClassification,
    OperationalDecomposition,
    RetainRemoveClassification,
)
from task_decomposition.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderOutputError,
)
from task_decomposition.providers.prompts import (
    ADDED_WORK_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    RETAIN_REMOVE_PROMPT,
)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class OpenAIProviderConfig:
    """Non-secret OpenAI adapter settings plus optional injected credentials."""

    model: str = DEFAULT_OPENAI_MODEL
    api_key: str | None = field(default=None, repr=False)
    organization: str | None = None
    base_url: str | None = None
    timeout: float | None = None
    max_output_tokens: int | None = 2000


class OpenAIDecompositionProvider:
    """Concrete structured-output provider implementing ``DecompositionProvider``.

    The SDK is imported lazily, so importing the deterministic package and
    using fake/custom providers does not require the ``openai`` extra.
    """

    provider_id = "openai"

    def __init__(self, config: OpenAIProviderConfig | None = None, *, client=None):
        self.config = config or OpenAIProviderConfig()
        self._client = client if client is not None else self._build_client()

    def generate_operational_decomposition(
        self, request: OperationalDecompositionRequest
    ) -> ProviderStageResponse:
        payload = {
            "task": request.request.task.model_dump(mode="json"),
            "transformation_intent": request.request.transformation_intent,
            "context": request.request.context,
        }
        return self._structured_stage(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            request_id=request.request.request_id,
            references=request.request.provenance_refs,
            prompt=OPERATIONAL_DECOMPOSITION_PROMPT,
            payload=payload,
            schema=OperationalDecomposition,
        )

    def classify_retain_remove(
        self, request: RetainRemoveClassificationRequest
    ) -> ProviderStageResponse:
        payload = {
            "task": request.request.task.model_dump(mode="json"),
            "transformation_intent": request.request.transformation_intent,
            "context": request.request.context,
            "operational_decomposition": request.operational_decomposition.model_dump(
                mode="json"
            ),
        }
        return self._structured_stage(
            stage=ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            request_id=request.request.request_id,
            references=request.request.provenance_refs,
            prompt=RETAIN_REMOVE_PROMPT,
            payload=payload,
            schema=RetainRemoveClassification,
        )

    def classify_added_work(
        self, request: AddedWorkClassificationRequest
    ) -> ProviderStageResponse:
        payload = {
            "task": request.request.task.model_dump(mode="json"),
            "transformation_intent": request.request.transformation_intent,
            "context": request.request.context,
            "operational_decomposition": request.operational_decomposition.model_dump(
                mode="json"
            ),
            "retain_remove_classification": request.retain_remove_classification.model_dump(
                mode="json"
            ),
        }
        return self._structured_stage(
            stage=ProviderStage.ADDED_WORK_CLASSIFICATION,
            request_id=request.request.request_id,
            references=request.request.provenance_refs,
            prompt=ADDED_WORK_PROMPT,
            payload=payload,
            schema=AddedWorkClassification,
        )

    def _structured_stage(
        self,
        *,
        stage: ProviderStage,
        request_id: str | None,
        references,
        prompt: str,
        payload: dict[str, Any],
        schema,
    ) -> ProviderStageResponse:
        parsed = self._parse_structured(
            stage=stage,
            prompt=prompt,
            payload=payload,
            schema=schema,
        )
        return ProviderStageResponse(
            stage=stage,
            payload=parsed,
            provenance=ProviderProvenance(
                provider_id=self.provider_id,
                stage=stage,
                model_id=self.config.model,
                request_id=request_id,
                references=tuple(references),
            ),
        )

    def _parse_structured(self, *, stage, prompt, payload, schema):
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        kwargs = {
            "model": self.config.model,
            "input": messages,
            "text_format": schema,
        }
        if self.config.max_output_tokens is not None:
            kwargs["max_output_tokens"] = self.config.max_output_tokens
        try:
            response = self._client.responses.parse(**kwargs)
        except Exception as exc:
            self._raise_openai_failure(stage, exc)
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderOutputError(
                f"OpenAI returned no structured output for {stage.value}"
            )
        try:
            return schema.model_validate(parsed)
        except Exception as exc:
            raise ProviderOutputError(
                f"OpenAI structured output failed contract mapping for {stage.value}"
            ) from exc

    def _build_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError(
                "OpenAI support requires installing the task-decomposition[openai] extra"
            ) from exc
        kwargs = {}
        if self.config.api_key is not None:
            kwargs["api_key"] = self.config.api_key
        if self.config.organization is not None:
            kwargs["organization"] = self.config.organization
        if self.config.base_url is not None:
            kwargs["base_url"] = self.config.base_url
        if self.config.timeout is not None:
            kwargs["timeout"] = self.config.timeout
        try:
            return OpenAI(**kwargs)
        except Exception as exc:
            raise ProviderConfigurationError(
                "OpenAI client configuration failed; provide OPENAI_API_KEY or inject a client"
            ) from exc

    @staticmethod
    def _raise_openai_failure(stage, exc):
        name = type(exc).__name__.lower()
        if "auth" in name or "permission" in name:
            raise ProviderAuthenticationError(
                f"OpenAI authentication failed during {stage.value}"
            ) from exc
        raise ProviderExecutionError(
            f"OpenAI request failed during {stage.value} ({type(exc).__name__})"
        ) from exc


__all__ = [
    "DEFAULT_OPENAI_MODEL",
    "OpenAIDecompositionProvider",
    "OpenAIProviderConfig",
]
