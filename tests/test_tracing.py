import json

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
from test_provider_application import request
from test_staged_pipeline import make_operational

from task_decomposition import (
    ProviderOutputError,
    ProviderSemanticValidationError,
    TraceLogger,
    decompose_task,
)
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider
from task_decomposition.providers.openai import OpenAIDecompositionProvider


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_tracing_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("TASK_DECOMPOSITION_TRACE_ENABLED", raising=False)
    tracer = TraceLogger.from_env()
    tracer.emit("test.disabled", data={"api_key": "sk-never-written"})
    assert not list(tmp_path.iterdir())


def test_successful_generation_writes_structured_trace_with_correlation_id(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    client = FakeClient(outputs={type(make_operational()): make_operational()})
    provider = OpenAIDecompositionProvider(client=client, tracer=tracer)

    provider.generate_operational_decomposition(openai_requests()[0])

    events = records(tmp_path / "task_decomposition.jsonl")
    names = [event["event"] for event in events]
    assert names == [
        "trace.session",
        "llm.request",
        "llm.response",
        "llm.parsed",
        "validation.structural",
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

    text = (tmp_path / "task_decomposition.jsonl").read_text()
    assert "super-secret" not in text
    assert "bearer-secret" not in text
    assert "123456789012345678901234" not in text
    event = records(tmp_path / "task_decomposition.jsonl")[0]
    assert event["data"]["api_key"] == "[REDACTED]"
    assert event["data"]["authorization"] == "[REDACTED]"


def test_empty_openai_response_is_traced_before_output_error(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = OpenAIDecompositionProvider(client=FakeClient(), tracer=tracer)

    with pytest.raises(ProviderOutputError, match="no structured output"):
        provider.generate_operational_decomposition(openai_requests()[0])

    events = records(tmp_path / "task_decomposition.jsonl")
    assert events[-1]["event"] == "validation.structural"
    assert events[-1]["data"]["result"] == "failure"
    assert any(event["event"] == "llm.response" for event in events)


def test_empty_response_records_structural_failure_and_correlation_id(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = DeepSeekDecompositionProvider(
        client=FakeDeepSeekClient(outputs=[""]),
        tracer=tracer,
    )

    with pytest.raises(ProviderOutputError, match="no structured output"):
        provider.generate_operational_decomposition(deepseek_requests()[0])

    events = records(tmp_path / "task_decomposition.jsonl")
    assert events[-1]["event"] == "validation.structural"
    assert all(event["correlation_id"] == "request-1" for event in events)


def test_malformed_json_records_exception(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    provider = DeepSeekDecompositionProvider(
        client=FakeDeepSeekClient(outputs=["not json"]),
        tracer=tracer,
    )

    with pytest.raises(ProviderOutputError, match="malformed JSON"):
        provider.generate_operational_decomposition(deepseek_requests()[0])

    events = records(tmp_path / "task_decomposition.jsonl")
    assert any(event["event"] == "llm.exception" for event in events)


def test_semantic_repair_trace_contains_feedback_and_repaired_output(tmp_path):
    tracer = TraceLogger(enabled=True, directory=tmp_path, console=False)
    repaired = make_operational()
    provider = RepairProvider([repaired])
    provider.tracer = tracer

    result = decompose_task(request(), provider)

    assert result.operational_decomposition == repaired
    events = records(tmp_path / "task_decomposition.jsonl")
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
    provider = RepairProvider([invalid, invalid])
    provider.tracer = tracer

    with pytest.raises(ProviderSemanticValidationError):
        decompose_task(request(), provider)

    events = records(tmp_path / "task_decomposition.jsonl")
    repair_requests = [event for event in events if event["event"] == "repair.request"]
    assert [event["attempt"] for event in repair_requests] == [1, 2]
    assert any(
        event["event"] == "validation.semantic" and event["data"]["result"] == "failure"
        for event in events
    )
