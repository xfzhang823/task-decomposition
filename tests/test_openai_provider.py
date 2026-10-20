import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_provider_application import account_input, request
from test_semantic_evaluator_providers import evaluation_request
from test_staged_pipeline import make_added, make_classification, make_operational

from task_decomposition import (
    AddedWorkEstimate,
    AddedWorkItem,
    EstimateRange,
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
    ProviderStage,
    SemanticEvaluation,
    TaskDecomposition,
    decompose,
)
from task_decomposition.contracts.decomposition import TransformationClassification
from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    RetainRemoveClassificationRequest,
    TransformationDecompositionRequest,
)
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION
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
from task_decomposition.tracing import TraceLogger


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
            SemanticEvaluation: {
                "decision": "accept",
                "rubric_version": SEMANTIC_EVALUATION_RUBRIC_VERSION,
            },
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


def test_openai_added_work_parses_expanded_estimate_schema():
    added = make_added().model_copy(
        update={
            "added_work_rows": (
                AddedWorkItem(
                    work_id="estimated-work",
                    workload_name="Guide AI",
                    category="AI_INTERACTION",
                    source_removed_subtask_ids=("sub-2",),
                    estimate=AddedWorkEstimate(
                        occurrences_per_parent_execution=EstimateRange(
                            low=0, typical=1, high=2
                        ),
                        reference_occurrences_per_parent_execution=EstimateRange(
                            low=1, typical=1, high=1
                        ),
                        relative_effort_per_occurrence=EstimateRange(
                            low="0.1", typical="0.2", high="0.4"
                        ),
                        reference_subtask_id="sub-1",
                        rationale="Comparable interaction.",
                        estimate_basis="assumed",
                    ),
                ),
            )
        }
    )
    client = FakeClient(outputs={type(added): added})
    provider = OpenAIDecompositionProvider(
        OpenAIProviderConfig(
            stage_output_tokens={
                ProviderStage.ADDED_WORK_CLASSIFICATION: 4000,
            }
        ),
        client=client,
    )
    response = provider.classify_added_work(stage_requests()[2])
    assert (
        provider.config.output_tokens_for(ProviderStage.ADDED_WORK_CLASSIFICATION.value)
        == 4000
    )
    assert client.responses.calls[0]["max_output_tokens"] == 4000
    assert response.payload.added_work_rows[
        0
    ].estimate.relative_effort_per_occurrence.typical == Decimal("0.2")
    assert response.payload.added_work_rows[0].source_removed_subtask_ids == ("sub-2",)


def test_openai_added_work_schema_omits_defaulted_compatibility_fields():
    schema = _provider_text_format(
        ProviderStage.ADDED_WORK_CLASSIFICATION, type(make_added())
    )["schema"]
    item = schema["$defs"]["AddedWorkItem"]
    assert not {
        "description",
        "amount",
        "depends_on_subtask_ids",
        "sequence_index",
        "provenance_refs",
    } & set(item["properties"])
    assert "provenance_refs" not in schema["$defs"]["AddedWorkEstimate"]["properties"]


def test_openai_added_work_incomplete_output_remains_an_explicit_failure():
    class IncompleteClient(FakeClient):
        def __init__(self):
            self.responses = FakeResponses()
            self.responses.create = lambda **kwargs: (
                self.responses.calls.append(kwargs)
                or SimpleNamespace(
                    status="incomplete",
                    incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                    output_text="{",
                    output=(),
                )
            )

    provider = OpenAIDecompositionProvider(client=IncompleteClient())
    with pytest.raises(ProviderOutputError, match="incomplete structured output"):
        provider.classify_added_work(stage_requests()[2])


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


def test_openai_transformation_provider_schemas_use_numeric_decimal_fields():
    retain_schema = _provider_text_format(
        ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
        type(make_classification()),
    )["schema"]["$defs"]
    assert retain_schema["ClassifiedSubtask"]["properties"][
        "baseline_effort_ratio"
    ] == {
        "anyOf": [
            {"minimum": 0, "type": "number"},
            {"type": "null"},
        ]
    }
    assert retain_schema["EffortQuantity"]["properties"]["value"] == {
        "minimum": 0,
        "type": "number",
    }

    added_schema = _provider_text_format(
        ProviderStage.ADDED_WORK_CLASSIFICATION,
        type(make_added()),
    )["schema"]["$defs"]
    assert added_schema["SupportWorkInput"]["properties"]["value"] == {
        "minimum": 0,
        "type": "number",
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


def test_openai_converts_transformation_numeric_values_to_decimal():
    classification = make_classification().model_dump(mode="json")
    classification["classified_subtasks"][0]["effort"] = None
    classification["classified_subtasks"][0]["baseline_effort_ratio"] = 0.125
    classification["classified_subtasks"][1]["effort"]["value"] = 12.5
    added = make_added().model_dump(mode="json")
    added["added_work_rows"][0]["amount"]["value"] = 2.75
    provider = OpenAIDecompositionProvider(
        client=FakeClient(
            outputs={
                type(make_classification()): classification,
                type(make_added()): added,
            }
        )
    )

    retain_result = provider.classify_retain_remove(stage_requests()[1])
    added_result = provider.classify_added_work(stage_requests()[2])

    ratio = retain_result.payload.classified_subtasks[0].baseline_effort_ratio
    assert ratio == Decimal("0.125")
    assert retain_result.payload.classified_subtasks[1].effort.value == Decimal("12.5")
    assert added_result.payload.added_work_rows[0].amount.value == Decimal("2.75")


@pytest.mark.parametrize(
    ("stage", "schema_factory", "field_path", "invalid_value"),
    [
        (
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            make_classification,
            ("classified_subtasks", 0, "baseline_effort_ratio"),
            -0.1,
        ),
        (
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            make_classification,
            ("classified_subtasks", 1, "effort", "value"),
            -1,
        ),
        (
            ProviderStage.ADDED_WORK_CLASSIFICATION,
            make_added,
            ("added_work_rows", 0, "amount", "value"),
            -1,
        ),
    ],
)
def test_openai_rejects_invalid_transformation_numeric_values(
    stage, schema_factory, field_path, invalid_value
):
    payload = schema_factory().model_dump(mode="json")
    target = payload
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = invalid_value
    provider = OpenAIDecompositionProvider(
        client=FakeClient(outputs={type(schema_factory()): payload})
    )

    operation = (
        provider.classify_retain_remove
        if stage is ProviderStage.RETAIN_REMOVE_CLASSIFICATION
        else provider.classify_added_work
    )
    request_value = (
        stage_requests()[1]
        if stage is ProviderStage.RETAIN_REMOVE_CLASSIFICATION
        else stage_requests()[2]
    )
    with pytest.raises(ProviderOutputError, match="schema validation"):
        operation(request_value)


def test_provider_prompts_request_compact_optional_fields():
    assert "names and descriptions" in OPERATIONAL_DECOMPOSITION_PROMPT
    assert "concise" in OPERATIONAL_DECOMPOSITION_PROMPT
    assert (
        "Keep names and descriptions concise" in OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT
    )
    assert "Set optional descriptions, dependencies" in ADDED_WORK_PROMPT


def test_retain_remove_prompt_assesses_current_ai_potential_without_context():
    request = stage_requests()[1]
    request = request.model_copy(
        update={
            "request": request.request.model_copy(update={"transformation_context": {}})
        }
    )
    provider = OpenAIDecompositionProvider(
        client=FakeClient(outputs={type(make_classification()): make_classification()})
    )

    provider.classify_retain_remove(request)

    call = provider._client.responses.calls[0]
    payload = json.loads(call["input"][1]["content"])
    assert payload["transformation_context"] == {}
    assert (
        "automation potential using current AI-enabled technology"
        in RETAIN_REMOVE_PROMPT
    )
    assert "execute most of the core operational activity" in RETAIN_REMOVE_PROMPT
    assert "limited recurring human execution" in RETAIN_REMOVE_PROMPT
    assert "not deployment, industry adoption, or authorization" in RETAIN_REMOVE_PROMPT
    assert "Empty transformation context does not imply RETAIN" in RETAIN_REMOVE_PROMPT
    assert "oversight, approval, accountability" in RETAIN_REMOVE_PROMPT
    assert "separately from substantial recurring execution" in RETAIN_REMOVE_PROMPT
    assert "Classify each subtask independently" in RETAIN_REMOVE_PROMPT
    assert "identify the core operational activity" in RETAIN_REMOVE_PROMPT
    assert "execute most of the core operational activity" in RETAIN_REMOVE_PROMPT
    assert "Do not classify RETAIN merely because" in RETAIN_REMOVE_PROMPT
    assert "realistic conditions" in RETAIN_REMOVE_PROMPT
    assert "Do not assign percentages or additional categories" in RETAIN_REMOVE_PROMPT
    assert "subtask_id, classification, and rationale" in RETAIN_REMOVE_PROMPT
    assert "one concise sentence" in RETAIN_REMOVE_PROMPT


def test_retain_remove_rationale_is_public_and_traced_without_changing_labels(
    tmp_path,
):
    classification = make_classification().model_copy(
        update={
            "classified_subtasks": tuple(
                row.model_copy(
                    update={
                        "rationale": (
                            "Automation handles the routine activity; human execution "
                            "is limited to approval."
                        )
                    }
                )
                for row in make_classification().classified_subtasks
            )
        }
    )
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = OpenAIDecompositionProvider(
        client=FakeClient(outputs={type(classification): classification}),
        tracer=tracer,
    )

    response = provider.classify_retain_remove(stage_requests()[1])

    assert [row.classification for row in response.payload.classified_subtasks] == [
        row.classification for row in make_classification().classified_subtasks
    ]
    assert all(row.rationale for row in response.payload.classified_subtasks)
    records = [
        json.loads(line)
        for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    ]
    parsed = next(record for record in records if record["event"] == "llm.parsed")
    assert parsed["data"]["parsed_response"]["classified_subtasks"][0]["rationale"]


def test_operational_prompt_preserves_supplied_task_scope():
    assert (
        "only activities necessary or reasonably implied"
        in OPERATIONAL_DECOMPOSITION_PROMPT
    )
    assert (
        "Do not add documentation, monitoring, feedback, or follow-up"
        in OPERATIONAL_DECOMPOSITION_PROMPT
    )


@pytest.mark.parametrize(
    ("activity", "classification"),
    [
        (
            "Evaluate standardized cases using rules and a model with human approval",
            "remove",
        ),
        (
            "Optimize a recurring allocation from structured constraints with exception review",
            "remove",
        ),
        (
            "Coordinate routine handoffs through workflow automation with escalation",
            "remove",
        ),
        (
            "Perform an ongoing hands-on inspection requiring physical judgment",
            "retain",
        ),
        (
            "Resolve a novel case through sustained negotiation with multiple stakeholders",
            "retain",
        ),
    ],
)
def test_retain_remove_examples_preserve_binary_identity_contract(
    activity, classification
):
    """Capability examples remain representable through the binary contract."""
    operational = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(update={"subtask_name": activity}),
            )
        }
    )
    output = make_classification().model_copy(
        update={
            "task": operational.task,
            "classified_subtasks": (
                make_classification()
                .classified_subtasks[0]
                .model_copy(
                    update={
                        "subtask_id": operational.operational_subtasks[0].subtask_id,
                        "classification": TransformationClassification(classification),
                    }
                ),
            ),
        }
    )
    validated = output
    assert [row.subtask_id for row in validated.classified_subtasks] == [
        operational.operational_subtasks[0].subtask_id
    ]
    assert validated.classified_subtasks[0].classification.value == classification


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
            SemanticEvaluation: {
                "decision": "accept",
                "rubric_version": SEMANTIC_EVALUATION_RUBRIC_VERSION,
            },
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


def test_semantic_parse_failure_traces_decision_and_severities(tmp_path):
    class ValidationError(Exception):
        def errors(self):
            return [
                {
                    "input": {
                        "decision": "repair",
                        "findings": [
                            {"severity": "repairable"},
                            {"severity": "blocking"},
                        ],
                    }
                }
            ]

    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = OpenAIDecompositionProvider(
        client=FakeClient(error=ValidationError("invalid semantic evaluation")),
        tracer=tracer,
    )
    with pytest.raises(ProviderOutputError, match="structured output failed"):
        provider.evaluate(evaluation_request())

    events = [
        json.loads(line)
        for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    ]
    failure = next(event for event in events if event["event"] == "llm.exception")
    assert failure["data"]["diagnostics"] == {
        "exception_type": "ValidationError",
        "decisions": ["repair"],
        "finding_severities": ["blocking", "repairable"],
    }
    assert failure["data"]["raw_response_available"] is False


def test_semantic_parse_failure_traces_sanitized_provider_details(tmp_path):
    class ValidationError(Exception):
        def __init__(self, message):
            super().__init__(message)
            self.body = {
                "status": "error",
                "code": "invalid_response",
                "message": "provider response unavailable",
                "api_key": "sk-never-write-this",
            }

        def errors(self):
            return [{"input": {"decision": "repair", "findings": []}}]

    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = OpenAIDecompositionProvider(
        client=FakeClient(error=ValidationError("invalid semantic evaluation")),
        tracer=tracer,
    )
    with pytest.raises(ProviderOutputError):
        provider.evaluate(evaluation_request())

    trace_path = next(tmp_path.glob("*.jsonl"))
    text = trace_path.read_text()
    assert "sk-never-write-this" not in text
    failure = next(
        json.loads(line)
        for line in trace_path.read_text().splitlines()
        if json.loads(line)["event"] == "llm.exception"
    )
    assert failure["data"]["diagnostics"]["provider_details"] == {
        "body": {
            "status": "error",
            "code": "invalid_response",
            "message": "provider response unavailable",
        }
    }


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
