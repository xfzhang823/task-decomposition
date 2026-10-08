"""Provider-independent semantic assertions for staged outputs."""

import re
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
    "compare",
    "assess",
    "evaluate",
    "determine",
    "decide",
    "analyze",
    "investigate",
    "research",
    "inspect",
    "reconcile",
    "calculate",
    "apply",
    "enter",
    "modify",
    "communicate",
    "contact",
    "operate",
    "approve",
    "reject",
    "authorize",
    "prepare",
    "assign",
    "select",
    "resolve",
    "document",
)

_ABSTRACT_LABELS = (
    re.compile(r"^(?:make|reach|take) (?:an? )?(?:approval )?decision$"),
    re.compile(r"^(?:ensure|achieve|complete|finish) .+$"),
    re.compile(r"^(?:.+ )?(?:approved|rejected|completed|processed)$"),
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
    """Require a distinct unit of time-consuming operational work."""
    issues = operational_subtask_semantic_errors(output)
    if issues:
        raise SemanticAssertionError("; ".join(issues))


def operational_subtask_semantic_errors(
    output: OperationalDecomposition,
) -> tuple[str, ...]:
    """Return all semantic defects, including the affected subtask IDs."""
    assert_no_forbidden_meta_language(output)
    issues: list[str] = []
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
        if any(pattern.fullmatch(text) for pattern in _ABSTRACT_LABELS):
            issues.append(
                f"subtask {subtask.subtask_id!r} ({subtask.subtask_name!r}) is a vague goal, state, or outcome; describe the work being performed"
            )
        elif not any(
            re.search(rf"\b{re.escape(verb)}(?:s|ed|ing)?\b", text)
            for verb in _OPERATIONAL_VERBS
        ):
            issues.append(
                f"subtask {subtask.subtask_id!r} ({subtask.subtask_name!r}) does not identify a reasonable unit of operational work"
            )
    return tuple(issues)


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
    "operational_subtask_semantic_errors",
]
