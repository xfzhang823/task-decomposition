"""Minimal live OpenAI example.

Requires the optional OpenAI extra and an ``OPENAI_API_KEY`` environment
variable.

Run the default example with::

    python examples/openai_decompose.py

Provide a custom task with command-line options::

TASK_TRANSMORPH_TRACE_ENABLED=true \
TASK_TRANSMORPH_TRACE_CONSOLE=true \
python examples/openai_decompose.py \
  --task-name "Production Scheduling" \
  --task-description "Review production orders, inventory availability, machine capacity, and workforce availability. Develop a feasible production schedule, assign production orders to machines and shifts, resolve scheduling conflicts, and communicate the finalized schedule to production teams."

TASK_TRANSMORPH_TRACE_ENABLED=true \
TASK_TRANSMORPH_TRACE_CONSOLE=true \
python examples/openai_decompose.py \
  --task-name "Production Scheduling" \
  --task-description "Plan and coordinate manufacturing production to fulfill customer orders within available resources, operational constraints, and delivery deadlines."

Use ``--help`` to see all available options.
"""

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPOSITORY_ROOT / "src"))

from task_transmorph import (
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
    allocate_effort,
    decompose_task,
    decompose_transformation,
)
from task_transmorph.application._provider_stage import (
    call_stage,
    provider_id,
    validate_classification_response,
)
from task_transmorph.contracts.decomposition import TransformationClassification
from task_transmorph.contracts.provenance import ProviderStage
from task_transmorph.contracts.provider import RetainRemoveClassificationRequest
from task_transmorph.domain import DEFAULT_TOLERANCE
from task_transmorph.errors import (
    MissingAccountingInputError,
    MissingEffortAllocationError,
)
from task_transmorph.providers.openai import (
    OpenAIDecompositionProvider,
    OpenAIProviderConfig,
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
    parser.add_argument("--domain", default="production_scheduling")
    return parser.parse_args()


class _CachedClassificationProvider:
    """Reuse the classification used to derive the example accounting input."""

    def __init__(self, provider, classification_response):
        self._provider = provider
        self._classification_response = classification_response
        self.provider_id = provider.provider_id
        self.tracer = provider.tracer

    def classify_retain_remove(self, request):
        return self._classification_response

    def classify_added_work(self, request):
        return self._provider.classify_added_work(request)


def _derive_accounting_input(
    baseline,
    classification,
    *,
    baseline_human_effort,
    support_work,
):
    """Build absolute accounting from normalized baseline weights and labels."""
    subtasks = baseline.operational_decomposition.operational_subtasks
    weights = {
        subtask.subtask_id: subtask.relative_effort_weight for subtask in subtasks
    }
    if not weights or any(weight is None for weight in weights.values()):
        raise MissingEffortAllocationError(
            "every baseline subtask requires a relative_effort_weight"
        )
    allocation = allocate_effort(baseline_human_effort, weights)
    rows = {row.subtask_id: row for row in classification.classified_subtasks}
    if set(rows) != set(weights):
        raise MissingAccountingInputError(
            "classification must cover every weighted baseline subtask exactly once"
        )
    retained = sum(
        (
            allocation[subtask_id].value
            for subtask_id, row in rows.items()
            if row.classification is TransformationClassification.RETAIN
        ),
        Decimal(0),
    )
    removed = sum(
        (
            allocation[subtask_id].value
            for subtask_id, row in rows.items()
            if row.classification is TransformationClassification.REMOVE
        ),
        Decimal(0),
    )
    if abs(retained + removed - baseline_human_effort.value) > DEFAULT_TOLERANCE:
        raise MissingAccountingInputError(
            "classified retained and removed effort does not reconcile to baseline"
        )
    return AbsoluteEffortInput(
        baseline_human_effort=baseline_human_effort,
        retained_human_work=baseline_human_effort.model_copy(
            update={"value": retained}
        ),
        gross_removed_work=baseline_human_effort.model_copy(update={"value": removed}),
        support_work=support_work,
    )


def _classify_once(provider, baseline, transformation_context):
    """Probe classification once so accounting and final output use one result."""
    effort = EffortQuantity(
        value=100, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION
    )
    zero_support = SupportWorkInputs(
        ai_interaction=SupportWorkInput(
            value=0,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=effort.unit,
            time_basis=effort.time_basis,
        ),
        ai_verification=SupportWorkInput(
            value=0,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=effort.unit,
            time_basis=effort.time_basis,
        ),
    )
    probe_request = TransformationDecompositionRequest(
        task_decomposition=baseline,
        transformation_context=transformation_context,
        accounting_input=AbsoluteEffortInput(
            baseline_human_effort=effort,
            retained_human_work=effort,
            gross_removed_work=effort.model_copy(update={"value": 0}),
            support_work=zero_support,
        ),
    )
    response = call_stage(
        provider_id(provider),
        ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
        provider.classify_retain_remove,
        RetainRemoveClassificationRequest(
            request=probe_request,
            operational_decomposition=baseline.operational_decomposition,
        ),
    )
    classification = validate_classification_response(
        baseline.operational_decomposition, response
    )
    return response, classification


def main() -> None:
    """Run the live OpenAI task and transformation decomposition example."""
    args = _parse_args()
    unit = EffortUnit.EFFORT
    period = TimeBasis.PER_OPERATION
    provider = OpenAIDecompositionProvider(
        OpenAIProviderConfig(
            stage_output_tokens={
                ProviderStage.OPERATIONAL_DECOMPOSITION: 4000,
                ProviderStage.RETAIN_REMOVE_CLASSIFICATION: 4000,
                ProviderStage.ADDED_WORK_CLASSIFICATION: 8000,
            }
        )
    )

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

    # Keep the independently callable stages in one end-to-end trace.
    tracer = provider.tracer
    with tracer.session(request.request_id):
        baseline = decompose_task(request, provider)
        allocations = {
            item.subtask_id: item for item in baseline.baseline_effort_allocations
        }
        print("Baseline operational decomposition:")
        for subtask in baseline.operational_decomposition.operational_subtasks:
            allocation = allocations.get(subtask.subtask_id)
            share = (
                f"{allocation.weight_ratio * 100:.2f}%"
                if allocation is not None and allocation.weight_ratio is not None
                else "unallocated"
            )
            dependencies = ", ".join(subtask.depends_on) or "none"
            print(f"- {subtask.subtask_name}: {share} (depends on: {dependencies})")

        transformation_context = {}
        classification_response, classification = _classify_once(
            provider, baseline, transformation_context
        )
        accounting_input = _derive_accounting_input(
            baseline,
            classification,
            baseline_human_effort=effort(100),
            support_work=SupportWorkInputs(
                ai_interaction=support(0),
                ai_verification=support(0),
            ),
        )

        # Transformation decomposition consumes the existing baseline.
        result = decompose_transformation(
            TransformationDecompositionRequest(
                task_decomposition=baseline,
                transformation_context=transformation_context,
                accounting_input=accounting_input,
            ),
            _CachedClassificationProvider(provider, classification_response),
        )

    print(result.accounting.model_dump(mode="json"))


if __name__ == "__main__":
    main()
