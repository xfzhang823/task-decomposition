"""Run the opt-in live semantic benchmark corpus and save review artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))

from task_decomposition import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    decompose,
)
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider
from task_decomposition.providers.gemini import GeminiDecompositionProvider
from task_decomposition.providers.openai import OpenAIDecompositionProvider

from benchmark_support import (
    check_hard_validity,
    load_benchmark_cases,
    render_review_artifact,
    review_task_semantics,
    review_transformation_semantics,
)


RESULTS_ROOT = Path(__file__).parent / "results"


def _accounting_input() -> AbsoluteEffortInput:
    def quantity(value: int) -> EffortQuantity:
        return EffortQuantity(
            value=value, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION
        )

    def support(value: int) -> SupportWorkInput:
        return SupportWorkInput(
            value=value,
            basis="absolute_effort",
            unit=EffortUnit.EFFORT,
            time_basis=TimeBasis.PER_OPERATION,
        )

    return AbsoluteEffortInput(
        baseline_human_effort=quantity(100),
        retained_human_work=quantity(60),
        gross_removed_work=quantity(40),
        support_work=SupportWorkInputs(
            governance=support(4),
            operational_support=support(8),
            lifecycle_support=support(2),
        ),
    )


def _provider_specs() -> dict[str, tuple[str, Callable[[], object]]]:
    return {
        "openai": ("OPENAI_API_KEY", OpenAIDecompositionProvider),
        "gemini": ("GEMINI_API_KEY", GeminiDecompositionProvider),
        "deepseek": ("DEEPSEEK_API_KEY", DeepSeekDecompositionProvider),
    }


def _provider_model(provider: object) -> str:
    return str(getattr(getattr(provider, "config", None), "model", "unknown"))


def _write_result(case, result, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = check_hard_validity(result)
    review = {
        "hard_validity": {"valid": report.valid, "errors": list(report.errors)},
        "task_semantics": review_task_semantics(case, result.task_decomposition),
        "transformation_semantics": review_transformation_semantics(case, result),
    }
    (output_dir / f"{case.id}.md").write_text(
        render_review_artifact(case, result), encoding="utf-8"
    )
    payload: dict[str, Any] = {
        "case": case.model_dump(mode="json"),
        "review": review,
        "result": result.model_dump(mode="json"),
    }
    (output_dir / f"{case.id}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_failure(case, exc: Exception, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case.id,
        "process_name": case.process_name,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    (output_dir / f"{case.id}.error.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_provider(
    provider_name: str,
    provider_factory: Callable[[], object],
    cases: tuple[object, ...],
    results_root: Path,
) -> tuple[int, int]:
    provider = provider_factory()
    model = _provider_model(provider)
    output_dir = results_root / provider_name / model
    succeeded = 0
    failed = 0
    for case in cases:
        request = TaskDecompositionRequest(
            task=TaskReference(
                task_id=case.id,
                task_name=case.process_name,
                task_description=case.process_description,
            ),
            task_context=case.task_context,
        )
        try:
            result = decompose(
                request,
                provider,
                transformation_context=case.transformation_context,
                accounting_input=_accounting_input(),
            )
            _write_result(case, result, output_dir)
            succeeded += 1
            print(f"{provider_name}/{model}: {case.id}: valid")
        except Exception as exc:
            _write_failure(case, exc, output_dir)
            failed += 1
            print(f"{provider_name}/{model}: {case.id}: {type(exc).__name__}")
    return succeeded, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-providers", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--results-root", type=Path, default=RESULTS_ROOT)
    args = parser.parse_args()

    if os.getenv("RUN_SEMANTIC_BENCHMARKS") != "1":
        print("Live benchmark skipped: set RUN_SEMANTIC_BENCHMARKS=1 to enable.")
        return 0

    available = [
        (name, key, factory)
        for name, (key, factory) in _provider_specs().items()
        if os.getenv(key)
    ]
    if not available:
        print("Live benchmark skipped: no configured provider API key found.")
        return 0

    cases = load_benchmark_cases()
    primary = available[:1]
    additional = available[1:] if args.all_providers else available[1:]
    selected = primary + additional
    total_succeeded = 0
    total_failed = 0
    for index, (name, _key, factory) in enumerate(selected):
        provider_cases = cases
        if index > 0 and not args.all_providers:
            provider_cases = cases[: min(3, len(cases))]
        if args.limit is not None:
            provider_cases = provider_cases[: args.limit]
        succeeded, failed = run_provider(
            name, factory, provider_cases, args.results_root
        )
        total_succeeded += succeeded
        total_failed += failed
    print(
        f"Live benchmark complete: {total_succeeded} succeeded, {total_failed} failed."
    )
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
