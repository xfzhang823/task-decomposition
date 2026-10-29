from decimal import Decimal

import pytest
from test_staged_pipeline import (
    PER_OPERATION,
    TASK,
    UNIT,
    make_absolute_accounting,
    make_operational,
)

from task_decomposition import (
    ActivityEffortEstimate,
    ActivityEffortEstimation,
    EffortQuantity,
    EffortUnit,
    HumanAgentActivity,
    HumanAgentActivityCategory,
    HumanAgentActivityModel,
    NormalizedAccountingInput,
    RatioBasis,
    validate_activity_effort_estimation,
)
from task_decomposition.application.activity_effort_estimation import (
    resolve_activity_support_work,
)
from task_decomposition.errors import (
    CardinalityError,
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
    StageValidationError,
)


def quantity(value, *, unit=UNIT, time_basis=PER_OPERATION):
    return EffortQuantity(value=value, unit=unit, time_basis=time_basis)


def estimate(activity_id, occurrences, effort, *, expected=None, unit=UNIT):
    expected = (
        Decimal(str(occurrences)) * Decimal(str(effort))
        if expected is None
        else expected
    )
    return ActivityEffortEstimate(
        activity_id=activity_id,
        expected_occurrences_per_parent_output=occurrences,
        active_effort_per_occurrence=quantity(effort, unit=unit),
        expected_effort_per_parent_output=quantity(expected, unit=unit),
        rationale="Deterministic test estimate.",
    )


def activities(*items):
    return HumanAgentActivityModel(task=TASK, activities=tuple(items))


def activity(activity_id, category, *agentic_ids):
    return HumanAgentActivity(
        activity_id=activity_id,
        activity_name=activity_id,
        description="A human activity for the test model.",
        category=category,
        agentic_task_ids=agentic_ids or ("AGT001",),
        trigger="The agent produces an output.",
        expected_action="Review or act on the output.",
    )


def estimation(*estimates):
    return ActivityEffortEstimation(
        task=TASK,
        activity_effort_estimates=tuple(estimates),
    )


def test_expected_occurrences_are_multiplied_once_per_parent_output():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_INTERACTION))
    value = estimation(estimate("HAA001", "0.2", 5, expected=1))

    validated = validate_activity_effort_estimation(make_operational(), model, value)
    support = resolve_activity_support_work(
        validated, model, make_absolute_accounting()
    )

    assert support.ai_interaction.value == Decimal(1)
    assert support.ai_verification.value == Decimal(0)


def test_repeated_activity_is_not_multiplied_by_external_volume():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_VERIFICATION))
    value = estimation(estimate("HAA001", 3, 2, expected=6))

    support = resolve_activity_support_work(value, model, make_absolute_accounting())

    assert support.ai_verification.value == Decimal(6)


def test_explicit_baseline_calibration_precedes_provider_estimate_and_converts_units():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_VERIFICATION))
    value = ActivityEffortEstimation(
        task=TASK,
        activity_effort_estimates=(estimate("HAA001", 1, 1, unit=EffortUnit.HOURS),),
    )
    accounting = NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.5"),
        gross_removed_work_ratio=Decimal("0.5"),
    )

    support = resolve_activity_support_work(
        value,
        model,
        accounting,
        baseline_effort=quantity(30, unit=EffortUnit.MINUTES),
    )

    assert support.ai_verification.value == Decimal(2)


def test_multiple_and_shared_activities_are_summed_once():
    model = activities(
        activity("HAA001", HumanAgentActivityCategory.AI_INTERACTION),
        activity(
            "HAA002", HumanAgentActivityCategory.AI_VERIFICATION, "AGT001", "AGT002"
        ),
        activity("HAA003", HumanAgentActivityCategory.AI_INTERACTION, "AGT002"),
    )
    value = estimation(
        estimate("HAA001", 1, 2),
        estimate("HAA002", 1, 3),
        estimate("HAA003", "0.1", 5),
    )

    support = resolve_activity_support_work(value, model, make_absolute_accounting())

    assert support.ai_interaction.value == Decimal("2.5")
    assert support.ai_verification.value == Decimal(3)


def test_exception_trigger_uses_canonical_interaction_category():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_INTERACTION))
    value = estimation(estimate("HAA001", 1, 4))

    support = resolve_activity_support_work(value, model, make_absolute_accounting())

    assert model.activities[0].category is HumanAgentActivityCategory.AI_INTERACTION
    assert support.ai_interaction.value == Decimal(4)


def test_expected_effort_is_optional_and_canonicalized_by_validation():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_VERIFICATION))
    value = ActivityEffortEstimation(
        task=TASK,
        activity_effort_estimates=(
            ActivityEffortEstimate(
                activity_id="HAA001",
                expected_occurrences_per_parent_output=Decimal("0.25"),
                active_effort_per_occurrence=quantity(8),
                rationale="The test activity is conditional.",
            ),
        ),
    )

    validated = validate_activity_effort_estimation(make_operational(), model, value)

    assert validated.activity_effort_estimates[
        0
    ].expected_effort_per_parent_output.value == Decimal("2.00")


def test_zero_activities_produce_zero_normalized_support_without_calibration():
    model = activities()
    value = ActivityEffortEstimation(task=TASK)
    accounting = NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.6"), gross_removed_work_ratio=Decimal("0.4")
    )

    support = resolve_activity_support_work(
        value, model, accounting, baseline_effort=quantity(100)
    )

    assert support.ai_interaction.value == Decimal(0)
    assert support.ai_verification.value == Decimal(0)


def test_missing_and_duplicate_estimates_are_rejected():
    model = activities(
        activity("HAA001", HumanAgentActivityCategory.AI_INTERACTION),
        activity("HAA002", HumanAgentActivityCategory.AI_VERIFICATION),
    )
    missing = estimation(estimate("HAA001", 1, 1))
    duplicate = estimation(estimate("HAA001", 1, 1), estimate("HAA001", 1, 1))

    with pytest.raises(CardinalityError, match="missing activity effort"):
        validate_activity_effort_estimation(make_operational(), model, missing)
    with pytest.raises(CardinalityError, match="duplicate"):
        validate_activity_effort_estimation(
            make_operational(),
            activities(activity("HAA001", HumanAgentActivityCategory.AI_INTERACTION)),
            duplicate,
        )


def test_product_and_units_are_validated_deterministically():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_INTERACTION))
    wrong_product = estimation(estimate("HAA001", 2, 3, expected=5))
    mismatched = estimation(estimate("HAA001", 1, 3)).model_copy(
        update={
            "activity_effort_estimates": (
                estimate("HAA001", 1, 3).model_copy(
                    update={
                        "expected_effort_per_parent_output": quantity(
                            3, unit=EffortUnit.HOURS
                        )
                    }
                ),
            )
        }
    )
    mismatched = mismatched.model_copy(
        update={
            "activity_effort_estimates": (
                mismatched.activity_effort_estimates[0].model_copy(
                    update={
                        "expected_effort_per_parent_output": quantity(
                            3, unit=EffortUnit.HOURS
                        ),
                        "active_effort_per_occurrence": quantity(3),
                    }
                ),
            )
        }
    )

    with pytest.raises(StageValidationError, match="does not equal"):
        validate_activity_effort_estimation(make_operational(), model, wrong_product)
    with pytest.raises(StageValidationError):
        validate_activity_effort_estimation(make_operational(), model, mismatched)


def test_supplied_absolute_calibration_is_used_without_normalized_conversion():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_VERIFICATION))
    value = estimation(estimate("HAA001", 1, 7))
    accounting = make_absolute_accounting()

    support = resolve_activity_support_work(value, model, accounting)

    assert support.ai_verification.basis is RatioBasis.ABSOLUTE_EFFORT
    assert support.ai_verification.value == Decimal(7)


def test_normalized_calibration_is_explicit_and_positive():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_VERIFICATION))
    value = estimation(estimate("HAA001", 1, 7))
    accounting = NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.6"), gross_removed_work_ratio=Decimal("0.4")
    )

    support = resolve_activity_support_work(
        value, model, accounting, baseline_effort=quantity(100)
    )

    assert support.ai_verification.basis is RatioBasis.NORMALIZED_CONTRIBUTION
    assert support.ai_verification.value == Decimal("0.07")

    with pytest.raises(MissingAccountingInputError):
        resolve_activity_support_work(value, model, accounting)


def test_absolute_unit_boundary_is_rejected():
    model = activities(activity("HAA001", HumanAgentActivityCategory.AI_VERIFICATION))
    value = estimation(estimate("HAA001", 1, 7, unit=UNIT))
    baseline = make_absolute_accounting().model_copy(
        update={
            "baseline_human_effort": quantity(
                100, unit=EffortUnit.HOURS, time_basis=PER_OPERATION
            )
        }
    )

    with pytest.raises(IncompatibleEffortUnitError):
        resolve_activity_support_work(value, model, baseline)
