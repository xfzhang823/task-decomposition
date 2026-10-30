"""Typed contracts for provider-independent semantic evaluation."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from task_transmorph.contracts.accounting import CanonicalTransformationImpact
from task_transmorph.contracts.stages import (
    ActivityEffortEstimation,
    AgenticTaskSynthesis,
    HumanAgentActivityModel,
    OperationalDecomposition,
    ParentOutputContract,
    RetainRemoveClassification,
    TaskDecomposition,
    TaskReference,
)


class SemanticEvaluationDecision(str, Enum):
    """Top-level semantic evaluation outcomes."""

    ACCEPT = "accept"
    REPAIR = "repair"
    REJECT = "reject"


class SemanticFindingSeverity(str, Enum):
    """Whether a finding is informational, repairable, or blocking."""

    SUGGESTION = "suggestion"
    REPAIRABLE = "repairable"
    BLOCKING = "blocking"


class TransformationSemanticCriterion(str, Enum):
    """Criteria reported by the transformation semantic checkpoint."""

    HUMAN_RESPONSIBILITY_COMPLETENESS = "human_responsibility_completeness"
    DOUBLE_COUNTING = "double_counting"
    TASK_BOUNDARY = "task_boundary"
    ACTIVE_HUMAN_EFFORT = "active_human_effort"
    OCCURRENCE_ASSUMPTIONS = "occurrence_assumptions"


class SemanticFindingCategory(str, Enum):
    """Stable high-level categories used by the semantic rubric."""

    ABSTRACTION = "abstraction"
    OUTCOME = "outcome"
    OVERLAP = "overlap"
    GRANULARITY = "granularity"
    COMPLETENESS = "completeness"
    POLICY = "policy"


class SemanticFindingCode(str, Enum):
    """Stable machine-readable finding codes for future repair feedback."""

    INSUFFICIENT_OPERATIONAL_SPECIFICITY = "insufficient_operational_specificity"
    OUTCOME_NOT_WORK = "outcome_not_work"
    OVERLAPPING_SUBTASKS = "overlapping_subtasks"
    INAPPROPRIATE_GRANULARITY = "inappropriate_granularity"
    INCOMPLETE_COVERAGE = "incomplete_coverage"
    INTERNAL_META_TASK = "internal_meta_task"
    CLARIFY_WORK_DESCRIPTION = "clarify_work_description"


class SemanticEvaluatorProvenance(BaseModel):
    """Optional provider metadata attached to an evaluator result.

    This is deliberately transport-neutral. Provider adapters can populate it
    later without making the evaluator contracts depend on an SDK response.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(min_length=1)
    model_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None


class SemanticEvaluationRequest(BaseModel):
    """Complete operational decomposition presented to the evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    task_context: dict[str, str] = Field(default_factory=dict)
    operational_decomposition: OperationalDecomposition
    rubric_version: str = Field(min_length=1)
    request_id: str | None = None
    correlation_id: str | None = None


class TransformationSemanticEvaluationRequest(BaseModel):
    """Complete frozen transformation presented to the semantic evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    transformation_context: dict[str, str] = Field(default_factory=dict)
    parent_output_contract: ParentOutputContract | None = None
    task_decomposition: TaskDecomposition
    retain_remove_classification: RetainRemoveClassification
    agentic_task_synthesis: AgenticTaskSynthesis
    human_agent_activity_modeling: HumanAgentActivityModel
    activity_effort_estimation: ActivityEffortEstimation
    accounting: CanonicalTransformationImpact
    rubric_version: str = Field(min_length=1)
    request_id: str | None = None
    correlation_id: str | None = None


class SemanticFinding(BaseModel):
    """Actionable semantic feedback about a decomposition or subtask."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subtask_id: str | None = None
    code: SemanticFindingCode
    category: SemanticFindingCategory
    severity: SemanticFindingSeverity
    message: str = Field(min_length=1)
    evidence: str | None = None
    criterion: TransformationSemanticCriterion | None = None
    affected_references: tuple[str, ...] = ()


class SemanticEvaluation(BaseModel):
    """Structured semantic decision returned by an evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: SemanticEvaluationDecision
    findings: tuple[SemanticFinding, ...] = ()
    rubric_version: str = Field(min_length=1)
    evaluator_provenance: SemanticEvaluatorProvenance | None = None

    @model_validator(mode="after")
    def validate_decision_findings(self) -> "SemanticEvaluation":
        severities = {finding.severity for finding in self.findings}

        if self.decision is SemanticEvaluationDecision.ACCEPT and (
            SemanticFindingSeverity.REPAIRABLE in severities
            or SemanticFindingSeverity.BLOCKING in severities
        ):
            raise ValueError("accept evaluations may contain suggestions only")

        if self.decision is SemanticEvaluationDecision.REPAIR:
            if SemanticFindingSeverity.REPAIRABLE not in severities:
                raise ValueError("repair evaluations require a repairable finding")
            if SemanticFindingSeverity.BLOCKING in severities:
                raise ValueError("repair evaluations cannot contain blocking findings")

        if self.decision is SemanticEvaluationDecision.REJECT and (
            SemanticFindingSeverity.BLOCKING not in severities
        ):
            raise ValueError("reject evaluations require a blocking finding")

        return self


__all__ = [
    "SemanticEvaluation",
    "SemanticEvaluationDecision",
    "SemanticEvaluationRequest",
    "SemanticEvaluatorProvenance",
    "SemanticFinding",
    "SemanticFindingCategory",
    "SemanticFindingCode",
    "SemanticFindingSeverity",
    "TransformationSemanticCriterion",
    "TransformationSemanticEvaluationRequest",
]
