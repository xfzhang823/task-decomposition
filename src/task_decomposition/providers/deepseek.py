"""Optional DeepSeek adapter using its documented OpenAI-compatible API."""

from dataclasses import dataclass, field
import json
import os

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
from task_decomposition.errors import ProviderConfigurationError, ProviderOutputError
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

DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


@dataclass(frozen=True)
class DeepSeekProviderConfig:
    """Non-secret DeepSeek settings and optional injected credentials."""

    model: str = DEFAULT_DEEPSEEK_MODEL
    api_key: str | None = field(default=None, repr=False)
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    timeout: float | None = None
    max_tokens: int | None = 2000


class DeepSeekDecompositionProvider:
    """DeepSeek-specific adapter; OpenAI compatibility is transport-only."""

    provider_id = "deepseek"

    def __init__(self, config: DeepSeekProviderConfig | None = None, *, client=None):
        self.config = config or DeepSeekProviderConfig()
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
        messages = [
            {
                "role": "system",
                "content": stage_text(prompt, stage_payload(request)),
            },
            {"role": "user", "content": "Return the requested JSON object."},
        ]
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        try:
            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
        except Exception as exc:
            raise_provider_failure("DeepSeek", stage, exc)
        if not content:
            raise ProviderOutputError(
                f"DeepSeek returned no structured output for {stage.value}"
            )
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except Exception as exc:
            raise ProviderOutputError(
                f"DeepSeek returned malformed JSON for {stage.value}"
            ) from exc
        payload = parse_model_payload(
            parsed, schema, provider_name="DeepSeek", stage=stage
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
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError(
                "DeepSeek support requires installing the task-decomposition[deepseek] extra"
            ) from exc
        kwargs = {"base_url": self.config.base_url}
        api_key = self.config.api_key or os.getenv("DEEPSEEK_API_KEY")
        if api_key is not None:
            kwargs["api_key"] = api_key
        if self.config.timeout is not None:
            kwargs["timeout"] = self.config.timeout
        try:
            return OpenAI(**kwargs)
        except Exception as exc:
            raise ProviderConfigurationError(
                "DeepSeek client configuration failed; provide DEEPSEEK_API_KEY or inject a client"
            ) from exc


__all__ = [
    "DEFAULT_DEEPSEEK_BASE_URL",
    "DEFAULT_DEEPSEEK_MODEL",
    "DeepSeekDecompositionProvider",
    "DeepSeekProviderConfig",
]
