import json
from types import SimpleNamespace

import pytest
from test_evaluation_contracts import evaluation_request, finding

from task_decomposition.errors import (
    ProviderAuthenticationError,
    ProviderExecutionError,
    ProviderOutputError,
)
from task_decomposition.evaluation import (
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SemanticFindingCode,
    SemanticFindingSeverity,
)
from task_decomposition.providers.deepseek import (
    DeepSeekDecompositionProvider,
    DeepSeekProviderConfig,
)
from task_decomposition.providers.gemini import (
    GeminiDecompositionProvider,
    GeminiProviderConfig,
)
from task_decomposition.providers.openai import (
    OpenAIDecompositionProvider,
    OpenAIProviderConfig,
)
from task_decomposition.tracing import TraceLogger


class FakeResponses:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_parsed=self.output)


class FakeOpenAIClient:
    def __init__(self, output=None, error=None):
        self.responses = FakeResponses(output=output, error=error)


class FakeCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeDeepSeekClient:
    def __init__(self, content=None, error=None):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(content=content, error=error)
        )


class FakeModels:
    def __init__(self, parsed=None, text=None, error=None):
        self.parsed = parsed
        self.text = text
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(parsed=self.parsed, text=self.text)


class FakeGeminiClient:
    def __init__(self, parsed=None, text=None, error=None):
        self.models = FakeModels(parsed=parsed, text=text, error=error)


def evaluation(decision):
    if decision == SemanticEvaluationDecision.ACCEPT:
        result_finding = finding(
            code=SemanticFindingCode.CLARIFY_WORK_DESCRIPTION,
            severity=SemanticFindingSeverity.SUGGESTION,
        )
    elif decision == SemanticEvaluationDecision.REPAIR:
        result_finding = finding(severity=SemanticFindingSeverity.REPAIRABLE)
    else:
        result_finding = finding(severity=SemanticFindingSeverity.BLOCKING)
    return SemanticEvaluation(
        decision=decision,
        findings=(result_finding,),
        rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )


def provider_factory(provider_name, result, *, tracer=None, error=None):
    if provider_name == "openai":
        client = FakeOpenAIClient(output=result, error=error)
        provider = OpenAIDecompositionProvider(
            OpenAIProviderConfig(model="openai-evaluator-test"),
            client=client,
            tracer=tracer,
        )
    elif provider_name == "deepseek":
        client = FakeDeepSeekClient(
            content=result.model_dump_json() if result is not None else None,
            error=error,
        )
        provider = DeepSeekDecompositionProvider(
            DeepSeekProviderConfig(model="deepseek-evaluator-test"),
            client=client,
            tracer=tracer,
        )
    else:
        client = FakeGeminiClient(parsed=result, error=error)
        provider = GeminiDecompositionProvider(
            GeminiProviderConfig(model="gemini-evaluator-test"),
            client=client,
            tracer=tracer,
        )
    return provider, client


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "gemini"])
@pytest.mark.parametrize(
    "decision",
    [
        SemanticEvaluationDecision.ACCEPT,
        SemanticEvaluationDecision.REPAIR,
        SemanticEvaluationDecision.REJECT,
    ],
)
def test_each_provider_returns_valid_evaluation_decisions(provider_name, decision):
    provider, _ = provider_factory(provider_name, evaluation(decision))
    result = provider.evaluate(evaluation_request())
    assert result.decision is decision
    assert result.evaluator_provenance is not None
    assert result.evaluator_provenance.provider_id == provider_name


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "gemini"])
def test_evaluator_request_contains_context_and_complete_decomposition(provider_name):
    result = evaluation(SemanticEvaluationDecision.ACCEPT)
    provider, client = provider_factory(provider_name, result)
    request = evaluation_request()
    provider.evaluate(request)

    if provider_name == "openai":
        call = client.responses.calls[0]
        payload = json.loads(call["input"][1]["content"])
        assert call["text_format"] is SemanticEvaluation
    elif provider_name == "deepseek":
        call = client.chat.completions.calls[0]
        payload = json.loads(
            call["messages"][0]["content"].split("INPUT JSON:\n", 1)[1]
        )
        assert call["response_format"] == {"type": "json_object"}
    else:
        call = client.models.calls[0]
        payload = json.loads(call["contents"].split("INPUT JSON:\n", 1)[1])
        assert call["config"]["response_schema"] is SemanticEvaluation

    assert payload["task"]["task_name"] == "Review an invoice"
    assert payload["task_context"] == {"department": "accounts payable"}
    assert len(payload["operational_decomposition"]["operational_subtasks"]) == 2
    assert payload["rubric_version"] == SEMANTIC_EVALUATION_RUBRIC_VERSION


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "gemini"])
@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda result: result.model_copy(update={"rubric_version": "0.9"}),
            id="rubric-mismatch",
        ),
        pytest.param(
            lambda result: result.model_copy(
                update={"findings": (finding(subtask_id="unknown-subtask"),)}
            ),
            id="unknown-subtask",
        ),
    ],
)
def test_provider_rejects_incompatible_evaluation_contract(provider_name, mutate):
    result = mutate(evaluation(SemanticEvaluationDecision.REPAIR))
    provider, _ = provider_factory(provider_name, result)
    with pytest.raises(ProviderOutputError):
        provider.evaluate(evaluation_request())


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "gemini"])
def test_provider_rejects_invalid_or_empty_structured_output(provider_name):
    if provider_name == "openai" or provider_name == "deepseek":
        provider, _ = provider_factory(provider_name, None)
    else:
        provider, _ = provider_factory(provider_name, None)
    with pytest.raises(ProviderOutputError):
        provider.evaluate(evaluation_request())


def test_openai_parse_validation_failure_is_output_error_not_semantic_reject():
    class InvalidJSONError(ValueError):
        pass

    provider, _ = provider_factory(
        "openai", None, error=InvalidJSONError("Invalid JSON: EOF")
    )
    with pytest.raises(ProviderOutputError, match="structured output"):
        provider.evaluate(evaluation_request())


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "gemini"])
def test_provider_api_failures_are_not_semantic_rejections(provider_name):
    provider, _ = provider_factory(
        provider_name, None, error=TimeoutError("request timed out")
    )
    with pytest.raises(ProviderExecutionError) as error:
        provider.evaluate(evaluation_request())
    assert not isinstance(error.value, ProviderOutputError)
    assert error.value.__cause__ is not None


def test_authentication_failure_remains_distinct_from_semantic_rejection():
    class AuthenticationError(Exception):
        pass

    provider, _ = provider_factory(
        "deepseek", None, error=AuthenticationError("invalid key")
    )
    with pytest.raises(ProviderAuthenticationError):
        provider.evaluate(evaluation_request())


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "gemini"])
def test_evaluator_tracing_has_distinct_stage_and_correlation(tmp_path, provider_name):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider, _ = provider_factory(
        provider_name,
        evaluation(SemanticEvaluationDecision.ACCEPT),
        tracer=tracer,
    )
    request = evaluation_request()
    provider.evaluate(request)
    records = [
        json.loads(line)
        for line in (tmp_path / "task_decomposition.jsonl").read_text().splitlines()
    ]
    evaluator_records = [
        record for record in records if record["stage"] == "semantic_evaluation"
    ]
    assert evaluator_records
    assert {record["correlation_id"] for record in evaluator_records} == {
        request.correlation_id
    }
    assert {record["event"] for record in evaluator_records} >= {
        "llm.request",
        "llm.response",
        "llm.parsed",
        "validation.evaluation",
    }
