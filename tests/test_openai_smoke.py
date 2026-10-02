"""Optional live OpenAI smoke test; never required for normal test runs."""

import os

import pytest

from task_decomposition import (
    AbsoluteEffortInput,
    DecompositionRequest,
    EffortQuantity,
    EffortUnit,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
    TaskReference,
    TimeBasis,
    decompose,
)
from task_decomposition.providers.openai import OpenAIDecompositionProvider


@pytest.mark.integration
def test_live_openai_three_stage_decomposition():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not configured")

    unit = EffortUnit.EFFORT
    period = TimeBasis.PER_OPERATION

    def effort(value):
        return EffortQuantity(value=value, unit=unit, time_basis=period)

    def support(value):
        return SupportWorkInput(
            value=value,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=unit,
            time_basis=period,
        )

    request = DecompositionRequest(
        task=TaskReference(
            task_id="live-smoke-task",
            task_name="Process a customer address update",
            task_description="Receive a request, verify it, update the record, and notify the customer.",
        ),
        transformation_intent="Identify which human activities remain or are removed after assistance is introduced.",
        context={"domain": "customer_support"},
        accounting_input=AbsoluteEffortInput(
            baseline_human_effort=effort(100),
            retained_human_work=effort(60),
            gross_removed_work=effort(40),
            support_work=SupportWorkInputs(
                governance=support(4),
                operational_support=support(8),
                lifecycle_support=support(2),
            ),
        ),
    )
    result = decompose(request, OpenAIDecompositionProvider())
    assert len(result.provider_provenance) == 3
    assert result.accounting.w0 == 100
