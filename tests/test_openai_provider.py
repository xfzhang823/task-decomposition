import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_provider_application import account_input, request
from test_staged_pipeline import make_added, make_classification, make_operational

from task_decomposition import (
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
    ProviderStage,
    SemanticEvaluation,
    TaskDecomposition,
    decompose,
)
from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    RetainRemoveClassificationRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.providers.openai import (
    DEFAULT_OPENAI_MODEL,
    OpenAIDecompositionProvider,
    OpenAIProviderConfig,
    _provider_text_format,
    _strict_text_format,
)
from task_decomposition.providers.prompts import (
    ADDED_WORK_PROMPT,
    OPERATIONAL_DECOMPOSITION_PROMPT,
    OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT,
    RETAIN_REMOVE_PROMPT,
)


class FakeResponses:
    def __init__(self, outputs=None, error=None):
        self.outputs = outputs or {}
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        schema = kwargs["text_format"]
        return SimpleNamespace(output_parsed=self.outputs.get(schema))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        name = kwargs["text"]["format"]["name"]
        value = next(
            (
                value
                for schema, value in self.outputs.items()
                if schema.__name__ == name
            ),
            None,
        )
        if hasattr(value, "model_dump_json"):
            raw = value.model_dump_json()
        elif isinstance(value, dict):
            raw = json.dumps(value)
        else:
            raw = value
        return SimpleNamespace(
            status="completed",
            output_text=raw,
            output=(),
            usage=None,
        )


class FakeClient:
    def __init__(self, outputs=None, error=None):
        self.responses = FakeResponses(outputs=outputs, error=error)


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


def test_each_openai_stage_uses_structured_output_and_maps_provenance():
    client = FakeClient(
        outputs={
            type(make_operational()): make_operational(),
            type(make_classification()): make_classification(),
            type(make_added()): make_added(),
            SemanticEvaluation: {"decision": "accept", "rubric_version": "1.0"},
        }
    )
    provider = OpenAIDecompositionProvider(
        OpenAIProviderConfig(model="test-structured-model", max_output_tokens=321),
        client=client,
    )
    operational_request, classification_request, added_request = stage_requests()

    operational_response = provider.generate_operational_decomposition(
        operational_request
    )
    classification_response = provider.classify_retain_remove(classification_request)
    added_response = provider.classify_added_work(added_request)

    assert operational_response.stage is ProviderStage.OPERATIONAL_DECOMPOSITION
    assert classification_response.stage is ProviderStage.RETAIN_REMOVE_CLASSIFICATION
    assert added_response.stage is ProviderStage.ADDED_WORK_CLASSIFICATION
    assert operational_response.provenance.provider_id == "openai"
    assert operational_response.provenance.model_id == "test-structured-model"
    assert operational_response.provenance.request_id == "request-1"
    assert len(client.responses.calls) == 3
    assert all(
        call["model"] == "test-structured-model" for call in client.responses.calls
    )
    assert all(call["max_output_tokens"] == 321 for call in client.responses.calls)
    assert (
        client.responses.calls[0]["text"]["format"]["name"]
        == "OperationalDecomposition"
    )
    assert (
        OPERATIONAL_DECOMPOSITION_PROMPT
        in client.responses.calls[0]["input"][0]["content"]
    )
    assert RETAIN_REMOVE_PROMPT in client.responses.calls[1]["input"][0]["content"]
    assert "JSON Output Rules" in RETAIN_REMOVE_PROMPT
    assert ADDED_WORK_PROMPT in client.responses.calls[2]["input"][0]["content"]


def test_openai_retain_remove_stage_override_reaches_request():
    client = FakeClient(outputs={type(make_classification()): make_classification()})
    provider = OpenAIDecompositionProvider(
        OpenAIProviderConfig(
            max_output_tokens=2000,
            stage_output_tokens={
                ProviderStage.RETAIN_REMOVE_CLASSIFICATION: 4000,
            },
        ),
        client=client,
    )

    provider.classify_retain_remove(stage_requests()[1])

    assert client.responses.calls[0]["max_output_tokens"] == 4000


def test_openai_operational_stage_override_reaches_request():
    client = FakeClient(outputs={type(make_operational()): make_operational()})
    provider = OpenAIDecompositionProvider(
        OpenAIProviderConfig(
            max_output_tokens=2000,
            stage_output_tokens={
                ProviderStage.OPERATIONAL_DECOMPOSITION: 4000,
            },
        ),
        client=client,
    )

    provider.generate_operational_decomposition(stage_requests()[0])

    assert client.responses.calls[0]["max_output_tokens"] == 4000


def test_openai_operational_provider_schema_uses_numeric_effort_weight():
    schema = _provider_text_format(
        ProviderStage.OPERATIONAL_DECOMPOSITION,
        type(make_operational()),
    )["schema"]["$defs"]["OperationalSubtask"]["properties"]

    assert schema["relative_effort_weight"] == {
        "anyOf": [
            {"exclusiveMinimum": 0, "type": "number"},
            {"type": "null"},
        ]
    }


def test_openai_converts_numeric_effort_weight_to_decimal():
    operational = make_operational().model_dump(mode="json")
    for index, subtask in enumerate(operational["operational_subtasks"], start=1):
        subtask["relative_effort_weight"] = index + 0.5
    provider = OpenAIDecompositionProvider(
        client=FakeClient(outputs={type(make_operational()): operational})
    )

    result = provider.generate_operational_decomposition(stage_requests()[0])

    assert [
        type(subtask.relative_effort_weight)
        for subtask in result.payload.operational_subtasks
    ] == [Decimal, Decimal, Decimal]


def test_provider_prompts_request_compact_optional_fields():
    assert (
        "Keep each subtask name and description concise"
        in OPERATIONAL_DECOMPOSITION_PROMPT
    )
    assert (
        "Keep names and descriptions concise" in OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT
    )
    assert "Set optional descriptions, dependencies" in ADDED_WORK_PROMPT


def test_openai_strict_schemas_require_nested_and_optional_fields():
    def assert_strict(schema):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
            for value in schema["properties"].values():
                assert_strict(value)
        for value in schema.get("$defs", {}).values():
            assert_strict(value)
        for value in schema.get("anyOf", []):
            assert_strict(value)
        if isinstance(schema.get("items"), dict):
            assert_strict(schema["items"])

    for schema in (
        type(make_operational()),
        type(make_classification()),
        type(make_added()),
        SemanticEvaluation,
    ):
        strict_format = _strict_text_format(schema)
        assert strict_format["strict"] is True
        assert_strict(strict_format["schema"])


def test_openai_adapter_runs_full_validated_application():
    client = FakeClient(
        outputs={
            type(make_operational()): make_operational(),
            type(make_classification()): make_classification(),
            type(make_added()): make_added(),
            SemanticEvaluation: {"decision": "accept", "rubric_version": "1.0"},
        }
    )
    result = decompose(
        request(),
        OpenAIDecompositionProvider(
            OpenAIProviderConfig(model="application-test-model"), client=client
        ),
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    assert result.accounting.w1 == 74
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert len(result.provider_provenance) == 3


def test_missing_structured_response_is_rejected():
    provider = OpenAIDecompositionProvider(client=FakeClient())
    with pytest.raises(ProviderOutputError, match="no structured output"):
        provider.generate_operational_decomposition(stage_requests()[0])


@pytest.mark.parametrize(
    ("response_kwargs", "message"),
    [
        ({"output_text": ""}, "no structured output"),
        (
            {
                "status": "incomplete",
                "incomplete_details": SimpleNamespace(reason="max_output_tokens"),
                "output_text": "{",
            },
            "incomplete structured output",
        ),
        (
            {
                "output_text": "",
                "output": (
                    SimpleNamespace(
                        content=(SimpleNamespace(type="refusal", refusal="safety"),)
                    ),
                ),
            },
            "refused structured output",
        ),
        ({"output_text": "not json"}, "malformed JSON"),
        ({"output_text": '{"task": {}}'}, "schema validation"),
    ],
)
def test_structured_output_failures_are_explicit(response_kwargs, message):
    class ResponseClient(FakeClient):
        def __init__(self):
            self.responses = FakeResponses()

            response = {
                "status": "completed",
                "output_text": "",
                "output": (),
                **response_kwargs,
            }
            self.responses.create = lambda **kwargs: (
                self.responses.calls.append(kwargs) or SimpleNamespace(**response)
            )

    provider = OpenAIDecompositionProvider(client=ResponseClient())
    with pytest.raises(ProviderOutputError, match=message):
        provider.classify_retain_remove(stage_requests()[1])


def test_openai_request_failure_is_wrapped():
    provider = OpenAIDecompositionProvider(
        client=FakeClient(error=RuntimeError("network unavailable"))
    )
    with pytest.raises(
        ProviderExecutionError, match="operational_decomposition"
    ) as error:
        provider.generate_operational_decomposition(stage_requests()[0])
    assert isinstance(error.value.__cause__, RuntimeError)


def test_openai_authentication_failure_is_wrapped():
    class AuthenticationError(Exception):
        pass

    provider = OpenAIDecompositionProvider(
        client=FakeClient(error=AuthenticationError("invalid key"))
    )
    with pytest.raises(ProviderAuthenticationError):
        provider.generate_operational_decomposition(stage_requests()[0])


def test_openai_provider_configuration_is_injected_without_sdk_import():
    client = FakeClient(outputs={type(make_operational()): make_operational()})
    provider = OpenAIDecompositionProvider(client=client)
    assert provider.provider_id == "openai"
    assert provider.config.model == DEFAULT_OPENAI_MODEL
    assert provider.config.api_key is None


def test_openai_provider_does_not_return_authoritative_accounting_metrics():
    client = FakeClient(outputs={type(make_operational()): make_operational()})
    response = OpenAIDecompositionProvider(
        client=client
    ).generate_operational_decomposition(stage_requests()[0])
    assert not hasattr(response.payload, "net_substitution_ratio")
    assert not hasattr(response.payload, "net_augmentation_multiplier")


def test_openai_provider_model_mapping_failure_is_wrapped():
    class BadPayload:
        pass

    client = FakeClient(outputs={type(make_operational()): BadPayload()})
    with pytest.raises(ProviderOutputError, match="malformed JSON"):
        OpenAIDecompositionProvider(client=client).generate_operational_decomposition(
            stage_requests()[0]
        )
