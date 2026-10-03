"""Provider protocol with no vendor, host, transport, or persistence types."""

from typing import Protocol, runtime_checkable

from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
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
    """Provider capability for classifying an existing operational baseline."""

    provider_id: str

    def classify_retain_remove(
        self, request: RetainRemoveClassificationRequest
    ) -> ProviderStageResponse:
        """Propose RETAIN/REMOVE labels for validated operational subtasks."""
        ...

    def classify_added_work(
        self, request: AddedWorkClassificationRequest
    ) -> ProviderStageResponse:
        """Propose explicitly based added-human-work rows."""
        ...


@runtime_checkable
class DecompositionProvider(
    TaskDecompositionProvider, TransformationDecompositionProvider, Protocol
):
    """Composite compatibility port implemented by concrete providers."""

    pass


__all__ = [
    "DecompositionProvider",
    "TaskDecompositionProvider",
    "TransformationDecompositionProvider",
]
