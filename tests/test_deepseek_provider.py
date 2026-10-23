import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_provider_application import account_input, request
from test_staged_pipeline import make_added, make_classification, make_operational

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
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION
from task_decomposition.providers.deepseek import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DeepSeekDecompositionProvider,
    DeepSeekProviderConfig,
)


class FakeCompletions:
    def __init__(
        self, outputs=None, error=None, finish_reason="stop", reasoning_tokens=None
    ):
        self.outputs = outputs or []
        self.error = error
        self.finish_reason = finish_reason
        self.reasoning_tokens = reasoning_tokens
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        request_payload = json.loads(
            kwargs["messages"][0]["content"].split("INPUT JSON:\n", 1)[1]
        )
        if "rubric_version" in request_payload:
            content = (
                '{"decision":"accept","rubric_version":"'
                + SEMANTIC_EVALUATION_RUBRIC_VERSION
                + '"}'
            )
        else:
            content = self.outputs.pop(0)
        usage = None
        if self.reasoning_tokens is not None:
            usage = SimpleNamespace(
                completion_tokens_details=SimpleNamespace(
                    reasoning_tokens=self.reasoning_tokens
                )
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                    finish_reason=self.finish_reason,
                )
            ],
            usage=usage,
        )


class FakeDeepSeekClient:
    def __init__(
        self, outputs=None, error=None, finish_reason="stop", reasoning_tokens=None
    ):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(
                outputs=outputs,
                error=error,
                finish_reason=finish_reason,
                reasoning_tokens=reasoning_tokens,
            )
        )


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
    # The adapter uses the schema contract after the fake transport returns JSON.
    outputs = [
        make_operational().model_dump_json(),
        make_classification().model_dump_json(),
        make_added().model_dump_json(),
    ]
    client = FakeDeepSeekClient(outputs=outputs)
    return DeepSeekDecompositionProvider(
        DeepSeekProviderConfig(model="deepseek-test-model", base_url="https://test"),
        client=client,
    ), client


def test_deepseek_implements_port_and_maps_all_stages():
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
    assert responses[0].provenance.provider_id == "deepseek"
    assert responses[0].provenance.model_id == "deepseek-test-model"
    assert len(client.chat.completions.calls) == 3
    assert all(
        call["model"] == "deepseek-test-model" for call in client.chat.completions.calls
    )
    assert all(
        call["response_format"] == {"type": "json_object"}
        for call in client.chat.completions.calls
    )


def test_deepseek_requests_include_the_contract_schema():
    provider_instance, client = provider()
    requests = stage_requests()
    provider_instance.generate_operational_decomposition(requests[0])
    provider_instance.classify_retain_remove(requests[1])
    provider_instance.classify_added_work(requests[2])

    prompts = [call["messages"][0]["content"] for call in client.chat.completions.calls]
    assert all("OUTPUT JSON SCHEMA" in prompt for prompt in prompts)
    assert all(
        prompt.index("OUTPUT JSON SCHEMA") < prompt.index("INPUT JSON:")
        for prompt in prompts
    )
    assert '"operational_subtasks"' in prompts[0]
    assert '"classified_subtasks"' in prompts[1]
    assert '"added_work_rows"' in prompts[2]


def test_deepseek_mapping_failure_reports_field_details():
    client = FakeDeepSeekClient(outputs=['{"subtasks": []}'])
    provider_instance = DeepSeekDecompositionProvider(client=client)

    with pytest.raises(ProviderOutputError, match="contract mapping") as excinfo:
        provider_instance.generate_operational_decomposition(stage_requests()[0])

    message = str(excinfo.value)
    assert "operational_subtasks: Field required" in message
    assert "subtasks: Extra inputs are not permitted" in message


def test_deepseek_length_finish_reports_token_limit():
    client = FakeDeepSeekClient(
        outputs=['{"task":'],
        finish_reason="length",
        reasoning_tokens=3907,
    )
    provider_instance = DeepSeekDecompositionProvider(
        DeepSeekProviderConfig(model="deepseek-test-model", max_tokens=4000),
        client=client,
    )

    with pytest.raises(ProviderOutputError, match="output token limit") as excinfo:
        provider_instance.generate_operational_decomposition(stage_requests()[0])

    message = str(excinfo.value)
    assert "max_tokens=4000" in message
    assert "reasoning_tokens=3907" in message


def test_deepseek_adapter_runs_validated_application():
    provider_instance, _client = provider()
    result = decompose(
        request(),
        provider_instance,
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    assert result.accounting.w1 == 74
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert all(item.provider_id == "deepseek" for item in result.provider_provenance)


def test_deepseek_malformed_output_is_rejected():
    client = FakeDeepSeekClient(outputs=["not json"])
    provider_instance = DeepSeekDecompositionProvider(client=client)
    with pytest.raises(ProviderOutputError, match="malformed JSON"):
        provider_instance.generate_operational_decomposition(stage_requests()[0])


def test_deepseek_provider_failures_are_mapped():
    class AuthenticationError(Exception):
        pass

    with pytest.raises(ProviderAuthenticationError):
        DeepSeekDecompositionProvider(
            client=FakeDeepSeekClient(error=AuthenticationError("invalid key"))
        ).generate_operational_decomposition(stage_requests()[0])

    with pytest.raises(ProviderExecutionError):
        DeepSeekDecompositionProvider(
            client=FakeDeepSeekClient(error=RuntimeError("unavailable"))
        ).generate_operational_decomposition(stage_requests()[0])


def test_deepseek_configuration_defaults_are_isolated():
    provider_instance = DeepSeekDecompositionProvider(client=FakeDeepSeekClient())
    assert provider_instance.config.model == DEFAULT_DEEPSEEK_MODEL
    assert provider_instance.config.base_url == DEFAULT_DEEPSEEK_BASE_URL
    assert provider_instance.config.api_key is None
    assert provider_instance.config.max_tokens == 16000
