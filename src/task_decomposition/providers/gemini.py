"""Optional Google Gemini adapter for the standalone provider port."""

import os
from dataclasses import dataclass, field
from typing import Any

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
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
)
from task_decomposition.providers._semantic import (
    SEMANTIC_EVALUATION_STAGE,
    parse_semantic_evaluation,
    semantic_payload,
)
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
    SEMANTIC_EVALUATION_PROMPT,
)
from task_decomposition.tracing import TraceLogger

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

    def __init__(
        self, config: GeminiProviderConfig | None = None, *, client=None, tracer=None
    ):
        self.config = config or GeminiProviderConfig()
        self._client = client if client is not None else self._build_client()
        self.tracer = tracer or TraceLogger.from_env()

    def evaluate(self, request: SemanticEvaluationRequest) -> SemanticEvaluation:
        """Evaluate a complete operational decomposition with Gemini."""

        with self.tracer.session(request.correlation_id or request.request_id):
            payload = semantic_payload(request)
            contents = stage_text(SEMANTIC_EVALUATION_PROMPT, payload)
            config: dict[str, Any] = {
                "response_mime_type": "application/json",
                "response_schema": SemanticEvaluation,
            }
            if self.config.max_output_tokens is not None:
                config["max_output_tokens"] = self.config.max_output_tokens
            invocation = self.tracer.invocation(
                provider=self.provider_id,
                stage=SEMANTIC_EVALUATION_STAGE,
                model=self.config.model,
                parameters={
                    "config": {
                        **config,
                        "response_schema": SemanticEvaluation.model_json_schema(),
                    }
                },
                messages=contents,
                schema=SemanticEvaluation,
                kind="evaluation",
                request_id=request.request_id,
            )
            try:
                response = self._client.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
                self.tracer.exception(invocation, exc)
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=(str(exc),),
                )
                raise_provider_failure("Gemini", SEMANTIC_EVALUATION_STAGE, exc)
            parsed = getattr(response, "parsed", None)
            if parsed is None:
                parsed = getattr(response, "text", None)
            self.tracer.response(
                invocation,
                raw=response,
                parsed=parsed,
                raw_output=getattr(response, "text", None)
                if getattr(response, "text", None) is not None
                else parsed,
                stage=SEMANTIC_EVALUATION_STAGE,
            )
            if parsed is None or parsed == "":
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=("no structured evaluator output",),
                )
                raise ProviderOutputError(
                    "Gemini returned no structured output for semantic_evaluation"
                )
            try:
                evaluation = parse_semantic_evaluation(
                    parsed,
                    request,
                    provider_name="Gemini",
                    model_id=self.config.model,
                )
            except Exception as exc:
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=(str(exc),),
                    response=parsed,
                )
                raise
            self.tracer.validation(
                phase="evaluation",
                stage=SEMANTIC_EVALUATION_STAGE,
                result="success",
                response=evaluation,
            )
            return evaluation

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
        contents = stage_text(prompt, payload)
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if self.config.max_output_tokens is not None:
            config["max_output_tokens"] = self.config.max_output_tokens
        request_id, references = request_metadata(request)
        invocation = self.tracer.invocation(
            provider=self.provider_id,
            stage=stage.value,
            model=self.config.model,
            parameters={"config": config},
            messages=contents,
            schema=schema,
            kind="repair"
            if prompt == OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT
            else "generation",
            request_id=request_id,
        )
        try:
            response = self._client.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
            self.tracer.exception(invocation, exc)
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
            )
            raise_provider_failure("Gemini", stage, exc)
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            parsed = getattr(response, "text", None)
        self.tracer.response(
            invocation,
            raw=response,
            parsed=parsed,
            raw_output=getattr(response, "text", None)
            if getattr(response, "text", None) is not None
            else parsed,
        )
        if parsed is None or parsed == "":
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"no structured output for {stage.value}",),
            )
        try:
            payload = parse_model_payload(
                parsed, schema, provider_name="Gemini", stage=stage
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
