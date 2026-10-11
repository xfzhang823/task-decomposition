import json
import re
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from test_deepseek_provider import (
    FakeDeepSeekClient,
)
from test_deepseek_provider import (
    stage_requests as deepseek_requests,
)
from test_openai_provider import FakeClient
from test_openai_provider import stage_requests as openai_requests
from test_operational_repair import RepairProvider, invalid_operational
from test_provider_application import FakeProvider as ApplicationFakeProvider
from test_provider_application import account_input, request
from test_semantic_evaluator_providers import evaluation, evaluation_request
from test_staged_pipeline import make_operational

from task_decomposition import (
    ProviderOutputError,
    ProviderSemanticValidationError,
    ProviderStage,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    TraceLogger,
    decompose,
    decompose_task,
    tracing,
)
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider
from task_decomposition.providers.openai import (
    OpenAIDecompositionProvider,
    OpenAIProviderConfig,
)


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def trace_file(directory):
    files = sorted(directory.glob("task_decomposition_*.jsonl"))
    assert len(files) == 1
    return files[0]


def test_tracing_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("TASK_DECOMPOSITION_TRACE_ENABLED", raising=False)
    tracer = TraceLogger.from_env()
    tracer.emit("test.disabled", data={"api_key": "sk-never-written"})
    assert not list(tmp_path.iterdir())


def test_default_trace_directory_is_repository_root_logs_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing, "repository_root", lambda: tmp_path)
    tracer = TraceLogger(enabled=True, console=False)
    tracer.emit("test.default")
    path = trace_file(tmp_path / "logs" / "llm")
    assert re.fullmatch(r"task_decomposition_\d{4}-\d{2}-\d{2}_\d{6}\.jsonl", path.name)


def test_trace_directory_override_is_resolved_from_repository_root(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tracing, "repository_root", lambda: tmp_path)
    tracer = TraceLogger(enabled=True, directory="custom-logs", console=False)
    tracer.emit("test.override")
    assert trace_file(tmp_path / "custom-logs").exists()
    monkeypatch.setenv("TASK_DECOMPOSITION_TRACE_ENABLED", "true")
    monkeypatch.setenv("TASK_DECOMPOSITION_TRACE_DIR", "env-logs")
    env_tracer = TraceLogger.from_env()
    env_tracer.emit("test.env-override")
    assert trace_file(tmp_path / "env-logs").exists()


def test_successful_generation_writes_structured_trace_with_correlation_id(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    client = FakeClient(outputs={type(make_operational()): make_operational()})
    provider = OpenAIDecompositionProvider(client=client, tracer=tracer)

    provider.generate_operational_decomposition(openai_requests()[0])

    events = records(trace_file(tmp_path))
    names = [event["event"] for event in events]
    assert names == [
        "trace.session",
        "llm.request",
        "llm.response",
        "llm.parsed",
        "validation.structural",
        "execution.summary",
    ]
    assert {event["correlation_id"] for event in events} == {"request-1"}
    request_event = events[1]
    assert request_event["data"]["model"] == "gpt-4o-mini"
    assert (
        request_event["data"]["structured_output_schema"]["title"]
        == "OperationalDecomposition"
    )


def test_redaction_applies_to_keys_and_authorization_values(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    tracer.emit(
        "test.redaction",
        data={
            "api_key": "sk-super-secret-value",
            "authorization": "Bearer bearer-secret",
            "nested": "AIza123456789012345678901234",
        },
    )

    text = trace_file(tmp_path).read_text()
    assert "super-secret" not in text
    assert "bearer-secret" not in text
    assert "123456789012345678901234" not in text
    event = records(trace_file(tmp_path))[0]
    assert event["data"]["api_key"] == "[REDACTED]"
    assert event["data"]["authorization"] == "[REDACTED]"


def test_empty_openai_response_is_traced_before_output_error(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = OpenAIDecompositionProvider(client=FakeClient(), tracer=tracer)

    with pytest.raises(ProviderOutputError, match="no structured output"):
        provider.generate_operational_decomposition(openai_requests()[0])

    events = records(trace_file(tmp_path))
    validation = [
        event for event in events if event["event"] == "validation.structural"
    ][-1]
    assert validation["result"] == "failure"


def test_openai_trace_keeps_budget_usage_and_incomplete_reason(tmp_path):
    class Responses:
        def create(self, **kwargs):
            return SimpleNamespace(
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                output_text="",
                output=(),
                usage=SimpleNamespace(
                    input_tokens=123,
                    output_tokens=321,
                    total_tokens=444,
                ),
            )

    class Client:
        responses = Responses()

    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = OpenAIDecompositionProvider(
        client=Client(),
        tracer=tracer,
        config=OpenAIProviderConfig(
            stage_output_tokens={
                ProviderStage.OPERATIONAL_DECOMPOSITION: 321,
            }
        ),
    )

    with pytest.raises(ProviderOutputError, match="max_output_tokens"):
        provider.generate_operational_decomposition(openai_requests()[0])

    events = records(trace_file(tmp_path))
    request_event = next(event for event in events if event["event"] == "llm.request")
    response_event = next(event for event in events if event["event"] == "llm.response")
    assert request_event["data"]["parameters"]["max_output_tokens"] == 321
    assert response_event["data"]["usage"]["output_tokens"] == 321
    assert response_event["data"]["response_metadata"]["incomplete_reason"] == (
        "max_output_tokens"
    )
    response = [event for event in events if event["event"] == "llm.response"][-1]
    assert response["data"]["raw_response_available"] is True
    assert response["data"]["raw_output_state"] == "empty"


def test_empty_response_records_structural_failure_and_correlation_id(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = DeepSeekDecompositionProvider(
        client=FakeDeepSeekClient(outputs=[""]),
        tracer=tracer,
    )

    with pytest.raises(ProviderOutputError, match="no structured output"):
        provider.generate_operational_decomposition(deepseek_requests()[0])

    events = records(trace_file(tmp_path))
    validation = [
        event for event in events if event["event"] == "validation.structural"
    ][-1]
    response = [event for event in events if event["event"] == "llm.response"][-1]
    assert response["data"]["raw_response_available"] is True
    assert response["data"]["raw_output_state"] == "empty"
    assert validation["result"] == "failure"
    assert all(event["correlation_id"] == "request-1" for event in events)


def test_malformed_json_records_exception(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = DeepSeekDecompositionProvider(
        client=FakeDeepSeekClient(outputs=["not json"]),
        tracer=tracer,
    )

    with pytest.raises(ProviderOutputError, match="malformed JSON"):
        provider.generate_operational_decomposition(deepseek_requests()[0])

    events = records(trace_file(tmp_path))
    assert any(event["event"] == "llm.exception" for event in events)


def test_semantic_repair_trace_contains_feedback_and_repaired_output(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    repaired = make_operational()
    provider = RepairProvider([repaired])
    provider.tracer = tracer

    result = decompose_task(request(), provider)

    assert result.operational_decomposition == repaired
    events = records(trace_file(tmp_path))
    repair_events = [event for event in events if event["event"].startswith("repair.")]
    assert [event["event"] for event in repair_events] == [
        "repair.request",
        "repair.output",
    ]
    assert repair_events[0]["attempt"] == 1
    assert repair_events[0]["data"]["feedback"]
    assert repair_events[1]["data"]["repaired_output"]


def test_semantic_repair_failure_is_traced_with_attempts(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    invalid = invalid_operational(
        "Make approval decision", "Invoice approved", "Complete review"
    )
    provider = RepairProvider([invalid, invalid], accept_after_repairs=False)
    provider.tracer = tracer

    with pytest.raises(ProviderSemanticValidationError):
        decompose_task(request(), provider)

    events = records(trace_file(tmp_path))
    repair_requests = [event for event in events if event["event"] == "repair.request"]
    assert [event["attempt"] for event in repair_requests] == [1, 2]
    assert any(
        event["event"] == "validation.evaluation" and event["result"] == "repair"
        for event in events
    )


def test_concurrent_sessions_reserve_distinct_timestamped_files(tmp_path):
    def write_trace(index):
        tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
        with tracer.session(f"request-{index}"):
            tracer.emit("test.concurrent", data={"index": index})

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(write_trace, (1, 2)))

    files = sorted(tmp_path.glob("task_decomposition_*.jsonl"))
    assert len(files) == 2
    assert {records(path)[0]["correlation_id"] for path in files} == {
        "request-1",
        "request-2",
    }


def test_multiple_llm_calls_share_minimal_execution_trace(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    client = FakeClient(
        outputs={
            type(make_operational()): make_operational(),
            SemanticEvaluation: evaluation(SemanticEvaluationDecision.ACCEPT),
        }
    )
    provider = OpenAIDecompositionProvider(client=client, tracer=tracer)

    with tracer.session("request-1"):
        provider.generate_operational_decomposition(openai_requests()[0])
        provider.evaluate(
            evaluation_request().model_copy(
                update={"correlation_id": "request-1", "request_id": "request-1"}
            )
        )

    events = records(trace_file(tmp_path))
    assert {event["correlation_id"] for event in events} == {"request-1"}
    assert {event.get("stage") for event in events} >= {
        "operational_decomposition",
        "semantic_evaluation",
    }
    assert all("invocation_id" not in event for event in events)


def test_composed_execution_keeps_all_application_stages_in_one_trace(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = ApplicationFakeProvider()
    provider.tracer = tracer

    decompose(
        request(),
        provider,
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )

    events = records(trace_file(tmp_path))
    assert len({event["correlation_id"] for event in events}) == 1
    assert sum(event["event"] == "trace.session" for event in events) == 1
    assert {
        event.get("stage")
        for event in events
        if event["event"].startswith(("validation.", "execution."))
    } >= {
        "operational_decomposition",
        "semantic_evaluation",
        "retain_remove_classification",
        "added_work_classification",
    }
    assert all(all(value is not None for value in event.values()) for event in events)
