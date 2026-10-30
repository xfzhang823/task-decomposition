"""End-to-end supplier-invoice baseline and normalized transformation example.

This example requires the OpenAI extra and ``OPENAI_API_KEY``. Running it makes
provider calls; inspecting the source or compiling it does not.

Run from an installed checkout with::

    python examples/supplier_invoice_transformation.py
"""

from task_decomposition import (
    ParentOutputContract,
    TaskDecompositionRequest,
    TaskReference,
    decompose_task,
    estimate_transformation,
)

PROVIDER = "openai"
MODEL = "gpt-4o-mini"


def _print_baseline(baseline) -> None:
    """Print the structured baseline decomposition and effort details."""
    allocations = {
        item.subtask_id: item for item in baseline.baseline_effort_allocations
    }
    print("\nBaseline subtasks and normalized allocations")
    for subtask in baseline.operational_decomposition.operational_subtasks:
        allocation = allocations.get(subtask.subtask_id)
        print(f"- {subtask.subtask_id}: {subtask.subtask_name}")
        print(f"  description: {subtask.description or '(not supplied)'}")
        if allocation is not None:
            print(f"  weight_ratio: {allocation.weight_ratio}")
            print(f"  effort: {allocation.effort}")
        print(f"  effort_rationale: {subtask.effort_rationale}")

    estimation = baseline.baseline_effort_estimation
    if estimation is None:
        print("  baseline assumptions: no bottom-up estimate was returned")
        return
    print("\nBaseline provider effort assumptions")
    for estimate in estimation.estimates:
        print(
            f"- {estimate.subtask_id}: occurrences="
            f"{estimate.expected_occurrences_per_parent_output}, "
            f"active_effort={estimate.active_effort_per_occurrence}"
        )
        print(f"  rationale: {estimate.rationale}")
        print(f"  assumptions: {estimate.assumptions or '(none)'}")
        print(f"  supporting references: {estimate.provenance_refs or '(none)'}")


def _print_transformation(result) -> None:
    """Print transformation facts, accounting, and available provenance."""
    accounting = result.accounting
    print("\nNormalized transformation accounting")
    print(f"W0: {accounting.w0}")
    print(f"W1: {accounting.w1}")
    print(f"Gross removed work ratio: {accounting.gross_removed_work_ratio}")
    print(f"Net remaining work ratio: {accounting.net_remaining_work_ratio}")
    print(f"Net substitution ratio: {accounting.net_substitution_ratio}")
    print(f"Net augmentation multiplier: {accounting.net_augmentation_multiplier}")

    print("\nRETAIN/REMOVE classifications")
    for item in result.retain_remove_classification.classified_subtasks:
        print(
            f"- {item.subtask_id}: {item.classification.value.upper()}"
            f"; rationale: {item.rationale or '(not supplied)'}"
        )
    print(
        "classification supporting references: "
        f"{result.retain_remove_classification.provenance_refs or '(none)'}"
    )

    synthesis = result.agentic_task_synthesis
    print("\nSynthesized agentic tasks")
    for task in synthesis.agentic_tasks if synthesis is not None else ():
        print(f"- {task.agentic_task_id}: {task.agentic_task_name}")
        print(f"  description: {task.description}")
        print(f"  source subtasks: {task.source_subtask_ids}")
        print(f"  inputs: {task.required_inputs}")
        print(f"  outputs: {task.expected_outputs}")
    if synthesis is not None:
        print(f"  supporting references: {synthesis.provenance_refs or '(none)'}")

    activities = result.human_agent_activity_modeling
    print("\nHuman-agent activities")
    for activity in activities.activities if activities is not None else ():
        print(f"- {activity.activity_id}: {activity.activity_name}")
        print(f"  category: {activity.category.value}")
        print(f"  trigger: {activity.trigger}")
        print(f"  expected action: {activity.expected_action}")
        print(f"  agentic tasks: {activity.agentic_task_ids}")
    if activities is not None:
        print(f"  supporting references: {activities.provenance_refs or '(none)'}")

    estimates = result.activity_effort_estimation
    print("\nAI interaction and verification effort estimates")
    for estimate in estimates.activity_effort_estimates if estimates else ():
        print(
            f"- {estimate.activity_id}: occurrences="
            f"{estimate.expected_occurrences_per_parent_output}, "
            f"active_effort={estimate.active_effort_per_occurrence}, "
            f"expected_effort={estimate.expected_effort_per_parent_output}"
        )
        print(f"  rationale: {estimate.rationale}")
        print(f"  assumptions: {estimate.assumptions or '(none)'}")
        print(f"  supporting references: {estimate.provenance_refs or '(none)'}")

    print("\nTransformation-level assumptions")
    print(result.estimation_assumptions or "(none)")
    print("\nProvider provenance")
    for provenance in result.provider_provenance:
        print(
            f"- {provenance.provider_id}/{provenance.stage.value}: "
            f"model={provenance.model_id}, request_id={provenance.request_id}"
        )
    print(f"result supporting references: {result.provenance_refs or '(none)'}")

    print(
        "\nContract limitations: classification rationales, effort rationales, "
        "assumptions, activity triggers, and provenance are exposed where the "
        "provider returned them. Agentic tasks and human activities have no "
        "dedicated rationale or assumption fields, and individual classified "
        "subtasks do not expose per-row provenance. Provider prose outside these "
        "structured fields is not retained by the result contract."
    )


def main() -> None:
    """Run the supplier-invoice decomposition and transformation."""
    request = TaskDecompositionRequest(
        task=TaskReference(
            task_name="Review and approve a supplier invoice",
            task_description=(
                "Review a raw-material supplier invoice for authenticity, "
                "purchase-order and receipt agreement, prices, quantities, "
                "taxes, duplicate charges, and discrepancies; resolve issues "
                "and approve it for payment under company policy."
            ),
        ),
        task_context={
            "domain": "accounts_payable",
            "transformation_goal": (
                "Use AI to perform invoice checks and identify discrepancies, "
                "while a human AP approver retains final authorization before payment."
            ),
        },
        parent_output_contract=ParentOutputContract(
            output_unit="one supplier invoice approved or routed for resolution",
            completion_boundary=(
                "The invoice is checked, discrepancies are resolved or identified, "
                "and the human approval decision is made under company policy."
            ),
            scope_exclusions=(
                "payment execution after approval",
                "supplier master-data maintenance",
            ),
            source="supplied",
        ),
    )

    baseline = decompose_task(request, provider=PROVIDER, model=MODEL)
    result = estimate_transformation(
        baseline,
        provider=PROVIDER,
        model=MODEL,
        transformation_context={
            "goal": (
                "AI performs authenticity, matching, duplicate, and arithmetic checks; "
                "the human AP approver makes the final authorization decision."
            )
        },
    )
    _print_baseline(baseline)
    _print_transformation(result)


if __name__ == "__main__":
    main()
