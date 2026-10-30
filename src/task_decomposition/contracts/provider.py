"""Host-neutral contracts at the provider/application boundary.

Requests carry task, transformation, accounting, and stage context without
vendor SDK types or workflow concerns. Provider responses are untrusted,
stage-labelled envelopes: adapters propose semantic facts, while application
validation and the accounting domain remain authoritative for identity,
effort products, unit compatibility, allocation, and W0/W1 results.

The canonical transformation stages are RETAIN/REMOVE classification, agentic
task synthesis, human-agent activity modeling, and activity-effort estimation.
These contracts deliberately exclude execution graphs, capacity, staffing, and
provider-generated accounting metrics.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    NormalizedAccountingInput,
)
from task_decomposition.contracts.provenance import (
    ProvenanceRef,
    ProviderProvenance,
    ProviderStage,
)
from task_decomposition.contracts.stages import (
    AgenticTaskSynthesis,
    HumanAgentActivityModel,
    OperationalDecomposition,
    ParentOutputContract,
    RetainRemoveClassification,
    TaskDecomposition,
    TaskReference,
)


class TaskDecompositionRequest(BaseModel):
    """Request an operational baseline for one host-defined parent task.

    This request describes what the task is and its context. It intentionally
    contains no transformation intent, RETAIN/REMOVE decision, workflow,
    capacity, or authoritative accounting result. The provider proposes
    subtasks; the application validates and allocates their relative effort.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference = Field(
        description="Operational task identity; provider/model selection is separate."
    )
    task_context: dict[str, str] = Field(
        default_factory=dict,
        description="Host-supplied context relevant to the baseline decomposition.",
    )
    parent_output_contract: ParentOutputContract | None = Field(
        default=None, description="Optional completion boundary and scope exclusions."
    )
    baseline_effort: "EffortQuantity | None" = Field(
        default=None,
        description="Optional measured baseline effort; otherwise provider estimates are normalized.",
    )
    request_id: str | None = Field(
        default=None, description="Optional correlation identifier for tracing."
    )
    provenance_refs: tuple[ProvenanceRef, ...] = Field(
        default=(), description="Host references supporting the request."
    )


class TransformationDecompositionRequest(BaseModel):
    """Request transformation analysis over an existing frozen decomposition.

    Providers must classify and describe changes to the supplied baseline;
    they must not regenerate the operational decomposition. ``accounting_input``
    supplies the explicit absolute or normalized basis used later by the
    deterministic accounting domain.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_decomposition: TaskDecomposition = Field(
        description="Frozen baseline to transform; it is not regenerated."
    )
    transformation_context: dict[str, str] = Field(
        default_factory=dict,
        description="Description of the requested transformation and its constraints.",
    )
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput = Field(
        description="Explicit absolute or normalized accounting basis for W0/W1."
    )
    request_id: str | None = Field(
        default=None, description="Optional correlation identifier for tracing."
    )
    provenance_refs: tuple[ProvenanceRef, ...] = Field(
        default=(), description="Host references supporting the transformation request."
    )


class TransformationProposalRequest(BaseModel):
    """Request qualitative transformation proposals without accounting input.

    This request is used by exploratory estimation flows that construct their
    normalized accounting input after classification. It still carries the
    existing frozen task decomposition and transformation context.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_decomposition: TaskDecomposition = Field(
        description="Frozen baseline used for provider-assisted estimation."
    )
    transformation_context: dict[str, str] = Field(
        default_factory=dict,
        description="Description of the requested transformation and constraints.",
    )
    request_id: str | None = Field(
        default=None, description="Optional correlation identifier for tracing."
    )
    provenance_refs: tuple[ProvenanceRef, ...] = Field(
        default=(), description="Host references supporting the proposal request."
    )


class OperationalDecompositionRequest(BaseModel):
    """Input envelope for the provider's operational-decomposition stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TaskDecompositionRequest


class RetainRemoveClassificationRequest(BaseModel):
    """Input for classifying the supplied baseline subtasks as RETAIN or REMOVE.

    ``operational_decomposition`` is the validated, identity-preserving stage
    result. The provider proposes labels only; application validation enforces
    complete coverage and preserves the canonical subtask identities.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TransformationDecompositionRequest | TransformationProposalRequest
    operational_decomposition: OperationalDecomposition


class AgenticTaskSynthesisRequest(BaseModel):
    """Input for grouping REMOVE subtasks into semantic AI responsibilities.

    Each proposed agentic task must reference existing removed subtasks and
    describe its responsibility, inputs, and outputs. This stage defines what
    AI is responsible for; it does not define execution, tools, capacity, or
    human effort.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TransformationDecompositionRequest | TransformationProposalRequest
    operational_decomposition: OperationalDecomposition
    retain_remove_classification: RetainRemoveClassification


class HumanAgentActivityModelingRequest(BaseModel):
    """Input for modeling new human activities around validated AI tasks.

    Activities describe interaction or verification, including exception
    triggers that require either kind of human action, that
    humans may perform because of the proposed AI responsibilities. They are
    semantic records only and do not contain occurrences, durations, effort,
    or accounting contributions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TransformationDecompositionRequest | TransformationProposalRequest
    operational_decomposition: OperationalDecomposition
    retain_remove_classification: RetainRemoveClassification
    agentic_task_synthesis: "AgenticTaskSynthesis"


class ActivityEffortEstimationRequest(BaseModel):
    """Input for estimating effort for the complete human-agent activity model.

    The provider estimates expected occurrences per parent output and active
    human effort per occurrence for each modeled activity, with explicit units,
    rationale, and assumptions. Baseline calibration is supplied by the
    application from caller input or bottom-up decomposition; this stage does
    not generate it. Python derives and validates effort products and converts
    the result into existing support-work inputs; the provider does not
    calculate W0 or W1.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: TransformationDecompositionRequest | TransformationProposalRequest
    operational_decomposition: OperationalDecomposition
    retain_remove_classification: RetainRemoveClassification
    agentic_task_synthesis: "AgenticTaskSynthesis"
    human_agent_activity_modeling: "HumanAgentActivityModel"


class ProviderStageResponse(BaseModel):
    """Envelope for one provider-stage result.

    ``payload`` is intentionally untyped here because each stage has a
    different contract and provider output is untrusted. The application must
    verify the stage, provenance, schema, cross-stage references, and semantic
    invariants before using the payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: ProviderStage
    payload: Any
    provenance: ProviderProvenance


__all__ = [
    "ActivityEffortEstimationRequest",
    "AgenticTaskSynthesisRequest",
    "HumanAgentActivityModelingRequest",
    "OperationalDecompositionRequest",
    "ProviderStageResponse",
    "RetainRemoveClassificationRequest",
    "TaskDecompositionRequest",
    "TransformationDecompositionRequest",
    "TransformationProposalRequest",
]
