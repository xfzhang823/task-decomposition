"""Deterministic conversion of activity estimates into canonical support work."""

from collections import defaultdict
from decimal import Decimal

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
    TimeBasis,
    convert_effort_quantity,
)
from task_decomposition.contracts.stages import (
    ActivityEffortEstimation,
    HumanAgentActivityCategory,
    HumanAgentActivityModel,
)
from task_decomposition.errors import (
    ContractValidationError,
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
)


def resolve_activity_support_work(
    estimation: ActivityEffortEstimation,
    activities: HumanAgentActivityModel,
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    *,
    baseline_effort: EffortQuantity | None = None,
) -> SupportWorkInputs:
    """Convert validated per-parent activity effort into support inputs.

    ``EXCEPTION_HANDLING`` is preserved in the activity model and mapped to
    ``AI_INTERACTION`` for the existing two-category accounting boundary.
    """
    by_id = {item.activity_id: item for item in activities.activities}
    totals = defaultdict(Decimal)
    selected_baseline = baseline_effort
    if selected_baseline is None and isinstance(accounting_input, AbsoluteEffortInput):
        selected_baseline = accounting_input.baseline_human_effort
    if (
        selected_baseline is not None
        and selected_baseline.time_basis is not TimeBasis.PER_OPERATION
    ):
        raise IncompatibleEffortUnitError(
            "activity-based baseline calibration must use a per-operation time basis"
        )
    for estimate in estimation.activity_effort_estimates:
        activity = by_id[estimate.activity_id]
        category = activity.category
        if category is HumanAgentActivityCategory.AI_VERIFICATION:
            target = HumanAgentActivityCategory.AI_VERIFICATION
        else:
            target = HumanAgentActivityCategory.AI_INTERACTION
        expected_effort = estimate.expected_effort_per_parent_output
        if selected_baseline is not None:
            try:
                expected_effort = convert_effort_quantity(
                    expected_effort, selected_baseline.unit
                )
            except ContractValidationError as exc:
                raise IncompatibleEffortUnitError(str(exc)) from exc
            if expected_effort.time_basis is not selected_baseline.time_basis:
                raise IncompatibleEffortUnitError(
                    "activity effort must use the same time basis as baseline calibration"
                )
        totals[target] += expected_effort.value

    if isinstance(accounting_input, AbsoluteEffortInput):
        baseline = selected_baseline
        if baseline is None:
            raise MissingAccountingInputError(
                "absolute activity estimation requires a baseline calibration"
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

    baseline = selected_baseline
    if baseline is None or baseline.value <= 0:
        raise MissingAccountingInputError(
            "activity-based normalized estimation requires a positive estimated baseline calibration"
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
