"""Optional DeepSeek adapter using its documented OpenAI-compatible API."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.provider import (
    ActivityEffortEstimationRequest,
    AgenticTaskSynthesisRequest,
    HumanAgentActivityModelingRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
from task_decomposition.contracts.stages import (
    ActivityEffortEstimation,
    AgenticTaskSynthesis,
    HumanAgentActivityModel,
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
    stage_output_tokens,
    stage_payload,
    stage_text,
    validate_stage_output_tokens,
)
from task_decomposition.providers.prompts import (
    ACTIVITY_EFFORT_ESTIMATION_PROMPT,
    AGENTIC_TASK_SYNTHESIS_PROMPT,
    HUMAN_AGENT_ACTIVITY_MODELING_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
    RETAIN_REMOVE_PROMPT,
    SEMANTIC_EVALUATION_PROMPT,
)
from task_decomposition.tracing import TraceLogger

DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _truncation_message(response, stage, output_tokens) -> str | None:
    """Describe a length-truncated response before JSON parsing can obscure it."""

    choices = getattr(response, "choices", None) or ()
    if not choices or getattr(choices[0], "finish_reason", None) != "length":
        return None
    stage_name = stage.value if isinstance(stage, ProviderStage) else stage
    details = [
        f"max_tokens={output_tokens}"
        if output_tokens is not None
        else "max_tokens unset"
    ]
    usage = getattr(response, "usage", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = getattr(completion_details, "reasoning_tokens", None)
    if reasoning_tokens is not None:
        details.append(f"reasoning_tokens={reasoning_tokens}")
    return (
        f"DeepSeek output token limit reached during {stage_name} "
        f"({', '.join(details)}); increase max_output_tokens"
    )


@dataclass(frozen=True)
class DeepSeekProviderConfig:
    """Non-secret DeepSeek settings and optional injected credentials."""

    model: str = DEFAULT_DEEPSEEK_MODEL
    api_key: str | None = field(default=None, repr=False)
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    timeout: float | None = None
    max_tokens: int | None = 16000
    stage_output_tokens: Mapping[str | ProviderStage, int] | None = None

    def __post_init__(self):
        validate_stage_output_tokens(self.stage_output_tokens)

    def output_tokens_for(self, stage: str) -> int | None:
        return stage_output_tokens(self.stage_output_tokens, stage, self.max_tokens)


class DeepSeekDecompositionProvider:
    """DeepSeek-specific adapter; OpenAI compatibility is transport-only."""

    provider_id = "deepseek"

    def __init__(
        self, config: DeepSeekProviderConfig | None = None, *, client=None, tracer=None
    ):
        self.config = config or DeepSeekProviderConfig()
        self._client = client if client is not None else self._build_client()
        self.tracer = tracer or TraceLogger.from_env()

    def evaluate(self, request: SemanticEvaluationRequest) -> SemanticEvaluation:
        """Evaluate a complete operational decomposition with DeepSeek."""

        with self.tracer.session(request.correlation_id or request.request_id):
            payload = semantic_payload(request)
            messages = [
                {
                    "role": "system",
                    "content": stage_text(
                        SEMANTIC_EVALUATION_PROMPT, payload, schema=SemanticEvaluation
                    ),
                },
                {"role": "user", "content": "Return the requested JSON object."},
            ]
            kwargs = {
                "model": self.config.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            output_tokens = self.config.output_tokens_for(SEMANTIC_EVALUATION_STAGE)
            if output_tokens is not None:
                kwargs["max_tokens"] = output_tokens
            invocation = self.tracer.invocation(
                provider=self.provider_id,
                stage=SEMANTIC_EVALUATION_STAGE,
                model=self.config.model,
                parameters={
                    key: value for key, value in kwargs.items() if key != "messages"
                },
                messages=messages,
                schema=SemanticEvaluation,
                kind="evaluation",
                request_id=request.request_id,
            )
            try:
                response = self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
            except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
                self.tracer.exception(invocation, exc)
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=(str(exc),),
                )
                raise_provider_failure("DeepSeek", SEMANTIC_EVALUATION_STAGE, exc)
            self.tracer.response(
                invocation,
                raw=response,
                stage=SEMANTIC_EVALUATION_STAGE,
            )
            truncation = _truncation_message(
                response, SEMANTIC_EVALUATION_STAGE, output_tokens
            )
            if truncation is not None:
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=(truncation,),
                )
                raise ProviderOutputError(truncation)
            if content is None or content == "":
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=("no structured evaluator output",),
                )
                raise ProviderOutputError(
                    "DeepSeek returned no structured output for semantic_evaluation"
                )
            try:
                evaluation = parse_semantic_evaluation(
                    content,
                    request,
                    provider_name="DeepSeek",
                    model_id=self.config.model,
                )
            except Exception as exc:
                self.tracer.validation(
                    phase="evaluation",
                    stage=SEMANTIC_EVALUATION_STAGE,
                    result="failure",
                    errors=(str(exc),),
                    response=content,
                )
                raise
            self.tracer.emit(
                "llm.parsed",
                provider=self.provider_id,
                stage=SEMANTIC_EVALUATION_STAGE,
                correlation_id=invocation.correlation_id,
                data={"parsed_response": evaluation},
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
        messages = [
            {
                "role": "system",
                "content": stage_text(prompt, payload, schema=schema),
            },
            {"role": "user", "content": "Return the requested JSON object."},
        ]
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        output_tokens = self.config.output_tokens_for(stage.value)
        if output_tokens is not None:
            kwargs["max_tokens"] = output_tokens
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
        truncation = _truncation_message(response, stage, output_tokens)
        if truncation is not None:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(truncation,),
            )
            raise ProviderOutputError(truncation)
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
            payload = parse_model_payload(
                content, schema, provider_name="DeepSeek", stage=stage
            )
        except Exception as exc:
            self.tracer.exception(invocation, exc)
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
                response=content,
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
