from decimal import Decimal

import pytest
from pydantic import ValidationError

from task_decomposition import (
    AbsoluteEffortInput,
    AccountingInvariantError,
    EffortQuantity,
    EffortUnit,
    EffectClassification,
    IncompatibleEffortUnitError,
    InvalidDenominatorError,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
    TimeBasis,
    account_absolute,
    account_normalized,
    classify_effect,
    aggregate_baseline_rows,
    allocate_effort,
    run_staged_pipeline,
)
from task_decomposition.contracts.decomposition import (
    TransformationClassification,
    TransformationRow,
)
from task_decomposition.contracts.stages import AddedWorkCategory, AddedWorkItem
from task_decomposition.errors import ZeroBaselineError


UNIT = EffortUnit.EFFORT
PER_OPERATION = TimeBasis.PER_OPERATION


def effort(value: Decimal | int | str) -> EffortQuantity:
    return EffortQuantity(value=value, unit=UNIT, time_basis=PER_OPERATION)


def support(value: Decimal | int | str, basis: RatioBasis) -> SupportWorkInput:
    kwargs = {"value": value, "basis": basis}
    if basis is RatioBasis.ABSOLUTE_EFFORT:
        kwargs.update(unit=UNIT, time_basis=PER_OPERATION)
    return SupportWorkInput(**kwargs)


def absolute_amount(value: Decimal | int | str) -> SupportWorkInput:
    return support(value, RatioBasis.ABSOLUTE_EFFORT)


def support_inputs(
    values: tuple[Decimal | int | str, Decimal | int | str, Decimal | int | str],
    basis: RatioBasis,
) -> SupportWorkInputs:
    return SupportWorkInputs(
        governance=support(values[0], basis),
        operational_support=support(values[1], basis),
        lifecycle_support=support(values[2], basis),
    )


def absolute_input(
    baseline: Decimal | int | str,
    retained: Decimal | int | str,
    removed: Decimal | int | str,
    added: tuple[Decimal | int | str, Decimal | int | str, Decimal | int | str],
) -> AbsoluteEffortInput:
    return AbsoluteEffortInput(
        baseline_human_effort=effort(baseline),
        retained_human_work=effort(retained),
        gross_removed_work=effort(removed),
        support_work=support_inputs(added, RatioBasis.ABSOLUTE_EFFORT),
    )


def normalized_input(
    retained: Decimal | int | str,
    removed: Decimal | int | str,
    added: tuple[Decimal | int | str, Decimal | int | str, Decimal | int | str],
) -> NormalizedAccountingInput:
    return NormalizedAccountingInput(
        retained_work_ratio=retained,
        gross_removed_work_ratio=removed,
        support_work=support_inputs(added, RatioBasis.NORMALIZED_CONTRIBUTION),
    )


@pytest.mark.parametrize(
    ("retained", "removed", "added", "w1", "substitution", "multiplier", "effect"),
    [
        ("100", "0", "0", "100", "0", "1", EffectClassification.NEUTRAL),
        (
            "60",
            "40",
            "0",
            "60",
            "0.4",
            "1.666666666666666666666666667",
            EffectClassification.GAIN,
        ),
        (
            "60",
            "40",
            "10",
            "70",
            "0.3",
            "1.428571428571428571428571429",
            EffectClassification.GAIN,
        ),
        ("60", "40", "40", "100", "0", "1", EffectClassification.NEUTRAL),
        (
            "60",
            "40",
            "60",
            "120",
            "-0.2",
            "0.8333333333333333333333333333",
            EffectClassification.DEGRADATION,
        ),
    ],
)
def test_known_answer_matrix(
    retained, removed, added, w1, substitution, multiplier, effect
):
    result = account_absolute(
        absolute_input("100", retained, removed, (added, "0", "0"))
    )

    assert result.w0 == Decimal("100")
    assert result.w1 == Decimal(w1)
    assert result.gross_removed_work_ratio == Decimal(removed) / Decimal("100")
    assert result.added_human_work_ratio == Decimal(added) / Decimal("100")
    assert result.net_remaining_work_ratio == Decimal(w1) / Decimal("100")
    assert result.net_substitution_ratio == Decimal(substitution)
    assert result.net_augmentation_multiplier == Decimal(multiplier)
    assert result.effect is effect


def test_full_removal_requires_positive_net_work_for_augmentation():
    with pytest.raises(InvalidDenominatorError):
        account_absolute(absolute_input("100", "0", "100", ("0", "0", "0")))

    result = account_absolute(absolute_input("100", "0", "100", ("20", "0", "0")))
    assert result.w1 == Decimal("20")
    assert result.net_remaining_work_ratio == Decimal("0.2")
    assert result.net_substitution_ratio == Decimal("0.8")
    assert result.effect is EffectClassification.GAIN


def test_very_small_positive_w1_remains_finite_and_unclamped():
    result = account_normalized(
        normalized_input("0.000000001", "0.999999999", ("0", "0", "0"))
    )

    assert result.w1 == Decimal("0.000000001")
    assert result.net_substitution_ratio == Decimal("0.999999999")
    assert result.net_augmentation_multiplier == Decimal("1000000000")


@pytest.mark.parametrize("scale", ["1", "10", "100", "10000"])
def test_absolute_and_normalized_inputs_are_scale_equivalent(scale):
    scale = Decimal(scale)
    absolute = account_absolute(
        absolute_input(
            scale,
            scale * Decimal("0.75"),
            scale * Decimal("0.25"),
            (
                scale * Decimal("0.04"),
                scale * Decimal("0.03"),
                scale * Decimal("0.03"),
            ),
        )
    )
    normalized = account_normalized(
        normalized_input("0.75", "0.25", ("0.04", "0.03", "0.03"))
    )

    for field in (
        "gross_removed_work_ratio",
        "added_human_work_ratio",
        "net_remaining_work_ratio",
        "net_substitution_ratio",
        "net_augmentation_multiplier",
    ):
        assert getattr(absolute, field) == getattr(normalized, field)
    assert absolute.effect is normalized.effect


@pytest.mark.parametrize(
    ("retained", "removed", "added"),
    [
        ("0.25", "0.75", "0.125"),
        ("0.333", "0.667", "0.111"),
        ("0.875", "0.125", "0.0625"),
    ],
)
def test_algebraic_invariants(retained, removed, added):
    retained = Decimal(retained)
    removed = Decimal(removed)
    added = Decimal(added)
    result = account_normalized(normalized_input(retained, removed, (added, "0", "0")))

    assert result.w0 == retained + removed
    assert result.w1 == retained + added
    assert result.gross_removed_work_ratio == removed
    assert result.net_remaining_work_ratio == result.w1 / result.w0
    assert result.net_substitution_ratio == 1 - result.net_remaining_work_ratio
    assert result.net_augmentation_multiplier == 1 / result.net_remaining_work_ratio


def test_added_work_zero_equals_gross_removal_and_increasing_support_is_monotonic():
    baseline = account_normalized(normalized_input("0.6", "0.4", ("0", "0", "0")))
    increased = account_normalized(
        normalized_input("0.6", "0.4", ("0.1", "0.2", "0.3"))
    )

    assert baseline.net_substitution_ratio == baseline.gross_removed_work_ratio
    assert increased.w1 >= baseline.w1
    assert increased.net_remaining_work_ratio >= baseline.net_remaining_work_ratio
    assert increased.net_substitution_ratio <= baseline.net_substitution_ratio
    assert increased.net_augmentation_multiplier <= baseline.net_augmentation_multiplier


@pytest.mark.parametrize(
    ("w1", "expected"),
    [
        ("99.999999999", EffectClassification.NEUTRAL),
        ("99.999999998", EffectClassification.GAIN),
        ("100.000000001", EffectClassification.NEUTRAL),
        ("100.000000002", EffectClassification.DEGRADATION),
    ],
)
def test_effect_tolerance_boundaries(w1, expected):
    assert classify_effect(Decimal("100"), Decimal(w1)) is expected


def test_allocation_to_accounting_consistency():
    allocations = allocate_effort(effort(100), {"a": "0.50", "b": "0.30", "c": "0.20"})
    rows = [
        TransformationRow(
            row_id="a",
            classification=TransformationClassification.RETAIN,
            effort=allocations["a"],
        ),
        TransformationRow(
            row_id="b",
            classification=TransformationClassification.REMOVE,
            effort=allocations["b"],
        ),
        TransformationRow(
            row_id="c",
            classification=TransformationClassification.RETAIN,
            effort=allocations["c"],
        ),
    ]
    retained, removed = aggregate_baseline_rows(rows)
    result = account_absolute(absolute_input(100, retained, removed, (0, 0, 0)))

    assert retained == Decimal("70")
    assert removed == Decimal("30")
    assert result.w0 == Decimal("100")
    assert result.w1 == Decimal("70")


def test_allocation_accounting_handles_all_retained_and_all_removed():
    allocations = allocate_effort(effort(100), {"a": "0.50", "b": "0.30", "c": "0.20"})
    all_retained = [
        TransformationRow(
            row_id=row_id,
            classification=TransformationClassification.RETAIN,
            effort=value,
        )
        for row_id, value in allocations.items()
    ]
    all_removed = [
        TransformationRow(
            row_id=row_id,
            classification=TransformationClassification.REMOVE,
            effort=value,
        )
        for row_id, value in allocations.items()
    ]
    retained, removed = aggregate_baseline_rows(all_retained)
    assert (retained, removed) == (Decimal("100"), Decimal("0"))
    retained, removed = aggregate_baseline_rows(all_removed)
    assert (retained, removed) == (Decimal("0"), Decimal("100"))


@pytest.mark.parametrize(
    ("removed_ids", "expected"),
    [
        (set(), (Decimal("100"), Decimal("0"))),
        ({"b"}, (Decimal("70"), Decimal("30"))),
        ({"b", "c"}, (Decimal("50"), Decimal("50"))),
        ({"a", "b", "c"}, (Decimal("0"), Decimal("100"))),
    ],
)
def test_allocation_handoff_preserves_retain_remove_totals(removed_ids, expected):
    allocations = allocate_effort(effort(100), {"a": "0.50", "b": "0.30", "c": "0.20"})
    rows = [
        TransformationRow(
            row_id=row_id,
            classification=(
                TransformationClassification.REMOVE
                if row_id in removed_ids
                else TransformationClassification.RETAIN
            ),
            effort=value,
        )
        for row_id, value in allocations.items()
    ]
    assert aggregate_baseline_rows(rows) == expected


def test_staged_pipeline_matches_direct_accounting_for_absolute_and_normalized_inputs():
    from test_staged_pipeline import (
        make_added,
        make_absolute_accounting,
        make_classification,
        make_normalized_accounting,
        make_operational,
    )

    absolute_staged = run_staged_pipeline(
        make_operational(),
        make_classification(),
        make_added(),
        make_absolute_accounting(),
    ).accounting
    absolute_direct = account_absolute(absolute_input("100", "60", "40", (4, 8, 2)))
    normalized_staged = run_staged_pipeline(
        make_operational(),
        make_classification(with_effort=False),
        make_added(normalized=True),
        make_normalized_accounting(),
    ).accounting
    normalized_direct = account_normalized(
        normalized_input("0.60", "0.40", ("0.04", "0.08", "0.02"))
    )

    for staged, direct in (
        (absolute_staged, absolute_direct),
        (normalized_staged, normalized_direct),
    ):
        assert staged.w0 == direct.w0
        assert staged.w1 == direct.w1
        assert staged.net_substitution_ratio == direct.net_substitution_ratio
        assert staged.net_augmentation_multiplier == direct.net_augmentation_multiplier
        assert staged.effect is direct.effect


def test_multiple_added_work_items_aggregate_by_category_without_double_counting():
    from test_staged_pipeline import (
        make_added,
        make_absolute_accounting,
        make_classification,
        make_operational,
    )

    added = make_added()
    rows = added.added_work_rows
    added = added.model_copy(
        update={
            "added_work_rows": (
                rows[0],
                AddedWorkItem(
                    work_id="work-gov-2",
                    workload_name="Review additional samples",
                    category=AddedWorkCategory.GOVERNANCE,
                    amount=absolute_amount(1),
                    sequence_index=2,
                ),
                rows[1].model_copy(update={"sequence_index": 3}),
                rows[2].model_copy(update={"sequence_index": 4}),
            )
        }
    )
    result = run_staged_pipeline(
        make_operational(), make_classification(), added, make_absolute_accounting()
    ).accounting

    assert result.governance_work.value == Decimal("5")
    assert result.added_human_work.value == Decimal("15")
    assert result.w1 == Decimal("75")


def test_invalid_finite_and_accounting_inputs_are_rejected():
    with pytest.raises(ValidationError):
        EffortQuantity(value=-1, unit=UNIT, time_basis=PER_OPERATION)
    with pytest.raises(ValidationError):
        NormalizedAccountingInput(
            retained_work_ratio=-1,
            gross_removed_work_ratio=2,
            support_work=support_inputs((0, 0, 0), RatioBasis.NORMALIZED_CONTRIBUTION),
        )
    with pytest.raises(ValidationError):
        EffortQuantity(value="NaN", unit=UNIT, time_basis=PER_OPERATION)
    with pytest.raises(ValidationError):
        EffortQuantity(value="Infinity", unit=UNIT, time_basis=PER_OPERATION)
    with pytest.raises(ValidationError, match="finite"):
        SupportWorkInput(value="NaN", basis=RatioBasis.NORMALIZED_CONTRIBUTION)
    with pytest.raises(ZeroBaselineError):
        account_absolute(absolute_input(0, 0, 0, (0, 0, 0)))
    with pytest.raises(AccountingInvariantError):
        account_normalized(normalized_input("0.8", "0.3", (0, 0, 0)))
    with pytest.raises(IncompatibleEffortUnitError):
        account_absolute(
            absolute_input("100", "60", "40", (4, 8, 2)).model_copy(
                update={
                    "gross_removed_work": EffortQuantity(
                        value=40, unit=EffortUnit.HOURS, time_basis=PER_OPERATION
                    )
                }
            )
        )
