from decimal import Decimal
from types import SimpleNamespace

import pytest

from task_decomposition import (
    DecompositionProvider,
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
    ProviderStage,
    TaskDecomposition,
    decompose,
)
from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    RetainRemoveClassificationRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.providers.gemini import (
    DEFAULT_GEMINI_MODEL,
    GeminiDecompositionProvider,
    GeminiProviderConfig,
)

from test_provider_application import account_input, request
from test_staged_pipeline import make_added, make_classification, make_operational


class FakeModels:
    def __init__(self, outputs=None, error=None):
        self.outputs = outputs or {}
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        schema = kwargs["config"]["response_schema"]
        return SimpleNamespace(parsed=self.outputs.get(schema), text=None)


class FakeGeminiClient:
    def __init__(self, outputs=None, error=None):
        self.models = FakeModels(outputs=outputs, error=error)


def stage_requests():
    task_request = request()
    operational = make_operational()
    classification = make_classification()
    transformation_request = TransformationDecompositionRequest(
        task_decomposition=TaskDecomposition(
            operational_decomposition=operational,
        ),
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
        request_id="request-1",
    )
    return (
        OperationalDecompositionRequest(request=task_request),
        RetainRemoveClassificationRequest(
            request=transformation_request, operational_decomposition=operational
        ),
        AddedWorkClassificationRequest(
            request=transformation_request,
            operational_decomposition=operational,
            retain_remove_classification=classification,
        ),
    )


def provider():
    client = FakeGeminiClient(
        outputs={
            type(make_operational()): make_operational(),
            type(make_classification()): make_classification(),
            type(make_added()): make_added(),
        }
    )
    return GeminiDecompositionProvider(
        GeminiProviderConfig(model="gemini-test-model", max_output_tokens=123),
        client=client,
    ), client


def test_gemini_implements_port_and_maps_all_stages():
    provider_instance, client = provider()
    assert isinstance(provider_instance, DecompositionProvider)
    requests = stage_requests()
    responses = (
        provider_instance.generate_operational_decomposition(requests[0]),
        provider_instance.classify_retain_remove(requests[1]),
        provider_instance.classify_added_work(requests[2]),
    )
    assert [response.stage for response in responses] == [
        ProviderStage.OPERATIONAL_DECOMPOSITION,
        ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
        ProviderStage.ADDED_WORK_CLASSIFICATION,
    ]
    assert responses[0].provenance.provider_id == "gemini"
    assert responses[0].provenance.model_id == "gemini-test-model"
    assert responses[0].provenance.request_id == "request-1"
    assert len(client.models.calls) == 3
    assert all(call["model"] == "gemini-test-model" for call in client.models.calls)
    assert all(
        call["config"]["response_mime_type"] == "application/json"
        for call in client.models.calls
    )


def test_gemini_adapter_runs_validated_application():
    provider_instance, _ = provider()
    result = decompose(
        request(),
        provider_instance,
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    assert result.accounting.w1 == 74
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert all(item.provider_id == "gemini" for item in result.provider_provenance)


def test_gemini_malformed_and_empty_output_are_rejected():
    class BadOutput:
        pass

    request_value = stage_requests()[0]
    bad = GeminiDecompositionProvider(
        client=FakeGeminiClient(outputs={type(make_operational()): BadOutput()})
    )
    with pytest.raises(ProviderOutputError, match="contract mapping"):
        bad.generate_operational_decomposition(request_value)

    empty = GeminiDecompositionProvider(client=FakeGeminiClient())
    with pytest.raises(ProviderOutputError, match="no structured output"):
        empty.generate_operational_decomposition(request_value)


def test_gemini_provider_failures_are_mapped():
    class AuthenticationError(Exception):
        pass

    with pytest.raises(ProviderAuthenticationError):
        GeminiDecompositionProvider(
            client=FakeGeminiClient(error=AuthenticationError("invalid key"))
        ).generate_operational_decomposition(stage_requests()[0])

    with pytest.raises(ProviderExecutionError):
        GeminiDecompositionProvider(
            client=FakeGeminiClient(error=RuntimeError("unavailable"))
        ).generate_operational_decomposition(stage_requests()[0])


def test_gemini_default_model_is_provider_specific():
    provider_instance = GeminiDecompositionProvider(client=FakeGeminiClient())
    assert provider_instance.config.model == DEFAULT_GEMINI_MODEL
    assert provider_instance.config.api_key is None
