"""Provider-independent contracts for the staged decomposition pipeline."""

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from task_decomposition.contracts.accounting import CanonicalTransformationImpact
from task_decomposition.contracts.decomposition import TransformationClassification
from task_decomposition.contracts.effort import (
    EffortQuantity,
)
from task_decomposition.contracts.provenance import ProvenanceRef, ProviderProvenance


class TaskReference(BaseModel):
    """Host-neutral task identity; no workflow, scenario, or persistence IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str | None = None
    task_name: str = Field(min_length=1)
    task_description: str | None = None


class ParentOutputContract(BaseModel):
    """Semantic definition of one completed parent-task output.

    The output unit is the denominator for every baseline subtask estimate.
    Scope exclusions document downstream work that must not be included in
    baseline effort, such as a later approval or settlement process.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_unit: str = Field(min_length=1)
    completion_boundary: str = Field(min_length=1)
    scope_exclusions: tuple[str, ...] = ()
    source: Literal["supplied", "provider_inferred", "application_inferred"] = (
        "provider_inferred"
    )
    provenance_refs: tuple[ProvenanceRef, ...] = ()


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
    parent_output_contract: ParentOutputContract | None = None
    baseline_effort_estimates: tuple["BaselineSubtaskEffortEstimate", ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class BaselineSubtaskEffortEstimate(BaseModel):
    """Bottom-up pre-AI effort estimate for one baseline subtask.

    The estimate is expressed per parent-task output. Its expected effort is
    deterministically defined as expected occurrences multiplied by active
    human effort for one occurrence. It excludes passive waiting, machine
    processing, and downstream work outside the parent boundary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    subtask_id: str = Field(min_length=1)
    expected_occurrences_per_parent_output: Decimal = Field(ge=0)
    active_effort_per_occurrence: EffortQuantity
    expected_effort_per_parent_output: EffortQuantity | None = None
    rationale: str = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    estimate_source: Literal["estimated", "supplied"] = "estimated"
    provenance_refs: tuple[ProvenanceRef, ...] = ()

    @field_validator("expected_occurrences_per_parent_output", mode="before")
    @classmethod
    def finite_occurrences(cls, value):
        """Reject non-finite occurrence expectations before multiplication."""
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("baseline occurrences must be finite")
        return result


class BaselineEffortEstimation(BaseModel):
    """Validated total of bottom-up baseline effort estimates.

    ``total_effort_per_parent_output`` is the sum of all subtask expected
    efforts in one compatible unit and time basis. Relative effort weights are
    derived from these values when the total is positive; this record never
    represents resource capacity or workflow demand.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    estimates: tuple[BaselineSubtaskEffortEstimate, ...]
    total_effort_per_parent_output: EffortQuantity
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
        """Require an allocation to carry absolute effort or a relative ratio."""
        if self.effort is None and self.weight_ratio is None:
            raise ValueError("baseline allocation requires effort or weight_ratio")
        return self


class TaskDecomposition(BaseModel):
    """Reusable operational decomposition with frozen baseline allocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operational_decomposition: OperationalDecomposition
    parent_output_contract: ParentOutputContract | None = None
    baseline_effort_estimation: BaselineEffortEstimation | None = None
    baseline_effort_allocations: tuple[BaselineEffortAllocation, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    provider_provenance: tuple[ProviderProvenance, ...] = ()

    @model_validator(mode="after")
    def validate_allocation_identity(self) -> "TaskDecomposition":
        """Ensure baseline allocations uniquely and completely cover subtasks."""
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
        """Accept provider JSON using either upper- or lower-case labels."""
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("baseline_effort_ratio", mode="before")
    @classmethod
    def decimal_ratio(cls, value):
        """Convert serialized numeric ratios to exact ``Decimal`` values."""
        return None if value is None else Decimal(str(value))

    @model_validator(mode="after")
    def validate_one_effort_basis(self) -> "ClassifiedSubtask":
        """Prevent absolute effort and normalized effort from being mixed."""
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


class AgenticTask(BaseModel):
    """One coherent AI responsibility replacing removed baseline work."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agentic_task_id: str = Field(min_length=1)
    agentic_task_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_subtask_ids: tuple[str, ...] = Field(min_length=1)
    required_inputs: tuple[str, ...] = Field(min_length=1)
    expected_outputs: tuple[str, ...] = Field(min_length=1)


class AgenticTaskSynthesis(BaseModel):
    """Validated output of the optional agentic-task synthesis stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    agentic_tasks: tuple[AgenticTask, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class HumanAgentActivityCategory(str, Enum):
    """Semantic categories for new human activities around agentic work."""

    AI_INTERACTION = "AI_INTERACTION"
    AI_VERIFICATION = "AI_VERIFICATION"


class HumanAgentActivity(BaseModel):
    """One semantic human activity associated with agentic responsibilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    activity_id: str = Field(min_length=1)
    activity_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: HumanAgentActivityCategory
    agentic_task_ids: tuple[str, ...] = Field(min_length=1)
    trigger: str = Field(min_length=1)
    expected_action: str = Field(min_length=1)

    @field_validator("category", mode="before")
    @classmethod
    def accept_wire_case(cls, value):
        """Accept provider JSON using case-insensitive activity categories."""
        return value.upper() if isinstance(value, str) else value


class HumanAgentActivityModel(BaseModel):
    """Validated semantic output of the optional human-activity stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    activities: tuple[HumanAgentActivity, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class ActivityEffortEstimate(BaseModel):
    """Quantify the human effort for one modeled human-agent activity.

    This is an estimate per execution of the parent task's output, such as
    one claim reviewed or one ticket resolved. It is not a duration for the
    agent, a staffing requirement, or a workload-volume estimate.

    The provider supplies the two inputs and a rationale:

    ``expected_occurrences_per_parent_output``
        The expected number of times the activity occurs for one parent
        output. A conditional activity uses its frequency across all parent
        outputs here, so its probability is applied once.

    ``active_effort_per_occurrence``
        Active human work for one execution of the activity. Passive waiting,
        autonomous agent execution, and machine processing are excluded.

    ``expected_effort_per_parent_output`` must equal occurrences multiplied by
    effort per occurrence. Application validation checks that relationship and
    uses the deterministic product for accounting conversion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    activity_id: str = Field(min_length=1)
    expected_occurrences_per_parent_output: Decimal = Field(ge=0)
    active_effort_per_occurrence: EffortQuantity
    expected_effort_per_parent_output: EffortQuantity | None = None
    rationale: str = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    provenance_refs: tuple[ProvenanceRef, ...] = ()

    @field_validator("expected_occurrences_per_parent_output", mode="before")
    @classmethod
    def finite_occurrences(cls, value):
        """Reject non-finite occurrence values before effort arithmetic."""
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("activity occurrences must be finite")
        return result


class ActivityEffortEstimation(BaseModel):
    """Complete activity-based effort estimates for one transformation.

    ``activity_effort_estimates`` must contain exactly one estimate for every
    modeled ``HumanAgentActivity``. An empty collection is valid when no
    human-agent activities were modeled and contributes zero added effort.

    This contract describes human effort assumptions; it does not estimate
    agent execution time, capacity, throughput, staffing, or financial impact.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    activity_effort_estimates: tuple[ActivityEffortEstimate, ...] = ()
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


class TransformationDecompositionResult(BaseModel):
    """Transformation facts plus authoritative canonical transformation impact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_decomposition: TaskDecomposition
    retain_remove_classification: RetainRemoveClassification
    agentic_task_synthesis: AgenticTaskSynthesis | None = None
    human_agent_activity_modeling: HumanAgentActivityModel | None = None
    activity_effort_estimation: ActivityEffortEstimation | None = None
    baseline_calibration_source: Literal["supplied", "baseline_bottom_up"] | None = None
    accounting: CanonicalTransformationImpact
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    provider_provenance: tuple[ProviderProvenance, ...] = ()
    normalized_work_estimates: tuple[NormalizedWorkEstimate, ...] = ()
    estimation_assumptions: tuple[str, ...] = ()


__all__ = [
    "ActivityEffortEstimate",
    "ActivityEffortEstimation",
    "AgenticTask",
    "AgenticTaskSynthesis",
    "BaselineEffortAllocation",
    "BaselineEffortEstimation",
    "BaselineSubtaskEffortEstimate",
    "ClassifiedSubtask",
    "HumanAgentActivity",
    "HumanAgentActivityCategory",
    "HumanAgentActivityModel",
    "NormalizedWorkEstimate",
    "OperationalDecomposition",
    "OperationalSubtask",
    "ParentOutputContract",
    "RetainRemoveClassification",
    "TaskDecomposition",
    "TaskReference",
    "TransformationDecompositionResult",
]
