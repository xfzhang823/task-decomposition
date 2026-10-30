"""Provider protocols with no vendor, host, transport, or persistence types."""

from typing import Protocol, runtime_checkable

from task_transmorph.contracts.provider import (
    ActivityEffortEstimationRequest,
    AgenticTaskSynthesisRequest,
    HumanAgentActivityModelingRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)


@runtime_checkable
class TaskDecompositionProvider(Protocol):
    """Provider capability for proposing an operational baseline."""

    provider_id: str

    def generate_operational_decomposition(
        self, request: OperationalDecompositionRequest
    ) -> ProviderStageResponse:
        """Propose operational subtasks; no accounting is authoritative."""
        ...


@runtime_checkable
class TransformationDecompositionProvider(Protocol):
    """Provider capability for the complete canonical transformation pipeline."""

    provider_id: str

    def classify_retain_remove(
        self, request: RetainRemoveClassificationRequest
    ) -> ProviderStageResponse:
        """Propose RETAIN/REMOVE labels for validated operational subtasks."""
        ...

    def synthesize_agentic_tasks(
        self, request: AgenticTaskSynthesisRequest
    ) -> ProviderStageResponse:
        """Group removed baseline subtasks into AI responsibilities."""
        ...

    def model_human_agent_activities(
        self, request: HumanAgentActivityModelingRequest
    ) -> ProviderStageResponse:
        """Model human activities around validated AI responsibilities."""
        ...

    def estimate_activity_effort(
        self, request: ActivityEffortEstimationRequest
    ) -> ProviderStageResponse:
        """Estimate activity occurrences and active effort per occurrence."""
        ...


@runtime_checkable
class AgenticTaskSynthesisProvider(Protocol):
    """Optional capability for synthesizing semantic AI responsibilities."""

    provider_id: str

    def synthesize_agentic_tasks(
        self, request: AgenticTaskSynthesisRequest
    ) -> ProviderStageResponse:
        """Group removed baseline subtasks into AI responsibilities."""
        ...


@runtime_checkable
class HumanAgentActivityModelingProvider(Protocol):
    """Optional capability for modeling semantic human activities."""

    provider_id: str

    def model_human_agent_activities(
        self, request: HumanAgentActivityModelingRequest
    ) -> ProviderStageResponse:
        """Propose human activities around validated agentic responsibilities."""
        ...


@runtime_checkable
class ActivityEffortEstimationProvider(Protocol):
    """Optional capability for activity-based human-effort estimation."""

    provider_id: str

    def estimate_activity_effort(
        self, request: ActivityEffortEstimationRequest
    ) -> ProviderStageResponse:
        """Estimate activity inputs; application code performs arithmetic."""
        ...


@runtime_checkable
class DecompositionProvider(
    TaskDecompositionProvider, TransformationDecompositionProvider, Protocol
):
    """Combined provider capability required by the convenience composition API."""


__all__ = [
    "ActivityEffortEstimationProvider",
    "AgenticTaskSynthesisProvider",
    "DecompositionProvider",
    "HumanAgentActivityModelingProvider",
    "TaskDecompositionProvider",
    "TransformationDecompositionProvider",
]
