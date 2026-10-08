"""Optional DeepSeek adapter using its documented OpenAI-compatible API."""

import json
import os
from dataclasses import dataclass, field

from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
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
    request_metadata,
    stage_payload,
    stage_text,
)
from task_decomposition.providers.prompts import (
    ADDED_WORK_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
    RETAIN_REMOVE_PROMPT,
)
from task_decomposition.tracing import TraceLogger

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

    def __init__(
        self, config: DeepSeekProviderConfig | None = None, *, client=None, tracer=None
    ):
        self.config = config or DeepSeekProviderConfig()
        self._client = client if client is not None else self._build_client()
        self.tracer = tracer or TraceLogger.from_env()

    def generate_operational_decomposition(
        self, request: OperationalDecompositionRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.OPERATIONAL_DECOMPOSITION,
            OPERATIONAL_DECOMPOSITION_PROMPT,
            OperationalDecomposition,
        )

    def repair_operational_decomposition(
        self, request, *, rejected_response, validation_errors
    ):
        return self._generate(
            request,
            ProviderStage.OPERATIONAL_DECOMPOSITION,
            OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
            OperationalDecomposition,
            repair_context={
                "rejected_structured_output": rejected_response.payload.model_dump(
                    mode="json"
                ),
                "semantic_validation_errors": list(validation_errors),
            },
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

    def _generate(self, request, stage, prompt, schema, repair_context=None):
        request_id, _ = request_metadata(request)
        with self.tracer.session(request_id):
            return self._generate_inner(
                request, stage, prompt, schema, repair_context=repair_context
            )

    def _generate_inner(self, request, stage, prompt, schema, repair_context=None):
        payload = stage_payload(request)
        if repair_context:
            payload.update(repair_context)
        messages = [
            {
                "role": "system",
                "content": stage_text(prompt, payload),
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
        request_id, references = request_metadata(request)
        invocation = self.tracer.invocation(
            provider=self.provider_id,
            stage=stage.value,
            model=self.config.model,
            parameters={
                key: value for key, value in kwargs.items() if key != "messages"
            },
            messages=messages,
            schema=schema,
            kind="repair"
            if prompt == OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT
            else "generation",
            request_id=request_id,
        )
        try:
            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
            self.tracer.exception(invocation, exc)
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
            )
            raise_provider_failure("DeepSeek", stage, exc)
        self.tracer.response(invocation, raw=response)
        if not content:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"no structured output for {stage.value}",),
            )
            raise ProviderOutputError(
                f"DeepSeek returned no structured output for {stage.value}"
            )
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except Exception as exc:
            self.tracer.exception(invocation, exc)
            raise ProviderOutputError(
                f"DeepSeek returned malformed JSON for {stage.value}"
            ) from exc
        try:
            payload = parse_model_payload(
                parsed, schema, provider_name="DeepSeek", stage=stage
            )
        except Exception as exc:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
                response=parsed,
            )
            raise
        self.tracer.validation(
            phase="structural",
            stage=stage.value,
            result="success",
            response=payload,
        )
        self.tracer.emit(
            "llm.parsed",
            provider=self.provider_id,
            stage=stage.value,
            correlation_id=invocation.correlation_id,
            invocation_id=invocation.invocation_id,
            data={"parsed_response": payload},
        )
        return make_stage_response(
            provider_id=self.provider_id,
            model_id=self.config.model,
            stage=stage,
            request_id=request_id,
            references=references,
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
