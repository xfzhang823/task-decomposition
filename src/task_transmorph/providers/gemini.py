"""Optional Google Gemini adapter for the standalone provider port."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from task_transmorph.contracts.provenance import ProviderStage
from task_transmorph.contracts.provider import (
    ActivityEffortEstimationRequest,
    AgenticTaskSynthesisRequest,
    HumanAgentActivityModelingRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
from task_transmorph.contracts.stages import (
    ActivityEffortEstimation,
    AgenticTaskSynthesis,
    HumanAgentActivityModel,
    OperationalDecomposition,
    RetainRemoveClassification,
)
from task_transmorph.errors import ProviderConfigurationError, ProviderOutputError
from task_transmorph.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
)
from task_transmorph.providers._semantic import (
    SEMANTIC_EVALUATION_STAGE,
    parse_semantic_evaluation,
    semantic_evaluation_prompt,
    semantic_payload,
)
from task_transmorph.providers._shared import (
    make_stage_response,
    parse_model_payload,
    raise_provider_failure,
    request_metadata,
    stage_output_tokens,
    stage_payload,
    stage_text,
    validate_stage_output_tokens,
)
from task_transmorph.providers.prompts import (
    ACTIVITY_EFFORT_ESTIMATION_PROMPT,
    AGENTIC_TASK_SYNTHESIS_PROMPT,
    HUMAN_AGENT_ACTIVITY_MODELING_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
    RETAIN_REMOVE_PROMPT,
)
from task_transmorph.tracing import TraceLogger

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class GeminiProviderConfig:
    """Non-secret Gemini adapter settings and optional injected credentials."""

    model: str = DEFAULT_GEMINI_MODEL
    api_key: str | None = field(default=None, repr=False)
    max_output_tokens: int | None = 2000
    stage_output_tokens: Mapping[str | ProviderStage, int] | None = None

    def __post_init__(self):
        validate_stage_output_tokens(self.stage_output_tokens)

    def output_tokens_for(self, stage: str) -> int | None:
        return stage_output_tokens(
            self.stage_output_tokens, stage, self.max_output_tokens
        )


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
        """Evaluate a complete baseline or transformation with Gemini."""

        with self.tracer.session(request.correlation_id or request.request_id):
            payload = semantic_payload(request)
            contents = stage_text(semantic_evaluation_prompt(request), payload)
            config: dict[str, Any] = {
                "response_mime_type": "application/json",
                "response_json_schema": SemanticEvaluation.model_json_schema(),
            }
            output_tokens = self.config.output_tokens_for(SEMANTIC_EVALUATION_STAGE)
            if output_tokens is not None:
                config["max_output_tokens"] = output_tokens
            invocation = self.tracer.invocation(
                provider=self.provider_id,
                stage=SEMANTIC_EVALUATION_STAGE,
                model=self.config.model,
                parameters={"config": config},
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

    def synthesize_agentic_tasks(
        self, request: AgenticTaskSynthesisRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.AGENTIC_TASK_SYNTHESIS,
            AGENTIC_TASK_SYNTHESIS_PROMPT,
            AgenticTaskSynthesis,
        )

    def model_human_agent_activities(
        self, request: HumanAgentActivityModelingRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.HUMAN_AGENT_ACTIVITY_MODELING,
            HUMAN_AGENT_ACTIVITY_MODELING_PROMPT,
            HumanAgentActivityModel,
        )

    def estimate_activity_effort(
        self, request: ActivityEffortEstimationRequest
    ) -> ProviderStageResponse:
        return self._generate(
            request,
            ProviderStage.ACTIVITY_EFFORT_ESTIMATION,
            ACTIVITY_EFFORT_ESTIMATION_PROMPT,
            ActivityEffortEstimation,
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
            "response_json_schema": schema.model_json_schema(),
        }
        output_tokens = self.config.output_tokens_for(stage.value)
        if output_tokens is not None:
            config["max_output_tokens"] = output_tokens
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
                "Gemini support requires installing the task-transmorph[gemini] extra"
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
