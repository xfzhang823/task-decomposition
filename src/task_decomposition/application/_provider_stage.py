"""Shared provider-stage invocation and validation for application services."""

from task_decomposition.contracts.provider import ProviderStageResponse
from task_decomposition.errors import (
    ProviderContractValidationError,
    ProviderError,
    ProviderExecutionError,
    ProviderOutputError,
    ProviderSemanticValidationError,
    SemanticAssertionError,
    StageValidationError,
)
from task_decomposition.validation.semantic import assert_no_forbidden_meta_language
from task_decomposition.validation.stages import (
    validate_added_work_classification,
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


def validate_operational_response(response):
    try:
        return validate_operational_decomposition(response.payload)
    except SemanticAssertionError as exc:
        raise ProviderSemanticValidationError(str(exc)) from exc
    except StageValidationError as exc:
        raise ProviderContractValidationError(str(exc)) from exc


def validate_classification_response(operational, response):
    try:
        assert_no_forbidden_meta_language(response.payload)
        return validate_retain_remove_classification(operational, response.payload)
    except SemanticAssertionError as exc:
        raise ProviderSemanticValidationError(str(exc)) from exc
    except StageValidationError as exc:
        raise ProviderContractValidationError(str(exc)) from exc


def validate_added_response(operational, classification, response):
    try:
        assert_no_forbidden_meta_language(response.payload)
        return validate_added_work_classification(
            operational, classification, response.payload
        )
    except SemanticAssertionError as exc:
        raise ProviderSemanticValidationError(str(exc)) from exc
    except StageValidationError as exc:
        raise ProviderContractValidationError(str(exc)) from exc


__all__ = [
    "call_stage",
    "provider_id",
    "validate_added_response",
    "validate_classification_response",
    "validate_operational_response",
]
