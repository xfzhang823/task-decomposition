"""Host-neutral extension ports; concrete implementations stay outside core."""

from task_decomposition.ports.effort_allocator import (
    EffortAllocation,
    EffortAllocationRequest,
    EffortAllocationResult,
    EffortAllocator,
)
from task_decomposition.ports.provider import (
    DecompositionProvider,
    TaskDecompositionProvider,
    TransformationDecompositionProvider,
)

__all__ = [
    "DecompositionProvider",
    "TaskDecompositionProvider",
    "TransformationDecompositionProvider",
    "EffortAllocation",
    "EffortAllocationRequest",
    "EffortAllocationResult",
    "EffortAllocator",
]
