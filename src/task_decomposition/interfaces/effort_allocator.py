"""Host-neutral effort allocation interface."""

from typing import Protocol, runtime_checkable

from task_decomposition.contracts.allocation import (
    EffortAllocationRequest,
    EffortAllocationResult,
)


@runtime_checkable
class EffortAllocator(Protocol):
    """Optional allocator; it supplies row effort but never computes impact."""

    def allocate(self, request: EffortAllocationRequest) -> EffortAllocationResult: ...


__all__ = ["EffortAllocator"]
