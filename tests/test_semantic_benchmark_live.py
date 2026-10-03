"""Optional live semantic benchmark execution; disabled unless explicitly requested."""

import os

import pytest

from task_decomposition import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    SupportWorkInput,
    SupportWorkInputs,
    decompose,
)
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider
from task_decomposition.providers.gemini import GeminiDecompositionProvider
from task_decomposition.providers.openai import OpenAIDecompositionProvider

from benchmark_support import (
    check_hard_validity,
    load_benchmark_cases,
    render_review_artifact,
)


def _accounting_input() -> AbsoluteEffortInput:
    def quantity(value):
        return EffortQuantity(
            value=value, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION
        )

    def support(value):
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


@pytest.mark.integration
@pytest.mark.parametrize(
    ("provider_name", "provider_factory", "key_name"),
    [
        ("openai", OpenAIDecompositionProvider, "OPENAI_API_KEY"),
        ("gemini", GeminiDecompositionProvider, "GEMINI_API_KEY"),
        ("deepseek", DeepSeekDecompositionProvider, "DEEPSEEK_API_KEY"),
    ],
)
def test_optional_live_semantic_benchmark(provider_name, provider_factory, key_name):
    if os.getenv("RUN_SEMANTIC_BENCHMARKS") != "1" or not os.getenv(key_name):
        pytest.skip("set RUN_SEMANTIC_BENCHMARKS=1 and the provider key to run")

    case = load_benchmark_cases()[0]
    request = TaskDecompositionRequest(
        task=TaskReference(
            task_id=case.id,
            task_name=case.process_name,
            task_description=case.process_description,
        ),
        task_context=case.task_context,
    )
    result = decompose(
        request,
        provider_factory(),
        transformation_context=case.transformation_context,
        accounting_input=_accounting_input(),
    )

    report = check_hard_validity(result)
    assert report.valid, report.errors
    assert result.provider_provenance
    assert provider_name in {item.provider_id for item in result.provider_provenance}
    assert "## RESULT" in render_review_artifact(case, result)
