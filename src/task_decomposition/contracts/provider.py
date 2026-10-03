"""Host-neutral requests and untrusted provider-stage response envelopes."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    NormalizedAccountingInput,
)
from task_decomposition.contracts.provenance import (
    ProviderProvenance,
    ProviderStage,
    ProvenanceRef,
)
from task_decomposition.contracts.stages import (
    OperationalDecomposition,
    RetainRemoveClassification,
    TaskDecomposition,
    TaskReference,
)


class TaskDecompositionRequest(BaseModel):
    """Canonical task-only request; it has no transformation intent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    task_context: dict[str, str] = Field(default_factory=dict)
    baseline_effort: "EffortQuantity | None" = None
    effort_weights: dict[str, Decimal] | None = None
    request_id: str | None = None
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class TransformationDecompositionRequest(BaseModel):
    """Canonical transformation request over an existing task decomposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_decomposition: TaskDecomposition
    transformation_context: dict[str, str] = Field(default_factory=dict)
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput
    request_id: str | None = None
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class OperationalDecompositionRequest(BaseModel):
    """Provider request for the first stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TaskDecompositionRequest


class RetainRemoveClassificationRequest(BaseModel):
    """Provider request containing the validated first-stage result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TransformationDecompositionRequest
    operational_decomposition: OperationalDecomposition


class AddedWorkClassificationRequest(BaseModel):
    """Provider request containing validated prior stage results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TransformationDecompositionRequest
    operational_decomposition: OperationalDecomposition
    retain_remove_classification: RetainRemoveClassification


class ProviderStageResponse(BaseModel):
    """Untrusted provider output; payload is validated by the application."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: ProviderStage
    payload: Any
    provenance: ProviderProvenance


__all__ = [
    "AddedWorkClassificationRequest",
    "OperationalDecompositionRequest",
    "ProviderStageResponse",
    "RetainRemoveClassificationRequest",
    "TaskDecompositionRequest",
    "TransformationDecompositionRequest",
]
