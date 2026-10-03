"""Provider-independent contracts for the staged decomposition pipeline."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from task_decomposition.contracts.accounting import CanonicalTransformationImpact
from task_decomposition.contracts.decomposition import TransformationClassification
from task_decomposition.contracts.effort import EffortQuantity, SupportWorkInput
from task_decomposition.contracts.provenance import ProviderProvenance, ProvenanceRef


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
    """Canonical category names for work introduced by the transformation."""

    GOVERNANCE = "GOVERNANCE"
    OPERATIONAL_SUPPORT = "OPERATIONAL_SUPPORT"
    LIFECYCLE_SUPPORT = "LIFECYCLE_SUPPORT"


class AddedWorkItem(BaseModel):
    """One added-human-work row, distinct from baseline RETAIN/REMOVE rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str = Field(min_length=1)
    workload_name: str = Field(min_length=1)
    category: AddedWorkCategory
    description: str | None = None
    amount: SupportWorkInput | None = None
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


class StagedDecompositionResult(BaseModel):
    """Validated staged inputs plus the authoritative Wave 1 accounting result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operational_decomposition: OperationalDecomposition
    retain_remove_classification: RetainRemoveClassification
    added_work_classification: AddedWorkClassification
    accounting: CanonicalTransformationImpact
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    provider_provenance: tuple[ProviderProvenance, ...] = ()


class TransformationDecompositionResult(BaseModel):
    """Transformation facts plus authoritative canonical transformation impact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_decomposition: TaskDecomposition
    retain_remove_classification: RetainRemoveClassification
    added_work_classification: AddedWorkClassification
    accounting: CanonicalTransformationImpact
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    provider_provenance: tuple[ProviderProvenance, ...] = ()


__all__ = [
    "AddedWorkCategory",
    "AddedWorkClassification",
    "AddedWorkItem",
    "BaselineEffortAllocation",
    "ClassifiedSubtask",
    "OperationalDecomposition",
    "OperationalSubtask",
    "RetainRemoveClassification",
    "StagedDecompositionResult",
    "TaskReference",
    "TaskDecomposition",
    "TransformationDecompositionResult",
]
