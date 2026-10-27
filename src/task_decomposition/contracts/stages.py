"""Provider-independent contracts for the staged decomposition pipeline."""

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from task_decomposition.contracts.accounting import CanonicalTransformationImpact
from task_decomposition.contracts.decomposition import TransformationClassification
from task_decomposition.contracts.effort import (
    EffortQuantity,
    SupportWorkInput,
    SupportWorkInputs,
)
from task_decomposition.contracts.provenance import ProvenanceRef, ProviderProvenance


class TaskReference(BaseModel):
    """Host-neutral task identity; no workflow, scenario, or persistence IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str | None = None
    task_name: str = Field(min_length=1)
    task_description: str | None = None


class OperationalSubtask(BaseModel):
    """One observable human operational activity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence_index: int = Field(ge=1)
    subtask_id: str = Field(min_length=1)
    subtask_name: str = Field(min_length=1)
    description: str | None = None
    relative_effort_weight: Decimal | None = Field(default=None, gt=0)
    effort_rationale: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class OperationalDecomposition(BaseModel):
    """Output of the operational-decomposition stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    operational_subtasks: tuple[OperationalSubtask, ...] = Field(min_length=1)
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class BaselineEffortAllocation(BaseModel):
    """Frozen baseline effort associated with one operational subtask."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subtask_id: str = Field(min_length=1)
    effort: EffortQuantity | None = None
    weight_ratio: Decimal | None = Field(default=None, ge=0)
    allocation_source: Literal["estimated", "host"] = "host"
    provenance_refs: tuple[ProvenanceRef, ...] = ()

    @model_validator(mode="after")
    def validate_allocation_basis(self) -> "BaselineEffortAllocation":
        if self.effort is None and self.weight_ratio is None:
            raise ValueError("baseline allocation requires effort or weight_ratio")
        return self


class TaskDecomposition(BaseModel):
    """Reusable operational decomposition with frozen baseline allocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operational_decomposition: OperationalDecomposition
    baseline_effort_allocations: tuple[BaselineEffortAllocation, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    provider_provenance: tuple[ProviderProvenance, ...] = ()

    @model_validator(mode="after")
    def validate_allocation_identity(self) -> "TaskDecomposition":
        subtask_ids = {
            item.subtask_id
            for item in self.operational_decomposition.operational_subtasks
        }
        allocation_ids = [item.subtask_id for item in self.baseline_effort_allocations]
        if len(allocation_ids) != len(set(allocation_ids)):
            raise ValueError("baseline effort allocation IDs must be unique")
        if set(allocation_ids) - subtask_ids:
            raise ValueError("baseline effort allocation references an unknown subtask")
        if allocation_ids and set(allocation_ids) != subtask_ids:
            raise ValueError(
                "baseline effort allocations must cover every operational subtask"
            )
        return self


class ClassifiedSubtask(BaseModel):
    """One identity-preserving RETAIN/REMOVE classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subtask_id: str = Field(min_length=1)
    subtask_name: str | None = None
    sequence_index: int | None = Field(default=None, ge=1)
    classification: TransformationClassification
    effort: EffortQuantity | None = None
    baseline_effort_ratio: Decimal | None = Field(default=None, ge=0)
    rationale: str | None = None

    @field_validator("classification", mode="before")
    @classmethod
    def accept_wire_case(cls, value):
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("baseline_effort_ratio", mode="before")
    @classmethod
    def decimal_ratio(cls, value):
        return None if value is None else Decimal(str(value))

    @model_validator(mode="after")
    def validate_one_effort_basis(self) -> "ClassifiedSubtask":
        if self.effort is not None and self.baseline_effort_ratio is not None:
            raise ValueError(
                "classification effort must use absolute effort or baseline_effort_ratio, not both"
            )
        return self


class RetainRemoveClassification(BaseModel):
    """Output of the RETAIN/REMOVE classification stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    classified_subtasks: tuple[ClassifiedSubtask, ...] = Field(min_length=1)
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class AddedWorkCategory(str, Enum):
    """Execution-level categories for new human work introduced by AI."""

    AI_INTERACTION = "AI_INTERACTION"
    AI_VERIFICATION = "AI_VERIFICATION"


class EstimateRange(BaseModel):
    """Ordered, finite low/typical/high estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    low: Decimal = Field(ge=0)
    typical: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)

    @field_validator("low", "typical", "high", mode="before")
    @classmethod
    def finite_decimal(cls, value):
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("estimate values must be finite")
        return result

    @model_validator(mode="after")
    def ordered(self) -> "EstimateRange":
        if not self.low <= self.typical <= self.high:
            raise ValueError("estimate range must satisfy low <= typical <= high")
        return self


class ExternalReference(BaseModel):
    """An analogous workflow and optional per-occurrence effort anchor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    activity: str = Field(min_length=1)
    effort_per_occurrence: EffortQuantity | SupportWorkInput | None = None


class AddedWorkEstimate(BaseModel):
    """Reference-class metadata; Python, not the provider, computes effort."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrences_per_parent_execution: EstimateRange
    reference_occurrences_per_parent_execution: EstimateRange | None = None
    relative_effort_per_occurrence: EstimateRange
    reference_subtask_id: str | None = None
    external_reference: ExternalReference | None = None
    rationale: str = Field(min_length=1)
    estimate_basis: Literal["measured", "documented", "assumed"]
    provenance_refs: tuple[ProvenanceRef, ...] = ()

    @model_validator(mode="after")
    def exactly_one_reference(self) -> "AddedWorkEstimate":
        if (self.reference_subtask_id is None) == (self.external_reference is None):
            raise ValueError(
                "estimate requires exactly one reference_subtask_id or external_reference"
            )
        if self.reference_subtask_id is not None and (
            self.reference_occurrences_per_parent_execution is None
        ):
            raise ValueError(
                "baseline references require reference occurrence estimates"
            )
        return self


class AddedWorkItem(BaseModel):
    """One added-human-work row, distinct from baseline RETAIN/REMOVE rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str = Field(min_length=1)
    workload_name: str = Field(min_length=1)
    category: AddedWorkCategory
    source_removed_subtask_ids: tuple[str, ...] = ()
    description: str | None = None
    estimate: AddedWorkEstimate | None = None
    depends_on_subtask_ids: tuple[str, ...] = ()
    sequence_index: int | None = Field(default=None, ge=1)
    provenance_refs: tuple[ProvenanceRef, ...] = ()

    @field_validator("category", mode="before")
    @classmethod
    def accept_wire_case(cls, value):
        return value.upper() if isinstance(value, str) else value


class AddedWorkClassification(BaseModel):
    """Output of the added-work classification stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    added_work_rows: tuple[AddedWorkItem, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class AddedWorkEstimateDetail(BaseModel):
    """Auditable calculation inputs and contribution for one added-work row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str = Field(min_length=1)
    workload_name: str = Field(min_length=1)
    description: str | None = None
    category: AddedWorkCategory
    source_removed_subtask_ids: tuple[str, ...] = ()
    occurrences_per_parent_execution: EstimateRange
    relative_effort_per_occurrence: EstimateRange
    reference_source: Literal["baseline_subtask", "external_reference"]
    reference_subtask_id: str | None = None
    external_reference_activity: str | None = None
    reference_effort: EffortQuantity | SupportWorkInput | None = None
    reference_occurrences_per_parent_execution: EstimateRange | None = None
    reference_effort_per_occurrence: EffortQuantity | SupportWorkInput | None = None
    calculated_added_effort: SupportWorkInput
    estimate_basis: Literal["measured", "documented", "assumed"]
    rationale: str
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class NormalizedWorkEstimate(BaseModel):
    """Auditable 100-unit baseline estimate for one classified subtask."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subtask_id: str = Field(min_length=1)
    subtask_name: str = Field(min_length=1)
    baseline_work_units: Decimal = Field(ge=0)
    retained_work_units: Decimal = Field(ge=0)
    gross_removed_work_units: Decimal = Field(ge=0)
    estimate_source: Literal["relative_effort_weight", "model_classification"]
    assumption: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class SupportWorkMode(str, Enum):
    HOST = "host"
    ESTIMATE = "estimate"
    AUTO = "auto"


class SupportWorkResolution(BaseModel):
    """Diagnostic record for host-versus-estimate support selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: SupportWorkMode
    source_by_category: dict[AddedWorkCategory, Literal["host", "estimate"]]
    host_support_work: SupportWorkInputs | None = None
    estimated_support_work: SupportWorkInputs | None = None
    reconciliation: Literal["not_applicable", "match", "difference"]


class TransformationDecompositionResult(BaseModel):
    """Transformation facts plus authoritative canonical transformation impact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_decomposition: TaskDecomposition
    retain_remove_classification: RetainRemoveClassification
    added_work_classification: AddedWorkClassification
    accounting: CanonicalTransformationImpact
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    provider_provenance: tuple[ProviderProvenance, ...] = ()
    support_work_resolution: SupportWorkResolution | None = None
    added_work_estimate_details: tuple[AddedWorkEstimateDetail, ...] = ()
    normalized_work_estimates: tuple[NormalizedWorkEstimate, ...] = ()
    estimation_assumptions: tuple[str, ...] = ()


__all__ = [
    "AddedWorkCategory",
    "AddedWorkClassification",
    "AddedWorkEstimate",
    "AddedWorkEstimateDetail",
    "AddedWorkItem",
    "BaselineEffortAllocation",
    "ClassifiedSubtask",
    "EstimateRange",
    "ExternalReference",
    "NormalizedWorkEstimate",
    "OperationalDecomposition",
    "OperationalSubtask",
    "RetainRemoveClassification",
    "SupportWorkMode",
    "SupportWorkResolution",
    "TaskDecomposition",
    "TaskReference",
    "TransformationDecompositionResult",
]
