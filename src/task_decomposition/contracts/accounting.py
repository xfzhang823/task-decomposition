"""Contracts for deterministic transformation-accounting results.

This module defines the public result vocabulary used by the accounting domain:
the accounting mode, the derived effect classification, and the immutable
``CanonicalTransformationImpact`` result.  It owns data shape and semantic
labels only.  It does not calculate W0, W1, ratios, or effects; those formulas
belong to ``task_decomposition.domain.accounting``.

Providers and application orchestration may supply or resolve accounting
inputs, but they must not create authoritative derived metrics outside the
domain accounting module.  The contracts remain provider-neutral and contain
no persistence, workflow, scenario, or execution concerns.
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from task_decomposition.contracts.effort import EffortQuantity, RatioBasis
from task_decomposition.contracts.provenance import ProvenanceRef


class AccountingMode(str, Enum):
    """Representation used for the canonical accounting calculation.

    ``NORMALIZED`` represents the baseline as ``W0 = 1`` and exposes ratios.
    ``ABSOLUTE`` represents effort with explicit units and time bases and also
    exposes the corresponding normalized ratios.
    """

    NORMALIZED = "normalized"
    ABSOLUTE = "absolute"


class EffectClassification(str, Enum):
    """Direction of change derived by comparing post-transformation W1 to W0.

    The accounting domain applies its canonical tolerance when assigning these
    labels.  Values are not clamped: support work can exceed gross removed work
    and produce ``DEGRADATION``.
    """

    GAIN = "gain"
    NEUTRAL = "neutral"
    DEGRADATION = "degradation"


class CanonicalTransformationImpact(BaseModel):
    """Immutable derived impact of a transformation on human effort.

    This model is the output contract of deterministic accounting.  ``w0`` is
    original baseline human effort, while ``w1`` is post-transformation human
    effort: retained work plus resolved AI-related support work.  Gross removed
    work is retained as a separate baseline quantity and is not added to ``w1``.

    Absolute-mode quantity fields are populated with ``EffortQuantity`` values.
    In normalized mode those fields are ``None`` because the result is
    represented by baseline-relative ratios instead.  The ratio fields are
    available in both modes.  Derived values are intentionally unclamped, so
    net substitution may be negative when support work exceeds gross removal.

    Attributes:
        accounting_mode: Whether the result was computed from absolute or
            normalized accounting inputs.
        baseline_human_effort: Original baseline effort in absolute mode;
            ``None`` in normalized mode.
        retained_human_work: Baseline effort retained after transformation in
            absolute mode; ``None`` in normalized mode.
        gross_removed_work: Baseline effort classified as removed before
            support work, in absolute mode; ``None`` in normalized mode.
        ai_interaction_work: Resolved added human effort for AI interaction in
            absolute mode; ``None`` in normalized mode.
        ai_verification_work: Resolved added human effort for AI verification
            in absolute mode; ``None`` in normalized mode.
        added_human_work: Sum of interaction and verification support work in
            absolute mode; ``None`` in normalized mode.
        net_human_effort: Post-transformation human effort in absolute mode;
            ``None`` in normalized mode.
        w0: Original baseline effort, or ``1`` for normalized accounting.
        w1: Post-transformation human effort, using the same representation as
            ``w0``.
        gross_removed_work_ratio: Gross removed work divided by ``w0``.
        added_human_work_ratio: Added support work divided by ``w0``.
        net_remaining_work_ratio: ``w1 / w0``.
        net_substitution_ratio: ``1 - net_remaining_work_ratio``; this is not
            the same as gross removed work ratio when support work is present.
        net_augmentation_multiplier: ``1 / net_remaining_work_ratio`` when
            ``w1`` is positive; ``None`` when ``w1`` is zero because the
            multiplier is undefined.
        effect: Tolerance-aware classification derived from ``w0`` and ``w1``.
        provenance_refs: Portable references supporting the result inputs or
            classifications.
    """

    model_config = ConfigDict(frozen=True)

    accounting_mode: AccountingMode = Field(
        description="Whether values are normalized or use absolute effort units."
    )
    baseline_human_effort: EffortQuantity | None = Field(
        description="Original human effort W0 in absolute mode; None when normalized."
    )
    retained_human_work: EffortQuantity | None = Field(
        description="Baseline effort classified RETAIN; part of W0 in absolute mode."
    )
    gross_removed_work: EffortQuantity | None = Field(
        description="Baseline effort classified REMOVE before support work."
    )
    ai_interaction_work: EffortQuantity | None = Field(
        description="Post-transformation human effort interacting with or operating AI."
    )
    ai_verification_work: EffortQuantity | None = Field(
        description="Post-transformation human effort checking or approving AI output."
    )
    added_human_work: EffortQuantity | None = Field(
        description="Sum of interaction and verification support work."
    )
    net_human_effort: EffortQuantity | None = Field(
        description="Post-transformation absolute human effort W1."
    )
    w0: Decimal = Field(
        description="Original baseline human effort; exactly 1 in normalized mode."
    )
    w1: Decimal = Field(
        description="Post-transformation human effort: retained work plus support work."
    )
    gross_removed_work_ratio: Decimal = Field(
        description="Gross removed baseline work divided by W0; not net substitution."
    )
    added_human_work_ratio: Decimal = Field(
        description="Added human support work divided by W0."
    )
    net_remaining_work_ratio: Decimal = Field(description="W1 divided by W0.")
    net_substitution_ratio: Decimal = Field(
        description="1 minus net_remaining_work_ratio; net reduction after support work."
    )
    net_augmentation_multiplier: Decimal | None = Field(
        description="W0 divided by W1 when W1 is positive; None when undefined."
    )
    effect: EffectClassification = Field(
        description="Tolerance-aware direction of change from W0 to W1."
    )
    provenance_refs: tuple[ProvenanceRef, ...] = Field(
        default=(),
        description="References supporting accounting inputs or classifications.",
    )


__all__ = [
    "AccountingMode",
    "CanonicalTransformationImpact",
    "EffectClassification",
    "RatioBasis",
]
