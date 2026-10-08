"""Minimal live OpenAI example.

Requires the optional OpenAI extra and an ``OPENAI_API_KEY`` environment
variable.

Run the default example with::

    python examples/openai_decompose.py

Provide a custom task with command-line options::

TASK_DECOMPOSITION_TRACE_ENABLED=true \
TASK_DECOMPOSITION_TRACE_DIR=logs/llm \
TASK_DECOMPOSITION_TRACE_CONSOLE=true \
python examples/openai_decompose.py \
  --task-name "Review an invoice" \
  --task-description "Validate the invoice and approve or reject it."

Use ``--help`` to see all available options.
"""

import argparse
import os
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPOSITORY_ROOT / "src"))

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

from task_decomposition.providers.openai import (
    OpenAIDecompositionProvider,
)

def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from the repository's .env file."""
    dotenv_path = _REPOSITORY_ROOT / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()

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
