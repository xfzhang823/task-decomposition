"""Deterministic conversion of activity estimates into canonical support work."""

from collections import defaultdict
from decimal import Decimal

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
)
from task_decomposition.contracts.stages import (
    ActivityEffortEstimation,
    HumanAgentActivityCategory,
    HumanAgentActivityModel,
)
from task_decomposition.errors import (
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
)


def resolve_activity_support_work(
    estimation: ActivityEffortEstimation,
    activities: HumanAgentActivityModel,
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
) -> SupportWorkInputs:
    """Convert validated per-parent activity effort into support inputs.

    ``EXCEPTION_HANDLING`` is preserved in the activity model and mapped to
    ``AI_INTERACTION`` for the existing two-category accounting boundary.
    """
    by_id = {item.activity_id: item for item in activities.activities}
    totals = defaultdict(Decimal)
    for estimate in estimation.activity_effort_estimates:
        activity = by_id[estimate.activity_id]
        category = activity.category
        if category is HumanAgentActivityCategory.AI_VERIFICATION:
            target = HumanAgentActivityCategory.AI_VERIFICATION
        else:
            target = HumanAgentActivityCategory.AI_INTERACTION
        totals[target] += (
            estimate.expected_occurrences_per_parent_output
            * estimate.active_effort_per_occurrence.value
        )

    if isinstance(accounting_input, AbsoluteEffortInput):
        baseline = accounting_input.baseline_human_effort
        for estimate in estimation.activity_effort_estimates:
            effort = estimate.expected_effort_per_parent_output
            if (
                effort.unit is not baseline.unit
                or effort.time_basis is not baseline.time_basis
            ):
                raise IncompatibleEffortUnitError(
                    "activity effort must match supplied baseline unit/time basis"
                )
        return SupportWorkInputs(
            ai_interaction=SupportWorkInput(
                value=totals[HumanAgentActivityCategory.AI_INTERACTION],
                basis=RatioBasis.ABSOLUTE_EFFORT,
                unit=baseline.unit,
                time_basis=baseline.time_basis,
            ),
            ai_verification=SupportWorkInput(
                value=totals[HumanAgentActivityCategory.AI_VERIFICATION],
                basis=RatioBasis.ABSOLUTE_EFFORT,
                unit=baseline.unit,
                time_basis=baseline.time_basis,
            ),
        )

    if not estimation.activity_effort_estimates:
        return SupportWorkInputs(
            ai_interaction=SupportWorkInput(
                value=Decimal(0), basis=RatioBasis.NORMALIZED_CONTRIBUTION
            ),
            ai_verification=SupportWorkInput(
                value=Decimal(0), basis=RatioBasis.NORMALIZED_CONTRIBUTION
            ),
        )

    baseline = estimation.estimated_baseline_effort_per_parent_output
    if baseline is None or baseline.value <= 0:
        raise MissingAccountingInputError(
            "activity-based normalized estimation requires a positive estimated baseline calibration"
        )
    for estimate in estimation.activity_effort_estimates:
        effort = estimate.expected_effort_per_parent_output
        if (
            effort.unit is not baseline.unit
            or effort.time_basis is not baseline.time_basis
        ):
            raise IncompatibleEffortUnitError(
                "activity effort must match estimated baseline unit/time basis"
            )
    return SupportWorkInputs(
        ai_interaction=SupportWorkInput(
            value=totals[HumanAgentActivityCategory.AI_INTERACTION] / baseline.value,
            basis=RatioBasis.NORMALIZED_CONTRIBUTION,
        ),
        ai_verification=SupportWorkInput(
            value=totals[HumanAgentActivityCategory.AI_VERIFICATION] / baseline.value,
            basis=RatioBasis.NORMALIZED_CONTRIBUTION,
        ),
    )


__all__ = ["resolve_activity_support_work"]
