"""Host-neutral requests and untrusted provider-stage response envelopes."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
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
    TaskReference,
)


class DecompositionRequest(BaseModel):
    """Minimum host-neutral context supplied to provider-driven generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    transformation_intent: str = Field(min_length=1)
    context: dict[str, str] = Field(default_factory=dict)
    request_id: str | None = None
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput | None = None
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class OperationalDecompositionRequest(BaseModel):
    """Provider request for the first stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: DecompositionRequest


class RetainRemoveClassificationRequest(BaseModel):
    """Provider request containing the validated first-stage result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: DecompositionRequest
    operational_decomposition: OperationalDecomposition


class AddedWorkClassificationRequest(BaseModel):
    """Provider request containing validated prior stage results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: DecompositionRequest
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
    "DecompositionRequest",
    "OperationalDecompositionRequest",
    "ProviderStageResponse",
    "RetainRemoveClassificationRequest",
]
