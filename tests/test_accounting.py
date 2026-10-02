from decimal import Decimal

import pytest
from pydantic import ValidationError

from task_decomposition import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
    TimeBasis,
    account_absolute,
    account_normalized,
)
from task_decomposition.contracts.accounting import EffectClassification
from task_decomposition.errors import (
    AccountingInvariantError,
    IncompatibleEffortUnitError,
    InvalidDenominatorError,
    RatioBasisError,
    ZeroBaselineError,
)


UNIT = EffortUnit.EFFORT
PER_OPERATION = TimeBasis.PER_OPERATION


def support(value: int | float | str, basis: RatioBasis, *, absolute: bool = False):
    kwargs = {"value": value, "basis": basis}
    if absolute:
        kwargs.update(unit=UNIT, time_basis=PER_OPERATION)
    return SupportWorkInput(**kwargs)


def supports(
    governance, operational, lifecycle, basis=RatioBasis.NORMALIZED_CONTRIBUTION
):
    return SupportWorkInputs(
        governance=support(
            governance, basis, absolute=basis is RatioBasis.ABSOLUTE_EFFORT
        ),
        operational_support=support(
            operational, basis, absolute=basis is RatioBasis.ABSOLUTE_EFFORT
        ),
        lifecycle_support=support(
            lifecycle, basis, absolute=basis is RatioBasis.ABSOLUTE_EFFORT
        ),
    )


def absolute_input(
    w0=100,
    retained=60,
    removed=40,
    support_values=(4, 8, 2),
    basis=RatioBasis.ABSOLUTE_EFFORT,
):
    return AbsoluteEffortInput(
        baseline_human_effort=EffortQuantity(
            value=w0, unit=UNIT, time_basis=PER_OPERATION
        ),
        retained_human_work=EffortQuantity(
            value=retained, unit=UNIT, time_basis=PER_OPERATION
        ),
        gross_removed_work=EffortQuantity(
            value=removed, unit=UNIT, time_basis=PER_OPERATION
        ),
        support_work=supports(*support_values, basis=basis),
    )


def normalized_input(
    retained=Decimal("0.60"),
    removed=Decimal("0.40"),
    values=("0.04", "0.08", "0.02"),
    basis=RatioBasis.NORMALIZED_CONTRIBUTION,
):
    return NormalizedAccountingInput(
        retained_work_ratio=retained,
        gross_removed_work_ratio=removed,
        support_work=supports(*values, basis=basis),
    )


def test_reference_absolute_case_has_distinct_gross_and_net_metrics():
    result = account_absolute(absolute_input())

    assert result.w0 == Decimal("100")
    assert result.w1 == Decimal("74")
    assert result.gross_removed_work_ratio == Decimal("0.4")
    assert result.added_human_work_ratio == Decimal("0.14")
    assert result.net_remaining_work_ratio == Decimal("0.74")
    assert result.net_substitution_ratio == Decimal("0.26")
    assert result.net_augmentation_multiplier == Decimal(100) / Decimal(74)
    assert result.effect is EffectClassification.GAIN
    assert result.gross_removed_work_ratio != result.net_substitution_ratio


def test_normalized_reference_is_semantically_equivalent_to_absolute():
    absolute = account_absolute(absolute_input())
    normalized = account_normalized(normalized_input())

    for field in (
        "gross_removed_work_ratio",
        "added_human_work_ratio",
        "net_remaining_work_ratio",
        "net_substitution_ratio",
        "net_augmentation_multiplier",
    ):
        assert getattr(normalized, field) == getattr(absolute, field)
    assert normalized.effect is absolute.effect


@pytest.mark.parametrize(
    ("retained", "removed", "expected"),
    [
        ("0.60", "0.40", EffectClassification.GAIN),
        ("1.00", "0.00", EffectClassification.NEUTRAL),
        ("1.00", "0.00", EffectClassification.DEGRADATION),
    ],
)
def test_effect_classes(retained, removed, expected):
    if expected is EffectClassification.DEGRADATION:
        result = account_normalized(
            normalized_input(
                retained="1.0", removed="0.0", values=("0.10", "0.10", "0.05")
            )
        )
    else:
        result = account_normalized(
            normalized_input(retained=retained, removed=removed, values=("0", "0", "0"))
        )
    assert result.effect is expected


def test_degradation_is_unclamped():
    result = account_absolute(
        absolute_input(w0=100, retained=100, removed=0, support_values=(10, 10, 5))
    )
    assert result.w1 == Decimal("125")
    assert result.net_remaining_work_ratio == Decimal("1.25")
    assert result.net_substitution_ratio == Decimal("-0.25")
    assert result.net_augmentation_multiplier == Decimal("0.8")
    assert result.effect is EffectClassification.DEGRADATION


def test_zero_removed_and_zero_added_are_valid_when_w1_is_positive():
    result = account_normalized(
        normalized_input(retained="1", removed="0", values=("0", "0", "0"))
    )
    assert result.gross_removed_work_ratio == 0
    assert result.added_human_work_ratio == 0
    assert result.net_substitution_ratio == 0


def test_all_baseline_work_can_be_gross_removed():
    result = account_normalized(
        normalized_input(retained="0", removed="1", values=("0.1", "0", "0"))
    )
    assert result.gross_removed_work_ratio == 1
    assert result.w1 == Decimal("0.1")
    assert result.net_substitution_ratio == Decimal("0.9")


def test_removed_work_ratio_support_is_converted_once():
    result = account_normalized(
        normalized_input(
            values=("0.1", "0.2", "0.05"),
            basis=RatioBasis.RATIO_OF_GROSS_REMOVED_WORK,
        )
    )
    assert result.added_human_work_ratio == Decimal("0.14")
    assert result.w1 == Decimal("0.74")


def test_absolute_support_can_be_supplied_as_ratio_of_baseline():
    result = account_absolute(
        absolute_input(
            support_values=("0.04", "0.08", "0.02"),
            basis=RatioBasis.RATIO_OF_BASELINE_WORK,
        )
    )
    assert result.added_human_work.value == Decimal("14")


def test_invalid_balance_is_rejected():
    with pytest.raises(AccountingInvariantError):
        account_absolute(absolute_input(retained=61, removed=40))
    with pytest.raises(AccountingInvariantError):
        account_normalized(normalized_input(retained="0.61", removed="0.40"))


def test_negative_effort_is_rejected():
    with pytest.raises(ValidationError):
        EffortQuantity(value=-1, unit=UNIT, time_basis=PER_OPERATION)


def test_zero_baseline_and_zero_net_are_explicit_errors():
    with pytest.raises(ZeroBaselineError):
        account_absolute(absolute_input(w0=0, retained=0, removed=0))
    with pytest.raises(InvalidDenominatorError):
        account_normalized(normalized_input(retained=0, removed=1, values=(0, 0, 0)))


def test_ratio_basis_is_required_and_absolute_metadata_is_required():
    with pytest.raises(ValidationError):
        SupportWorkInput(value=0.1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        SupportWorkInput(value=1, basis=RatioBasis.ABSOLUTE_EFFORT)
    with pytest.raises(RatioBasisError):
        account_normalized(
            normalized_input(values=(1, 0, 0), basis=RatioBasis.ABSOLUTE_EFFORT)
        )


def test_absolute_unit_mismatch_is_rejected():
    value = absolute_input()
    mismatched = value.model_copy(
        update={
            "gross_removed_work": EffortQuantity(
                value=40, unit=EffortUnit.HOURS, time_basis=PER_OPERATION
            )
        }
    )
    with pytest.raises(IncompatibleEffortUnitError):
        account_absolute(mismatched)
