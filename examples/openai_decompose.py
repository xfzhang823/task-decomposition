"""Minimal live OpenAI example.

Requires the optional OpenAI extra and an ``OPENAI_API_KEY`` environment
variable.

Run the default example with::

    PYTHONPATH=src python examples/openai_decompose.py

Provide a custom task with command-line options::

    PYTHONPATH=src python examples/openai_decompose.py \\
        --task-id invoice-review \\
        --task-name "Review an invoice" \\
        --task-description "Validate invoice details and approve or reject the invoice." \\
        --domain finance

Use ``--help`` to see all available options.
"""

import argparse

from task_decomposition import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    TransformationDecompositionRequest,
    decompose_task,
    decompose_transformation,
)
from task_decomposition.providers.openai import OpenAIDecompositionProvider


def _parse_args() -> argparse.Namespace:
    """Parse task details supplied on the command line."""
    parser = argparse.ArgumentParser(
        description="Decompose a task with the OpenAI provider."
    )
    parser.add_argument("--task-id", default="example-task")
    parser.add_argument(
        "--task-name",
        default="Process a customer account update request",
    )
    parser.add_argument(
        "--task-description",
        default="Receive, verify, apply, and communicate a customer account change.",
    )
    parser.add_argument("--domain", default="customer_support")
    return parser.parse_args()


def main() -> None:
    """Run the live OpenAI task and transformation decomposition example."""
    args = _parse_args()
    unit = EffortUnit.EFFORT
    period = TimeBasis.PER_OPERATION
    provider = OpenAIDecompositionProvider()

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
            task_id=args.task_id,
            task_name=args.task_name,
            task_description=args.task_description,
        ),
        task_context={"domain": args.domain},
        baseline_effort=None,
    )

    # Task decomposition can be run and inspected independently.
    baseline = decompose_task(
        request,
        provider,
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

    # Transformation decomposition consumes the existing baseline.
    result = decompose_transformation(
        TransformationDecompositionRequest(
            task_decomposition=baseline,
            accounting_input=accounting_input,
        ),
        provider,
    )

    print(result.accounting.model_dump(mode="json"))


if __name__ == "__main__":
    main()
