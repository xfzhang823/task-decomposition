"""Small portable provenance references; persistence remains host-owned."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1)
    value: str = Field(min_length=1)


class ProviderStage(str, Enum):
    """The provider-driven stages supported by the standalone application."""

    OPERATIONAL_DECOMPOSITION = "operational_decomposition"
    RETAIN_REMOVE_CLASSIFICATION = "retain_remove_classification"
    AGENTIC_TASK_SYNTHESIS = "agentic_task_synthesis"
    HUMAN_AGENT_ACTIVITY_MODELING = "human_agent_activity_modeling"
    ACTIVITY_EFFORT_ESTIMATION = "activity_effort_estimation"
    ADDED_WORK_CLASSIFICATION = "added_work_classification"


class ProviderProvenance(BaseModel):
    """Portable provider metadata, without traces or persistence concerns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(min_length=1)
    stage: ProviderStage
    model_id: str | None = None
    request_id: str | None = None
    references: tuple[ProvenanceRef, ...] = ()
