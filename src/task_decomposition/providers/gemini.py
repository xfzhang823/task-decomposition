"""Optional Google Gemini adapter for the standalone provider port."""

from dataclasses import dataclass, field
import os
from typing import Any

from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.stages import (
    AddedWorkClassification,
    OperationalDecomposition,
    RetainRemoveClassification,
)
from task_decomposition.errors import ProviderConfigurationError
from task_decomposition.providers._shared import (
    make_stage_response,
    parse_model_payload,
    raise_provider_failure,
    stage_payload,
    stage_text,
)
from task_decomposition.providers.prompts import (
    ADDED_WORK_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    RETAIN_REMOVE_PROMPT,
)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class GeminiProviderConfig:
    """Non-secret Gemini adapter settings and optional injected credentials."""

    model: str = DEFAULT_GEMINI_MODEL
    api_key: str | None = field(default=None, repr=False)
    max_output_tokens: int | None = 2000


class GeminiDecompositionProvider:
    """Structured-output Gemini adapter implementing ``DecompositionProvider``."""

    provider_id = "gemini"

    def __init__(self, config: GeminiProviderConfig | None = None, *, client=None):
        self.config = config or GeminiProviderConfig()
        self._client = client if client is not None else self._build_client()

    def generate_operational_decomposition(
        self, request: OperationalDecompositionRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.OPERATIONAL_DECOMPOSITION,
            OPERATIONAL_DECOMPOSITION_PROMPT,
            OperationalDecomposition,
        )

    def classify_retain_remove(
        self, request: RetainRemoveClassificationRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            RETAIN_REMOVE_PROMPT,
            RetainRemoveClassification,
        )

    def classify_added_work(
        self, request: AddedWorkClassificationRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.ADDED_WORK_CLASSIFICATION,
            ADDED_WORK_PROMPT,
            AddedWorkClassification,
        )

    def _generate(self, request, stage, prompt, schema):
        contents = stage_text(prompt, stage_payload(request))
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if self.config.max_output_tokens is not None:
            config["max_output_tokens"] = self.config.max_output_tokens
        try:
            response = self._client.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise_provider_failure("Gemini", stage, exc)
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            parsed = getattr(response, "text", None)
        payload = parse_model_payload(
            parsed, schema, provider_name="Gemini", stage=stage
        )
        return make_stage_response(
            provider_id=self.provider_id,
            model_id=self.config.model,
            stage=stage,
            request_id=request.request.request_id,
            references=request.request.provenance_refs,
            payload=payload,
        )

    def _build_client(self):
        try:
            from google import genai
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Gemini support requires installing the task-decomposition[gemini] extra"
            ) from exc
        kwargs = {}
        api_key = self.config.api_key or os.getenv("GEMINI_API_KEY")
        if api_key is not None:
            kwargs["api_key"] = api_key
        try:
            return genai.Client(**kwargs)
        except Exception as exc:
            raise ProviderConfigurationError(
                "Gemini client configuration failed; provide GEMINI_API_KEY or inject a client"
            ) from exc


__all__ = [
    "DEFAULT_GEMINI_MODEL",
    "GeminiDecompositionProvider",
    "GeminiProviderConfig",
]
