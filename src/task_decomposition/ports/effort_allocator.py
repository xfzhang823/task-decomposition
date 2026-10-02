"""Optional host-neutral effort allocation extension."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from task_decomposition.contracts.effort import EffortQuantity
from task_decomposition.contracts.provenance import ProvenanceRef
from task_decomposition.contracts.stages import OperationalSubtask, TaskReference


class EffortAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskReference
    operational_subtasks: tuple[OperationalSubtask, ...] = Field(min_length=1)
    parent_effort: EffortQuantity


class EffortAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subtask_id: str = Field(min_length=1)
    effort: EffortQuantity
    weight_ratio: float | None = Field(default=None, ge=0)
    provenance_refs: tuple[ProvenanceRef, ...] = ()


class EffortAllocationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allocations: tuple[EffortAllocation, ...] = Field(min_length=1)
    provenance_refs: tuple[ProvenanceRef, ...] = ()


@runtime_checkable
class EffortAllocator(Protocol):
    """Optional allocator; it supplies row effort but never computes impact."""

    def allocate(self, request: EffortAllocationRequest) -> EffortAllocationResult: ...


__all__ = [
    "EffortAllocation",
    "EffortAllocationRequest",
    "EffortAllocationResult",
    "EffortAllocator",
]
