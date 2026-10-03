"""Minimal live OpenAI example; requires the optional openai extra and API key."""

from task_decomposition import (
    AbsoluteEffortInput,
    TaskDecompositionRequest,
    EffortQuantity,
    EffortUnit,
    SupportWorkInput,
    SupportWorkInputs,
    TaskReference,
    TimeBasis,
    RatioBasis,
    decompose,
)
from task_decomposition.providers.openai import OpenAIDecompositionProvider


def main() -> None:
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

    request = TaskDecompositionRequest(
        task=TaskReference(
            task_id="example-task",
            task_name="Process a customer account update request",
            task_description="Receive, verify, apply, and communicate a customer account change.",
        ),
        task_context={"domain": "customer_support"},
        baseline_effort=None,
    )
    accounting_input = AbsoluteEffortInput(
        baseline_human_effort=effort(100),
        retained_human_work=effort(60),
        gross_removed_work=effort(40),
        support_work=SupportWorkInputs(
            governance=support(4),
            operational_support=support(8),
            lifecycle_support=support(2),
        ),
    )
    result = decompose(
        request,
        OpenAIDecompositionProvider(),
        transformation_context={
            "goal": "Reduce avoidable manual work while retaining required controls."
        },
        accounting_input=accounting_input,
    )
    print(result.accounting.model_dump(mode="json"))


if __name__ == "__main__":
    main()
