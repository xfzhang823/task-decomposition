"""Host-neutral extension ports; concrete implementations stay outside core."""

from task_decomposition.ports.benchmark import (
    BenchmarkProvider,
    BenchmarkQuery,
    BenchmarkReference,
)
from task_decomposition.ports.effort_allocator import (
    EffortAllocation,
    EffortAllocationRequest,
    EffortAllocationResult,
    EffortAllocator,
)
from task_decomposition.ports.provider import DecompositionProvider

__all__ = [
    "BenchmarkProvider",
    "BenchmarkQuery",
    "BenchmarkReference",
    "DecompositionProvider",
    "EffortAllocation",
    "EffortAllocationRequest",
    "EffortAllocationResult",
    "EffortAllocator",
]
