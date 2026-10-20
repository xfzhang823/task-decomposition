"""Optional OpenAI adapter for the standalone decomposition provider port."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
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
from task_decomposition.providers._shared import (
    raise_provider_failure,
    request_metadata,
    stage_output_tokens,
    stage_payload,
    validate_stage_output_tokens,
)
from task_decomposition.providers.prompts import (
    ADDED_WORK_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
    RETAIN_REMOVE_PROMPT,
    SEMANTIC_EVALUATION_PROMPT,
)
from task_decomposition.tracing import TraceLogger

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _semantic_parse_diagnostics(exc: BaseException) -> dict[str, Any]:
    """Extract safe decision/severity clues from a structured-output failure."""
    diagnostics: dict[str, Any] = {"exception_type": type(exc).__name__}
    decisions: set[str] = set()
    severities: set[str] = set()

    def inspect(value: Any) -> None:
        """Collect decision/severity strings from nested validator error entries."""
        if isinstance(value, Mapping):
            decision = value.get("decision")
            if isinstance(decision, str):
                decisions.add(decision)
            severity = value.get("severity")
            if isinstance(severity, str):
                severities.add(severity)
            findings = value.get("findings")
            if isinstance(findings, (list, tuple)):
                for finding in findings:
                    inspect(finding)
            for key in ("input", "ctx", "error"):
                if key in value:
                    inspect(value[key])
        elif isinstance(value, (list, tuple)):
            for item in value:
                inspect(item)

    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            inspect(errors())
        except Exception as diagnostic_error:  # noqa: BLE001
            diagnostics["diagnostic_error_type"] = type(diagnostic_error).__name__
    if decisions:
        diagnostics["decisions"] = sorted(decisions)
    if severities:
        diagnostics["finding_severities"] = sorted(severities)

    provider_details = {}
    for name in ("status_code", "body", "response", "raw_response"):
        value = getattr(exc, name, None)
        if value is None:
            continue
        if name == "status_code" and isinstance(value, (int, str)):
            provider_details[name] = value
            continue
        if isinstance(value, Mapping):
            safe = {
                key: value[key]
                for key in ("status", "code", "type", "message", "detail")
                if key in value and isinstance(value[key], (bool, int, float, str))
            }
            if safe:
                provider_details[name] = safe
    if provider_details:
        diagnostics["provider_details"] = provider_details
    return diagnostics


def _strict_text_format(schema):
    """Build the Responses API format using the installed SDK conversion."""
    from openai.lib._pydantic import to_strict_json_schema

    return {
        "type": "json_schema",
        "name": schema.__name__,
        "strict": True,
        "schema": to_strict_json_schema(schema),
    }


def _provider_text_format(stage, schema):
    """Use numeric OpenAI schemas for Decimal fields rejected by the API."""
    text_format = _strict_text_format(schema)
    definitions = text_format["schema"]["$defs"]
    if stage is ProviderStage.OPERATIONAL_DECOMPOSITION:
        definitions["OperationalSubtask"]["properties"]["relative_effort_weight"] = {
            "anyOf": [
                {"exclusiveMinimum": 0, "type": "number"},
                {"type": "null"},
            ]
        }
    elif stage is ProviderStage.RETAIN_REMOVE_CLASSIFICATION:
        definitions["ClassifiedSubtask"]["properties"]["baseline_effort_ratio"] = {
            "anyOf": [
                {"minimum": 0, "type": "number"},
                {"type": "null"},
            ]
        }
        definitions["EffortQuantity"]["properties"]["value"] = {
            "minimum": 0,
            "type": "number",
        }
    elif stage is ProviderStage.ADDED_WORK_CLASSIFICATION:
        definitions["SupportWorkInput"]["properties"]["value"] = {
            "minimum": 0,
            "type": "number",
        }
        item = definitions["AddedWorkItem"]
        compact_item_fields = {
            "description",
            "depends_on_subtask_ids",
            "sequence_index",
            "provenance_refs",
        }
        for field in compact_item_fields:
            item["properties"].pop(field, None)
        item["required"] = [
            field for field in item["required"] if field not in compact_item_fields
        ]
        estimate = definitions["AddedWorkEstimate"]
        estimate["properties"].pop("provenance_refs", None)
        estimate["required"].remove("provenance_refs")
    return text_format


def _canonicalize_operational_weights(payload):
    """Convert provider numeric weights to the canonical Decimal representation."""
    if not isinstance(payload, dict):
        return payload
    for subtask in payload.get("operational_subtasks", ()):
        if not isinstance(subtask, dict):
            continue
        weight = subtask.get("relative_effort_weight")
        if weight is not None:
            subtask["relative_effort_weight"] = Decimal(str(weight))
    return payload


def _canonicalize_transformation_values(stage, payload):
    """Convert stage-boundary numeric values to canonical Decimal values."""
    if not isinstance(payload, dict):
        return payload
    if stage is ProviderStage.RETAIN_REMOVE_CLASSIFICATION:
        for subtask in payload.get("classified_subtasks", ()):
            if not isinstance(subtask, dict):
                continue
            ratio = subtask.get("baseline_effort_ratio")
            if ratio is not None:
                subtask["baseline_effort_ratio"] = Decimal(str(ratio))
            effort = subtask.get("effort")
            if isinstance(effort, dict) and effort.get("value") is not None:
                effort["value"] = Decimal(str(effort["value"]))
    return payload


def _response_detail(value, key):
    """Read one field from a dict-or-object response detail."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _response_refusal(response):
    """Return the first refusal message in a Responses API result, if any."""
    for output in getattr(response, "output", ()) or ():
        for content in getattr(output, "content", ()) or ():
            if getattr(content, "type", None) == "refusal":
                return getattr(content, "refusal", None) or "provider refusal"
    return None


@dataclass(frozen=True)
class OpenAIProviderConfig:
    """Non-secret OpenAI adapter settings plus optional injected credentials."""

    model: str = DEFAULT_OPENAI_MODEL
    api_key: str | None = field(default=None, repr=False)
    organization: str | None = None
    base_url: str | None = None
    timeout: float | None = None
    max_output_tokens: int | None = 2000
    stage_output_tokens: Mapping[str | ProviderStage, int] | None = None

    def __post_init__(self):
        """Validate stage-scoped output-token overrides."""
        validate_stage_output_tokens(self.stage_output_tokens)

    def output_tokens_for(self, stage: str) -> int | None:
        """Resolve the output-token cap for one stage."""
        return stage_output_tokens(
            self.stage_output_tokens, stage, self.max_output_tokens
        )


class OpenAIDecompositionProvider:
    """Concrete structured-output provider implementing ``DecompositionProvider``.

    The SDK is imported lazily, so importing the deterministic package and
    using fake/custom providers does not require the ``openai`` extra.
    """

    provider_id = "openai"

    def __init__(
        self, config: OpenAIProviderConfig | None = None, *, client=None, tracer=None
    ):
        """Store config; use an injected client and tracer when provided."""
        self.config = config or OpenAIProviderConfig()
        self._client = client if client is not None else self._build_client()
        self.tracer = tracer or TraceLogger.from_env()

    def evaluate(self, request: SemanticEvaluationRequest) -> SemanticEvaluation:
        """Evaluate a complete operational decomposition with OpenAI."""

        with self.tracer.session(request.correlation_id or request.request_id):
            return self._evaluate_inner(request)

    def _evaluate_inner(self, request: SemanticEvaluationRequest):
        """Run the evaluation request and normalize structured-output failures."""
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
        output_tokens = self.config.output_tokens_for(SEMANTIC_EVALUATION_STAGE)
        if output_tokens is not None:
            kwargs["max_output_tokens"] = output_tokens
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
            self.tracer.exception(
                invocation, exc, diagnostics=_semantic_parse_diagnostics(exc)
            )
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
            self.tracer.exception(
                invocation, exc, diagnostics=_semantic_parse_diagnostics(exc)
            )
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
        """Propose operational subtasks for a task."""
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
        """Re-propose operational subtasks after a semantic validation failure."""
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
        """Classify baseline subtasks as RETAIN or REMOVE."""
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
        """Propose added/support work caused by REMOVE subtasks."""
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
        """Run one structured stage and attach provenance to the parsed payload."""
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
        """Call the Responses API, then validate status, JSON, and schema."""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        kwargs = {
            "model": self.config.model,
            "input": messages,
            "text_format": schema,
        }
        output_tokens = self.config.output_tokens_for(stage.value)
        if output_tokens is not None:
            kwargs["max_output_tokens"] = output_tokens
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
            response = self._client.responses.create(
                model=kwargs["model"],
                input=kwargs["input"],
                text={"format": _provider_text_format(stage, schema)},
                **{
                    key: value
                    for key, value in kwargs.items()
                    if key not in {"model", "input", "text_format"}
                },
            )
        except Exception as exc:  # noqa: BLE001 - normalize vendor SDK failures
            self.tracer.exception(invocation, exc)
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(str(exc),),
            )
            raise_provider_failure("OpenAI", stage, exc)
        self.tracer.response(
            invocation,
            raw=response,
        )
        status = getattr(response, "status", None)
        incomplete_details = getattr(response, "incomplete_details", None)
        if status == "incomplete" or incomplete_details is not None:
            reason = _response_detail(incomplete_details, "reason")
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(
                    f"incomplete structured output for {stage.value}"
                    + (f": {reason}" if reason else ""),
                ),
            )
            raise ProviderOutputError(
                f"OpenAI returned incomplete structured output for {stage.value}"
                + (f" ({reason})" if reason else "")
            )
        response_error = _response_detail(getattr(response, "error", None), "message")
        if response_error:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"OpenAI response error: {response_error}",),
            )
            raise ProviderExecutionError(
                f"OpenAI request failed during {stage.value}: {response_error}"
            )
        if status not in (None, "completed", "incomplete"):
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"unexpected response status for {stage.value}: {status}",),
            )
            raise ProviderOutputError(
                f"OpenAI returned status {status!r} for {stage.value}"
            )
        refusal = _response_refusal(response)
        if refusal:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"structured output refused: {refusal}",),
            )
            raise ProviderOutputError(
                f"OpenAI refused structured output for {stage.value}: {refusal}"
            )
        raw_output = getattr(response, "output_text", None)
        if raw_output is None or raw_output == "":
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
            parsed = json.loads(raw_output)
        except (TypeError, json.JSONDecodeError) as exc:
            self.tracer.validation(
                phase="structural",
                stage=stage.value,
                result="failure",
                errors=(f"malformed JSON for {stage.value}: {exc}",),
                response=raw_output,
            )
            raise ProviderOutputError(
                f"OpenAI returned malformed JSON for {stage.value}"
            ) from exc
        try:
            if schema is OperationalDecomposition:
                parsed = _canonicalize_operational_weights(parsed)
            _canonicalize_transformation_values(stage, parsed)
            mapped = schema.model_validate(parsed)
            self.tracer.emit(
                "llm.parsed",
                provider=self.provider_id,
                stage=stage.value,
                correlation_id=invocation.correlation_id,
                data={"parsed_response": mapped},
            )
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
                f"OpenAI structured output failed schema validation for {stage.value}"
            ) from exc

    def _build_client(self):
        """Build the OpenAI SDK client or raise a configuration error."""
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
    def _raise_openai_evaluation_failure(stage, exc):
        """Map an SDK exception onto the provider error taxonomy."""
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
