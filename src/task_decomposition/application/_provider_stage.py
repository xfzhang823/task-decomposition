"""Shared provider-stage invocation and validation for application services."""

from task_decomposition.contracts.provider import ProviderStageResponse
from task_decomposition.errors import (
    ProviderContractValidationError,
    ProviderError,
    ProviderExecutionError,
    ProviderOutputError,
    StageValidationError,
)
from task_decomposition.tracing import current_tracer
from task_decomposition.validation.stages import (
    validate_activity_effort_estimation,
    validate_agentic_task_synthesis,
    validate_human_agent_activity_model,
    validate_operational_decomposition,
    validate_retain_remove_classification,
)


def provider_id(provider) -> str:
    value = getattr(provider, "provider_id", None)
    if not isinstance(value, str) or not value.strip():
        raise ProviderOutputError("provider must expose a non-empty provider_id")
    return value


def call_stage(provider_name, expected_stage, operation, stage_request):
    try:
        response = operation(stage_request)
    except ProviderError:
        raise
    except Exception as exc:
        tracer = current_tracer()
        if tracer:
            tracer.emit(
                "provider.exception",
                provider=provider_name,
                stage=expected_stage.value,
                data={
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "cause": repr(exc.__cause__) if exc.__cause__ else None,
                },
            )
        raise ProviderExecutionError(
            f"provider {provider_name!r} failed during {expected_stage.value}: {exc}"
        ) from exc
    try:
        if not isinstance(response, ProviderStageResponse):
            response = ProviderStageResponse.model_validate(response)
    except Exception as exc:
        raise ProviderOutputError(
            f"provider {provider_name!r} returned an invalid {expected_stage.value} response"
        ) from exc
    if response.stage is not expected_stage:
        raise ProviderOutputError(
            f"provider response stage {response.stage.value!r} does not match "
            f"{expected_stage.value!r}"
        )
    if response.provenance.provider_id != provider_name:
        raise ProviderOutputError(
            "provider provenance provider_id does not match the executing provider"
        )
    if response.provenance.stage is not expected_stage:
        raise ProviderOutputError(
            "provider provenance stage does not match response stage"
        )
    return response


def validate_operational_response(response, *, attempt=None):
    try:
        result = validate_operational_decomposition(response.payload)
        tracer = current_tracer()
        if tracer:
            tracer.validation(
                phase="structural",
                stage="operational_decomposition",
                result="success",
                attempt=attempt,
                response=result,
            )
        return result
    except StageValidationError as exc:
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="operational_decomposition",
                result="failure",
                attempt=attempt,
                errors=(str(exc),),
                response=response.payload,
            )
        raise ProviderContractValidationError(str(exc)) from exc


def validate_classification_response(operational, response):
    try:
        result = validate_retain_remove_classification(operational, response.payload)
        tracer = current_tracer()
        if tracer:
            tracer.validation(
                phase="structural",
                stage="retain_remove_classification",
                result="success",
                response=result,
            )
        return result
    except StageValidationError as exc:
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="retain_remove_classification",
                result="failure",
                errors=(str(exc),),
                response=response.payload,
            )
        raise ProviderContractValidationError(str(exc)) from exc


def validate_agentic_response(operational, classification, response):
    try:
        result = validate_agentic_task_synthesis(
            operational, classification, response.payload
        )
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="agentic_task_synthesis",
                result="success",
                response=result,
            )
        return result
    except StageValidationError as exc:
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="agentic_task_synthesis",
                result="failure",
                errors=(str(exc),),
                response=response.payload,
            )
        raise ProviderContractValidationError(str(exc)) from exc


def validate_human_activity_response(operational, classification, synthesis, response):
    try:
        result = validate_human_agent_activity_model(
            operational, classification, synthesis, response.payload
        )
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="human_agent_activity_modeling",
                result="success",
                response=result,
            )
        return result
    except StageValidationError as exc:
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="human_agent_activity_modeling",
                result="failure",
                errors=(str(exc),),
                response=response.payload,
            )
        raise ProviderContractValidationError(str(exc)) from exc


def validate_activity_effort_response(operational, activities, response):
    try:
        result = validate_activity_effort_estimation(
            operational, activities, response.payload
        )
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="activity_effort_estimation",
                result="success",
                response=result,
            )
        return result
    except StageValidationError as exc:
        if current_tracer():
            current_tracer().validation(
                phase="structural",
                stage="activity_effort_estimation",
                result="failure",
                errors=(str(exc),),
                response=response.payload,
            )
        raise ProviderContractValidationError(str(exc)) from exc


__all__ = [
    "call_stage",
    "provider_id",
    "validate_activity_effort_response",
    "validate_agentic_response",
    "validate_classification_response",
    "validate_human_activity_response",
    "validate_operational_response",
]
