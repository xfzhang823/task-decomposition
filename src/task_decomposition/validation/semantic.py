"""Provider-independent semantic assertions for staged outputs."""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from task_decomposition.contracts.stages import OperationalDecomposition
from task_decomposition.errors import SemanticAssertionError

_FORBIDDEN_PHRASES = (
    "ai_suitability",
    "ai readiness",
    "ai-readiness",
    "readiness score",
    "readiness-score",
    "suitability score",
    "suitability-score",
    "automation readiness",
    "automation-readiness",
    "automation potential score",
    "automation-potential-score",
    "analyze the task",
    "evaluate the task",
    "generate rationale",
    "make a decision",
    "document rationale",
    "analyze request intake",
    "analyze automation opportunity",
    "make retain/remove decision",
    "document classification rationale",
    "evaluate accounting rows",
    "generate decomposition rationale",
)

_OPERATIONAL_VERBS = (
    "receive",
    "verify",
    "check",
    "update",
    "route",
    "notify",
    "close",
    "record",
    "extract",
    "open",
    "confirm",
    "validate",
    "flag",
    "send",
    "identify",
    "escalate",
    "review",
    "log",
    "process",
    "handle",
)


def assert_no_forbidden_meta_language(value: Any) -> None:
    """Reject readiness, scoring, prompt, and meta-analysis output language."""
    for text in _iter_text_values(value):
        normalized = text.lower()
        for phrase in _FORBIDDEN_PHRASES:
            if phrase in normalized:
                raise SemanticAssertionError(
                    f"forbidden staged-output phrase detected: {phrase}"
                )


def assert_operational_subtasks_are_concrete(
    output: OperationalDecomposition,
) -> None:
    """Require real operational activity language, not abstract commentary."""
    assert_no_forbidden_meta_language(output)
    for subtask in output.operational_subtasks:
        text = (
            " ".join(
                part
                for part in (subtask.subtask_name, subtask.description or "")
                if part
            )
            .strip()
            .lower()
        )
        if not any(verb in text for verb in _OPERATIONAL_VERBS):
            raise SemanticAssertionError(
                f"operational subtask is too meta or abstract: {subtask.subtask_name!r}"
            )


def _iter_text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, BaseModel):
        yield from _iter_text_values(value.model_dump(mode="python"))
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_text_values(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_text_values(item)


__all__ = [
    "assert_no_forbidden_meta_language",
    "assert_operational_subtasks_are_concrete",
]
