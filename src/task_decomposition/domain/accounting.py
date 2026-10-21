"""Deterministic canonical W0/W1 accounting.

The domain treats original human work and newly introduced support work as
separate quantities.  For compatible absolute inputs, ``W0`` is the original
baseline and must satisfy ``W0 = retained + gross_removed``.  ``W1`` is the
post-transformation human effort and is ``retained + resolved_support``.
"""

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
from task_decomposition.domain.allocation import DEFAULT_TOLERANCE
from task_decomposition.errors import (
    AccountingInvariantError,
    IncompatibleEffortUnitError,
    InvalidDenominatorError,
    RatioBasisError,
    ZeroBaselineError,
)


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
    """Derive effect from original and post-transformation work totals.

    ``w0`` is original human effort and ``w1`` is remaining human effort after
    transformation.  Values are never clamped: support work can exceed gross
    removal, producing a degradation and a negative net-substitution ratio.
    The tolerance defines the neutral band around equality.
    """
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
    """Compute canonical accounting from baseline-relative contributions.

    This mode fixes ``W0 = 1``.  The retained and gross-removed ratios are a
    baseline partition and must sum to one within ``tolerance``.  Support
    contributions are additional post-transformation work, converted from
    their declared ratio bases as needed.  The resulting relationship is
    ``W1 = retained + resolved_support``; gross removal is not added to W1.

    The application support-work resolver normally supplies the two support
    values before this function is called.  Absolute support effort is not a
    valid representation in normalized mode.
    """
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
            accounting.support_work.ai_interaction,
            accounting.support_work.ai_verification,
        )
    ]
    ai_interaction, ai_verification = support_values
    added = ai_interaction + ai_verification
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
        ai_interaction_work=None,
        ai_verification_work=None,
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
    """Compute canonical accounting from absolute effort quantities.

    All absolute baseline quantities must share one unit and time basis.  The
    baseline partition is validated as ``W0 = retained_human_work +
    gross_removed_work`` within ``tolerance``.  Support work is additional
    post-transformation effort, so the post-transformation relationship is
    ``W1 = retained_human_work + resolved_support_work``.  Gross removal is
    reported separately and is not itself part of W1.

    Ratio-based support inputs are converted to absolute effort using their
    explicit bases; absolute support inputs must match the baseline unit and
    time basis.  The result also exposes baseline-relative ratios.
    """
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
        accounting.support_work.ai_interaction,
        accounting.support_work.ai_verification,
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
    ai_interaction, ai_verification = (
        _support_to_absolute(support, w0=w0, gross_removed=removed)
        for support in supports
    )
    added = ai_interaction + ai_verification
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
        ai_interaction_work=quantity(ai_interaction),
        ai_verification_work=quantity(ai_verification),
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
    """Aggregate validated baseline rows into retained and gross-removed work.

    The returned values are both portions of the original baseline.  Added
    support work is not represented by this helper and must not be included in
    either total.
    """
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
