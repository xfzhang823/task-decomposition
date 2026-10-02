"""Deterministic canonical W0/W1 accounting."""

from collections.abc import Iterable
from decimal import Decimal

from task_decomposition.contracts.accounting import (
    AccountingMode,
    CanonicalTransformationImpact,
    EffectClassification,
)
from task_decomposition.contracts.decomposition import (
    TransformationClassification,
    TransformationRow,
)
from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
)
from task_decomposition.errors import (
    AccountingInvariantError,
    IncompatibleEffortUnitError,
    InvalidDenominatorError,
    RatioBasisError,
    ZeroBaselineError,
)

DEFAULT_TOLERANCE = Decimal("0.000000001")


def _close(left: Decimal, right: Decimal, tolerance: Decimal) -> bool:
    return abs(left - right) <= tolerance


def _require_same_unit(*quantities: EffortQuantity) -> None:
    first = quantities[0]
    if any(
        quantity.unit is not first.unit or quantity.time_basis is not first.time_basis
        for quantity in quantities[1:]
    ):
        raise IncompatibleEffortUnitError(
            "all absolute effort values need one unit/time basis"
        )


def _support_to_normalized(
    support: SupportWorkInput,
    *,
    w0: Decimal,
    gross_removed: Decimal,
    mode: AccountingMode,
) -> Decimal:
    if support.basis is RatioBasis.NORMALIZED_CONTRIBUTION:
        return support.value
    if support.basis is RatioBasis.RATIO_OF_BASELINE_WORK:
        return support.value
    if support.basis is RatioBasis.RATIO_OF_GROSS_REMOVED_WORK:
        return gross_removed / w0 * support.value
    if support.basis is RatioBasis.ABSOLUTE_EFFORT:
        if mode is AccountingMode.NORMALIZED:
            raise RatioBasisError(
                "absolute support effort is not valid in normalized mode"
            )
        return support.value / w0
    raise RatioBasisError(f"unsupported support basis: {support.basis}")


def _support_to_absolute(
    support: SupportWorkInput,
    *,
    w0: Decimal,
    gross_removed: Decimal,
) -> Decimal:
    if support.basis is RatioBasis.ABSOLUTE_EFFORT:
        return support.value
    return (
        _support_to_normalized(
            support, w0=w0, gross_removed=gross_removed, mode=AccountingMode.ABSOLUTE
        )
        * w0
    )


def classify_effect(
    w0: Decimal, w1: Decimal, tolerance: Decimal = DEFAULT_TOLERANCE
) -> EffectClassification:
    """Derive effect from W0/W1; values are never clamped."""
    if w1 < w0 - tolerance:
        return EffectClassification.GAIN
    if w1 > w0 + tolerance:
        return EffectClassification.DEGRADATION
    return EffectClassification.NEUTRAL


def account_normalized(
    accounting: NormalizedAccountingInput,
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> CanonicalTransformationImpact:
    """Account with W0=1.0 and baseline-relative contributions."""
    w0 = Decimal("1")
    retained = accounting.retained_work_ratio
    removed = accounting.gross_removed_work_ratio
    if not _close(retained + removed, w0, tolerance):
        raise AccountingInvariantError(
            "retained and gross-removed normalized work must sum to 1"
        )
    support_values = [
        _support_to_normalized(
            support,
            w0=w0,
            gross_removed=removed,
            mode=AccountingMode.NORMALIZED,
        )
        for support in (
            accounting.support_work.governance,
            accounting.support_work.operational_support,
            accounting.support_work.lifecycle_support,
        )
    ]
    governance, operational, lifecycle = support_values
    added = governance + operational + lifecycle
    w1 = retained + added
    if w1 == 0:
        raise InvalidDenominatorError(
            "net augmentation multiplier is undefined when W1 is zero"
        )
    return CanonicalTransformationImpact(
        accounting_mode=AccountingMode.NORMALIZED,
        baseline_human_effort=None,
        retained_human_work=None,
        gross_removed_work=None,
        governance_work=None,
        operational_support_work=None,
        lifecycle_support_work=None,
        added_human_work=None,
        net_human_effort=None,
        w0=w0,
        w1=w1,
        gross_removed_work_ratio=removed,
        added_human_work_ratio=added,
        net_remaining_work_ratio=w1,
        net_substitution_ratio=1 - w1,
        net_augmentation_multiplier=1 / w1,
        effect=classify_effect(w0, w1, tolerance),
    )


def account_absolute(
    accounting: AbsoluteEffortInput,
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> CanonicalTransformationImpact:
    """Account absolute effort and expose the equivalent normalized ratios."""
    baseline = accounting.baseline_human_effort
    retained_quantity = accounting.retained_human_work
    removed_quantity = accounting.gross_removed_work
    _require_same_unit(baseline, retained_quantity, removed_quantity)
    w0 = baseline.value
    if w0 <= 0:
        raise ZeroBaselineError("baseline W0 must be positive for impact accounting")
    retained = retained_quantity.value
    removed = removed_quantity.value
    if not _close(retained + removed, w0, tolerance):
        raise AccountingInvariantError(
            "retained and gross-removed effort must reconcile to W0"
        )
    supports = (
        accounting.support_work.governance,
        accounting.support_work.operational_support,
        accounting.support_work.lifecycle_support,
    )
    for support in supports:
        if support.basis is RatioBasis.ABSOLUTE_EFFORT:
            if (
                support.unit is not baseline.unit
                or support.time_basis is not baseline.time_basis
            ):
                raise IncompatibleEffortUnitError(
                    "absolute support effort must match W0 unit/time basis"
                )
    governance, operational, lifecycle = (
        _support_to_absolute(support, w0=w0, gross_removed=removed)
        for support in supports
    )
    added = governance + operational + lifecycle
    w1 = retained + added
    if w1 == 0:
        raise InvalidDenominatorError(
            "net augmentation multiplier is undefined when W1 is zero"
        )
    unit = baseline.unit
    period = baseline.time_basis

    def quantity(value: Decimal) -> EffortQuantity:
        return EffortQuantity(value=value, unit=unit, time_basis=period)

    return CanonicalTransformationImpact(
        accounting_mode=AccountingMode.ABSOLUTE,
        baseline_human_effort=baseline,
        retained_human_work=retained_quantity,
        gross_removed_work=removed_quantity,
        governance_work=quantity(governance),
        operational_support_work=quantity(operational),
        lifecycle_support_work=quantity(lifecycle),
        added_human_work=quantity(added),
        net_human_effort=quantity(w1),
        w0=w0,
        w1=w1,
        gross_removed_work_ratio=removed / w0,
        added_human_work_ratio=added / w0,
        net_remaining_work_ratio=w1 / w0,
        net_substitution_ratio=1 - (w1 / w0),
        net_augmentation_multiplier=w0 / w1,
        effect=classify_effect(w0, w1, tolerance),
    )


def aggregate_baseline_rows(
    rows: Iterable[TransformationRow],
) -> tuple[Decimal, Decimal]:
    """Return retained and gross-removed effort from effort-bearing rows."""
    retained = Decimal("0")
    removed = Decimal("0")
    for row in rows:
        if row.effort is None:
            raise AccountingInvariantError(f"row {row.row_id!r} has no effort")
        if row.classification is TransformationClassification.RETAIN:
            retained += row.effort.value
        else:
            removed += row.effort.value
    return retained, removed
