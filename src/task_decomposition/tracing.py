"""Opt-in, provider-neutral JSONL tracing for LLM-backed decomposition."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_CURRENT_TRACE: ContextVar[tuple[TraceLogger, str] | None] = ContextVar(
    "task_decomposition_trace", default=None
)
_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|authorization|credential|password|secret|token)", re.IGNORECASE
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|"
    r"\b(?:sk|rk)-[A-Za-z0-9_-]{12,}\b|"
    r"\bAIza[0-9A-Za-z_-]{20,}\b"
)
_MISSING = object()


def repository_root() -> Path:
    """Return the checkout root containing ``pyproject.toml``."""
    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return source.parents[2]


def resolve_trace_directory(directory: str | Path | None = None) -> Path:
    """Resolve relative trace paths from the repository root, not cwd."""
    configured = Path(directory) if directory is not None else Path("logs") / "llm"
    return configured if configured.is_absolute() else repository_root() / configured


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe(value: Any, *, key: str | None = None) -> Any:
    if key and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if value is None or isinstance(value, (bool, int, float, str)):
        return (
            _SENSITIVE_VALUE.sub(r"\1[REDACTED]", value)
            if isinstance(value, str)
            else value
        )
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _safe(value.model_dump(mode="json"))
    if hasattr(value, "model_dump_json"):
        return _safe(value.model_dump_json())
    if hasattr(value, "__dict__"):
        return _safe(vars(value))
    return repr(value)


@dataclass(frozen=True)
class TraceInvocation:
    """Identity and timing for one provider SDK invocation."""

    invocation_id: str
    correlation_id: str
    started_at: float


class TraceLogger:
    """Write redacted structured events only when tracing is explicitly enabled."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        directory: str | Path | None = None,
        console: bool = True,
    ):
        self.enabled = enabled
        self.directory = resolve_trace_directory(directory)
        self.console = console
        self._trace_file: Path | None = None
        self._last_stage: str | None = None

    @classmethod
    def from_env(cls) -> TraceLogger:
        return cls(
            enabled=_env_bool("TASK_DECOMPOSITION_TRACE_ENABLED", False),
            directory=os.getenv("TASK_DECOMPOSITION_TRACE_DIR", "logs/llm"),
            console=_env_bool("TASK_DECOMPOSITION_TRACE_CONSOLE", True),
        )

    @contextmanager
    def session(self, request_id: str | None = None):
        if not self.enabled:
            yield None
            return
        current = _CURRENT_TRACE.get()
        if (
            current
            and current[0] is self
            and (request_id is None or current[1] == request_id)
        ):
            yield current[1]
            return
        correlation_id = request_id or f"td-{uuid4().hex}"
        token = _CURRENT_TRACE.set((self, correlation_id))
        try:
            self.emit(
                "trace.session",
                correlation_id=correlation_id,
                data={"request_id": request_id},
            )
            yield correlation_id
        except BaseException as exc:
            self.summary(
                result="failure",
                stage=self._last_stage,
                error={
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "cause": repr(exc.__cause__) if exc.__cause__ else None,
                },
            )
            raise
        else:
            self.summary(result="success", stage=self._last_stage)
        finally:
            _CURRENT_TRACE.reset(token)

    def invocation(
        self,
        *,
        provider: str,
        stage: str,
        model: str,
        parameters: dict[str, Any],
        messages: Any,
        schema: Any,
        attempt: int | None = None,
        kind: str = "generation",
        request_id: str | None = None,
    ) -> TraceInvocation:
        correlation_id = self.current_correlation_id(request_id)
        invocation = TraceInvocation(uuid4().hex, correlation_id, time.perf_counter())
        self.emit(
            "llm.request",
            provider=provider,
            stage=stage,
            correlation_id=correlation_id,
            invocation_id=invocation.invocation_id,
            attempt=attempt,
            data={
                "kind": kind,
                "model": model,
                "parameters": parameters,
                "messages": messages,
                "structured_output_schema": (
                    schema.model_json_schema()
                    if hasattr(schema, "model_json_schema")
                    else schema
                ),
            },
        )
        return invocation

    def response(
        self,
        invocation: TraceInvocation,
        *,
        raw: Any,
        parsed: Any = None,
        raw_output: Any = _MISSING,
        stage: str | None = None,
    ):
        if raw_output is _MISSING:
            raw_output = _extract_raw_output(raw)
        if raw_output is _MISSING:
            raw_output_state = "unavailable"
            raw_output_available = False
        elif raw_output in (None, ""):
            raw_output_state = "empty"
            raw_output_available = True
        else:
            raw_output_state = "available"
            raw_output_available = True
        self.emit(
            "llm.response",
            stage=stage,
            correlation_id=invocation.correlation_id,
            invocation_id=invocation.invocation_id,
            data={
                "latency_ms": round(
                    (time.perf_counter() - invocation.started_at) * 1000, 3
                ),
                "result": "success",
                "raw_response": raw,
                "raw_response_available": raw is not None,
                "raw_output": raw_output if raw_output is not _MISSING else None,
                "raw_output_available": raw_output_available,
                "raw_output_state": raw_output_state,
                "usage": _safe(_response_usage(raw)),
                "response_metadata": _response_metadata(raw),
            },
        )
        if parsed is not None:
            self.emit(
                "llm.parsed",
                stage=stage,
                correlation_id=invocation.correlation_id,
                invocation_id=invocation.invocation_id,
                data={"parsed_response": parsed},
            )

    def exception(self, invocation: TraceInvocation, exc: BaseException):
        attached = {}
        for name in ("response", "body", "raw_response", "request", "status_code"):
            if hasattr(exc, name):
                attached[name] = getattr(exc, name)
        raw_attached = any(
            name in attached for name in ("response", "raw_response", "body")
        )
        self.emit(
            "llm.exception",
            correlation_id=invocation.correlation_id,
            invocation_id=invocation.invocation_id,
            data={
                "result": "failure",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "cause": repr(exc.__cause__) if exc.__cause__ else None,
                "context": repr(exc.__context__) if exc.__context__ else None,
                "exception_attributes": (vars(exc) if hasattr(exc, "__dict__") else {}),
                "attached_provider_data": attached,
                "raw_response_available": raw_attached,
                "raw_output_state": "available" if raw_attached else "unavailable",
            },
        )

    def validation(
        self,
        *,
        phase: str,
        stage: str,
        result: str,
        errors: Any = (),
        response: Any = None,
        attempt: int | None = None,
    ):
        self.emit(
            f"validation.{phase}",
            stage=stage,
            attempt=attempt,
            data={"result": result, "errors": errors, "response": response},
        )

    def repair(
        self,
        *,
        stage: str,
        attempt: int,
        feedback: Any,
        rejected_output: Any,
        repaired_output: Any = None,
    ):
        self.emit(
            "repair.output" if repaired_output is not None else "repair.request",
            stage=stage,
            attempt=attempt,
            data={
                "result": "success" if repaired_output is not None else "pending",
                "feedback": feedback,
                "rejected_output": rejected_output,
                "repaired_output": repaired_output,
            },
        )

    def emit(
        self,
        event: str,
        *,
        provider: str | None = None,
        stage: str | None = None,
        correlation_id: str | None = None,
        invocation_id: str | None = None,
        attempt: int | None = None,
        data: dict[str, Any] | None = None,
    ):
        if not self.enabled:
            return
        if stage:
            self._last_stage = stage
        correlation_id = correlation_id or self.current_correlation_id()
        event_data = _safe(data or {})
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "correlation_id": correlation_id,
            "invocation_id": invocation_id,
            "provider": provider,
            "stage": stage,
            "attempt": attempt,
            "result": event_data.get("result"),
            "data": event_data,
        }
        try:
            self._write(record)
        except OSError:
            # Tracing must never turn an otherwise valid provider call into a failure.
            self.enabled = False
            return
        if self.console:
            try:
                model = event_data.get("model") or event_data.get(
                    "response_metadata", {}
                ).get("model", "-")
                status = record["result"] or "-"
                details = [
                    f"[task-decomposition trace] {event}",
                    f"provider={provider or '-'}",
                    f"model={model}",
                    f"stage={stage or '-'}",
                    f"status={status}",
                ]
                if attempt is not None:
                    details.append(f"attempt={attempt}")
                if event == "llm.exception":
                    details.append(
                        f"error={event_data.get('exception_type')}:"
                        f"{event_data.get('message')}"
                    )
                elif event.startswith("validation.") and event_data.get("errors"):
                    details.append(f"error={event_data['errors']}")
                print(
                    " ".join(details) + f" correlation_id={correlation_id}",
                    file=sys.stderr,
                )
            except OSError:
                pass

    def summary(self, *, result: str, stage: str | None, error: Any = None):
        self.emit(
            "execution.summary",
            stage=stage,
            data={"result": result, "error": error},
        )

    def current_correlation_id(self, request_id: str | None = None) -> str:
        current = _CURRENT_TRACE.get()
        return current[1] if current else (request_id or f"td-{uuid4().hex}")

    def _write(self, record: dict[str, Any]):
        if self._trace_file is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._trace_file = self.directory / "task_decomposition.jsonl"
        with self._trace_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=repr) + "\n")


def _response_usage(raw: Any) -> Any:
    if raw is None:
        return None
    return getattr(raw, "usage", getattr(raw, "usage_metadata", None))


def _response_metadata(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    metadata = {
        key: getattr(raw, key)
        for key in ("id", "status", "model", "created", "incomplete_details")
        if hasattr(raw, key)
    }
    incomplete_details = metadata.get("incomplete_details")
    if incomplete_details is not None:
        metadata["incomplete_reason"] = getattr(incomplete_details, "reason", None) or (
            incomplete_details.get("reason")
            if isinstance(incomplete_details, dict)
            else None
        )
    return _safe(metadata)


def _extract_raw_output(raw: Any) -> Any:
    """Extract output without confusing unavailable output with an empty value."""
    if raw is None:
        return _MISSING
    for name in ("output_text", "text"):
        if hasattr(raw, name):
            return getattr(raw, name)
    choices = getattr(raw, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None and hasattr(message, "content"):
            return message.content
    return _MISSING


def current_tracer() -> TraceLogger | None:
    current = _CURRENT_TRACE.get()
    return current[0] if current else None


__all__ = ["TraceInvocation", "TraceLogger", "current_tracer"]
