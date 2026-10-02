"""Canonical accounting result contracts."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict

from task_decomposition.contracts.effort import EffortQuantity, RatioBasis
from task_decomposition.contracts.provenance import ProvenanceRef


class AccountingMode(str, Enum):
    NORMALIZED = "normalized"
    ABSOLUTE = "absolute"


class EffectClassification(str, Enum):
    GAIN = "gain"
    NEUTRAL = "neutral"
    DEGRADATION = "degradation"


class CanonicalTransformationImpact(BaseModel):
    """Derived, unclamped workload transformation impact."""

    model_config = ConfigDict(frozen=True)

    accounting_mode: AccountingMode
    baseline_human_effort: EffortQuantity | None
    retained_human_work: EffortQuantity | None
    gross_removed_work: EffortQuantity | None
    governance_work: EffortQuantity | None
    operational_support_work: EffortQuantity | None
    lifecycle_support_work: EffortQuantity | None
    added_human_work: EffortQuantity | None
    net_human_effort: EffortQuantity | None
    w0: Decimal
    w1: Decimal
    gross_removed_work_ratio: Decimal
    added_human_work_ratio: Decimal
    net_remaining_work_ratio: Decimal
    net_substitution_ratio: Decimal
    net_augmentation_multiplier: Decimal
    effect: EffectClassification
    provenance_refs: tuple[ProvenanceRef, ...] = ()


__all__ = [
    "AccountingMode",
    "CanonicalTransformationImpact",
    "EffectClassification",
    "RatioBasis",
]
