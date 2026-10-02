"""Provider protocol with no vendor, host, transport, or persistence types."""

from typing import Protocol, runtime_checkable

from task_decomposition.contracts.provider import (
    AddedWorkClassificationRequest,
    OperationalDecompositionRequest,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
)


@runtime_checkable
class DecompositionProvider(Protocol):
    """A provider proposes one untrusted output for each decomposition stage."""

    provider_id: str

    def generate_operational_decomposition(
        self, request: OperationalDecompositionRequest
    ) -> ProviderStageResponse:
        """Propose operational subtasks; no accounting is authoritative."""
        ...

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


__all__ = ["DecompositionProvider"]
