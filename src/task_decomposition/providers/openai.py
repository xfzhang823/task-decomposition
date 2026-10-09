"""Optional OpenAI adapter for the standalone decomposition provider port."""

import json
from dataclasses import dataclass, field
from typing import Any

from task_decomposition.contracts.provenance import ProviderProvenance, ProviderStage
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
from task_decomposition.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderOutputError,
)
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationRequest,
)
from task_decomposition.providers._semantic import (
    SEMANTIC_EVALUATION_STAGE,
    parse_semantic_evaluation,
    semantic_payload,
)
from task_decomposition.providers._shared import request_metadata, stage_payload
from task_decomposition.providers.prompts import (
    ADDED_WORK_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
    RETAIN_REMOVE_PROMPT,
    SEMANTIC_EVALUATION_PROMPT,
)
from task_decomposition.tracing import TraceLogger

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

    def __init__(
        self, config: OpenAIProviderConfig | None = None, *, client=None, tracer=None
    ):
        self.config = config or OpenAIProviderConfig()
        self._client = client if client is not None else self._build_client()
        self.tracer = tracer or TraceLogger.from_env()

    def evaluate(self, request: SemanticEvaluationRequest) -> SemanticEvaluation:
        """Evaluate a complete operational decomposition with OpenAI."""

        with self.tracer.session(request.correlation_id or request.request_id):
            return self._evaluate_inner(request)

    def _evaluate_inner(self, request: SemanticEvaluationRequest):
        payload = semantic_payload(request)
        messages = [
            {"role": "system", "content": SEMANTIC_EVALUATION_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        kwargs = {
            "model": self.config.model,
            "input": messages,
            "text_format": SemanticEvaluation,
        }
        if self.config.max_output_tokens is not None:
            kwargs["max_output_tokens"] = self.config.max_output_tokens
        invocation = self.tracer.invocation(
            provider=self.provider_id,
            stage=SEMANTIC_EVALUATION_STAGE,
            model=self.config.model,
            parameters={
                key: value
                for key, value in kwargs.items()
                if key not in {"input", "text_format"}
            },
            messages=messages,
            schema=SemanticEvaluation,
            kind="evaluation",
            request_id=request.request_id,
        )
        try:
            response = self._client.responses.parse(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
            self.tracer.exception(invocation, exc)
            self.tracer.validation(
                phase="evaluation",
                stage=SEMANTIC_EVALUATION_STAGE,
                result="failure",
                errors=(str(exc),),
            )
            self._raise_openai_evaluation_failure(SEMANTIC_EVALUATION_STAGE, exc)
        parsed = getattr(response, "output_parsed", None)
        self.tracer.response(
            invocation,
            raw=response,
            parsed=parsed,
            stage=SEMANTIC_EVALUATION_STAGE,
        )
        if parsed is None:
            self.tracer.validation(
                phase="evaluation",
                stage=SEMANTIC_EVALUATION_STAGE,
                result="failure",
                errors=("no structured evaluator output",),
            )
            raise ProviderOutputError(
                "OpenAI returned no structured output for semantic_evaluation"
            )
        try:
            evaluation = parse_semantic_evaluation(
                parsed,
                request,
                provider_name="OpenAI",
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
        payload = stage_payload(request)
        request_id, references = request_metadata(request)
        return self._structured_stage(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            request_id=request_id,
            references=references,
            prompt=OPERATIONAL_DECOMPOSITION_PROMPT,
            payload=payload,
            schema=OperationalDecomposition,
        )

    def repair_operational_decomposition(
        self, request, *, rejected_response, validation_errors
    ):
        payload = stage_payload(request)
        payload["rejected_structured_output"] = rejected_response.payload.model_dump(
            mode="json"
        )
        payload["semantic_validation_errors"] = list(validation_errors)
        request_id, references = request_metadata(request)
        return self._structured_stage(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            request_id=request_id,
            references=references,
            prompt=OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
            payload=payload,
            schema=OperationalDecomposition,
        )

    def classify_retain_remove(
        self, request: RetainRemoveClassificationRequest
    ) -> ProviderStageResponse:
        payload = stage_payload(request)
        request_id, references = request_metadata(request)
        return self._structured_stage(
            stage=ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            request_id=request_id,
            references=references,
            prompt=RETAIN_REMOVE_PROMPT,
            payload=payload,
            schema=RetainRemoveClassification,
        )

    def classify_added_work(
        self, request: AddedWorkClassificationRequest
    ) -> ProviderStageResponse:
        payload = stage_payload(request)
        request_id, references = request_metadata(request)
        return self._structured_stage(
            stage=ProviderStage.ADDED_WORK_CLASSIFICATION,
            request_id=request_id,
            references=references,
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
        with self.tracer.session(request_id):
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
        invocation = self.tracer.invocation(
            provider=self.provider_id,
            stage=stage.value,
            model=self.config.model,
            parameters={
                key: value
                for key, value in kwargs.items()
                if key not in {"input", "text_format"}
            },
            messages=messages,
            schema=schema,
            kind="repair"
            if prompt == OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT
            else "generation",
        )
        try:
            response = self._client.responses.parse(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
            self.tracer.exception(invocation, exc)
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
            )
            self._raise_openai_failure(stage, exc)
        self.tracer.response(
            invocation,
            raw=response,
            parsed=getattr(response, "output_parsed", None),
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"no structured output for {stage.value}",),
            )
            raise ProviderOutputError(
                f"OpenAI returned no structured output for {stage.value}"
            )
        try:
            mapped = schema.model_validate(parsed)
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="success",
                response=mapped,
            )
            return mapped
        except Exception as exc:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
                response=parsed,
            )
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
        stage_name = stage.value if hasattr(stage, "value") else stage
        name = type(exc).__name__.lower()
        if "auth" in name or "permission" in name:
            raise ProviderAuthenticationError(
                f"OpenAI authentication failed during {stage_name}"
            ) from exc
        raise ProviderExecutionError(
            f"OpenAI request failed during {stage_name} ({type(exc).__name__})"
        ) from exc

    @staticmethod
    def _raise_openai_evaluation_failure(stage, exc):
        stage_name = stage.value if hasattr(stage, "value") else stage
        name = type(exc).__name__.lower()
        if "auth" in name or "permission" in name:
            raise ProviderAuthenticationError(
                f"OpenAI authentication failed during {stage_name}"
            ) from exc
        if (
            "json" in name
            or "validation" in name
            or "parse" in name
            or "invalid json" in str(exc).lower()
        ):
            raise ProviderOutputError(
                f"OpenAI structured output failed during {stage_name}"
            ) from exc
        raise ProviderExecutionError(
            f"OpenAI request failed during {stage_name} ({type(exc).__name__})"
        ) from exc


__all__ = [
    "DEFAULT_OPENAI_MODEL",
    "OpenAIDecompositionProvider",
    "OpenAIProviderConfig",
]
