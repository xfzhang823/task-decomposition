"""Provider-driven orchestration over the validated Wave 2 stage pipeline."""

from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    DecompositionRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.stages import StagedDecompositionResult
from task_decomposition.application.staged_pipeline import run_staged_pipeline
from task_decomposition.errors import (
    MissingAccountingInputError,
    ProviderContractValidationError,
    ProviderError,
    ProviderExecutionError,
    ProviderOutputError,
    ProviderSemanticValidationError,
    SemanticAssertionError,
    StageValidationError,
)
from task_decomposition.ports.provider import DecompositionProvider
from task_decomposition.validation.semantic import assert_no_forbidden_meta_language
from task_decomposition.validation.stages import (
    validate_added_work_classification,
    validate_operational_decomposition,
    validate_retain_remove_classification,
)


def decompose(
    request: DecompositionRequest,
    provider: DecompositionProvider,
) -> StagedDecompositionResult:
    """Generate and validate all stages, then run deterministic accounting.

    Provider results are accepted only as stage payloads.  The service never
    asks a provider for, reads, or trusts W0/W1 or any derived impact metric.
    """
    if request.accounting_input is None:
        raise MissingAccountingInputError(
            "provider-driven decomposition requires explicit Wave 1 accounting input"
        )
    if not isinstance(provider, DecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the DecompositionProvider protocol"
        )
    provider_id = _provider_id(provider)
    operational_response = _call_stage(
        provider_id,
        ProviderStage.OPERATIONAL_DECOMPOSITION,
        provider.generate_operational_decomposition,
        OperationalDecompositionRequest(request=request),
    )
    operational = _validate_operational(operational_response)

    classification_response = _call_stage(
        provider_id,
        ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
        provider.classify_retain_remove,
        RetainRemoveClassificationRequest(
            request=request, operational_decomposition=operational
        ),
    )
    classification = _validate_classification(operational, classification_response)

    added_response = _call_stage(
        provider_id,
        ProviderStage.ADDED_WORK_CLASSIFICATION,
        provider.classify_added_work,
        AddedWorkClassificationRequest(
            request=request,
            operational_decomposition=operational,
            retain_remove_classification=classification,
        ),
    )
    added = _validate_added(operational, classification, added_response)

    result = run_staged_pipeline(
        operational,
        classification,
        added,
        request.accounting_input,
        support_work_override=request.accounting_input.support_work,
    )
    provider_provenance = (
        operational_response.provenance,
        classification_response.provenance,
        added_response.provenance,
    )
    portable_refs = tuple(
        ref for provenance in provider_provenance for ref in provenance.references
    )
    return result.model_copy(
        update={
            "provider_provenance": provider_provenance,
            "provenance_refs": result.provenance_refs + portable_refs,
        }
    )


def _provider_id(provider: DecompositionProvider) -> str:
    provider_id = getattr(provider, "provider_id", None)
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ProviderOutputError("provider must expose a non-empty provider_id")
    return provider_id


def _call_stage(provider_id, expected_stage, operation, stage_request):
    try:
        response = operation(stage_request)
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderExecutionError(
            f"provider {provider_id!r} failed during {expected_stage.value}: {exc}"
        ) from exc
    try:
        if not isinstance(response, ProviderStageResponse):
            response = ProviderStageResponse.model_validate(response)
    except Exception as exc:
        raise ProviderOutputError(
            f"provider {provider_id!r} returned an invalid {expected_stage.value} response"
        ) from exc
    if response.stage is not expected_stage:
        raise ProviderOutputError(
            f"provider response stage {response.stage.value!r} does not match "
            f"{expected_stage.value!r}"
        )
    if response.provenance.provider_id != provider_id:
        raise ProviderOutputError(
            "provider provenance provider_id does not match the executing provider"
        )
    if response.provenance.stage is not expected_stage:
        raise ProviderOutputError(
            "provider provenance stage does not match response stage"
        )
    return response


def _validate_operational(response):
    try:
        return validate_operational_decomposition(response.payload)
    except SemanticAssertionError as exc:
        raise ProviderSemanticValidationError(str(exc)) from exc
    except StageValidationError as exc:
        raise ProviderContractValidationError(str(exc)) from exc


def _validate_classification(operational, response):
    try:
        assert_no_forbidden_meta_language(response.payload)
        return validate_retain_remove_classification(operational, response.payload)
    except SemanticAssertionError as exc:
        raise ProviderSemanticValidationError(str(exc)) from exc
    except StageValidationError as exc:
        raise ProviderContractValidationError(str(exc)) from exc


def _validate_added(operational, classification, response):
    try:
        assert_no_forbidden_meta_language(response.payload)
        return validate_added_work_classification(
            operational, classification, response.payload
        )
    except SemanticAssertionError as exc:
        raise ProviderSemanticValidationError(str(exc)) from exc
    except StageValidationError as exc:
        raise ProviderContractValidationError(str(exc)) from exc


__all__ = ["decompose"]
