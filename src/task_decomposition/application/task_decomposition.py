"""Application capability for reusable task decomposition."""

from decimal import Decimal

from task_decomposition.application._provider_stage import (
    call_stage,
    provider_id,
    validate_operational_response,
)
from task_decomposition.contracts.provider import (
    OperationalDecompositionRequest,
    TaskDecompositionRequest,
)
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.contracts.stages import (
    BaselineEffortAllocation,
    TaskDecomposition,
)
from task_decomposition.errors import MissingEffortAllocationError, ProviderOutputError
from task_decomposition.ports.provider import TaskDecompositionProvider
from task_decomposition.ports.effort_allocator import (
    EffortAllocator,
    EffortAllocationRequest,
)


def decompose_task(
    request: TaskDecompositionRequest,
    provider: TaskDecompositionProvider,
    *,
    effort_allocator: EffortAllocator | None = None,
) -> TaskDecomposition:
    """Generate and validate a reusable task decomposition.

    Transformation context and accounting are deliberately absent. Baseline
    effort is either supplied through explicit weights, allocated by the
    optional host-neutral allocator, or omitted when the caller wants only an
    operational decomposition.
    """
    if not isinstance(provider, TaskDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TaskDecompositionProvider capability"
        )
    provider_name = provider_id(provider)
    response = call_stage(
        provider_name,
        ProviderStage.OPERATIONAL_DECOMPOSITION,
        provider.generate_operational_decomposition,
        OperationalDecompositionRequest(request=request),
    )
    operational = validate_operational_response(response)
    allocations = _allocate_baseline(
        request, operational, effort_allocator=effort_allocator
    )
    return TaskDecomposition(
        operational_decomposition=operational,
        baseline_effort_allocations=allocations,
        provenance_refs=operational.provenance_refs + response.provenance.references,
        provider_provenance=(response.provenance,),
    )


def _allocate_baseline(request, operational, *, effort_allocator):
    subtasks = operational.operational_subtasks
    if effort_allocator is not None:
        if request.baseline_effort is None:
            raise MissingEffortAllocationError(
                "an effort allocator requires explicit baseline_effort"
            )
        result = effort_allocator.allocate(
            EffortAllocationRequest(
                task=operational.task,
                operational_subtasks=subtasks,
                parent_effort=request.baseline_effort,
            )
        )
        by_id = {item.subtask_id: item for item in result.allocations}
        if set(by_id) != {item.subtask_id for item in subtasks}:
            raise MissingEffortAllocationError(
                "effort allocator must return one allocation per subtask"
            )
        total_effort = sum(
            (by_id[subtask.subtask_id].effort.value for subtask in subtasks),
            Decimal("0"),
        )
        if total_effort <= 0:
            raise MissingEffortAllocationError(
                "effort allocator must return a positive total effort"
            )
        return tuple(
            BaselineEffortAllocation(
                subtask_id=subtask.subtask_id,
                effort=by_id[subtask.subtask_id].effort,
                weight_ratio=(
                    Decimal(str(by_id[subtask.subtask_id].weight_ratio))
                    if by_id[subtask.subtask_id].weight_ratio is not None
                    else by_id[subtask.subtask_id].effort.value / total_effort
                ),
                provenance_refs=by_id[subtask.subtask_id].provenance_refs,
            )
            for subtask in subtasks
        )
    if request.effort_weights is None and request.baseline_effort is None:
        return ()
    if request.effort_weights is None:
        raise MissingEffortAllocationError(
            "baseline_effort requires explicit effort_weights or an effort_allocator"
        )
    expected = {item.subtask_id for item in subtasks}
    if set(request.effort_weights) != expected:
        raise MissingEffortAllocationError(
            "effort_weights must contain exactly one weight per subtask"
        )
    total = sum(request.effort_weights.values(), Decimal("0"))
    if total <= 0:
        raise MissingEffortAllocationError("effort_weights must have a positive total")
    allocated = {}
    if request.baseline_effort is not None:
        allocated = {
            subtask_id: request.baseline_effort.model_copy(
                update={"value": request.baseline_effort.value * weight / total}
            )
            for subtask_id, weight in request.effort_weights.items()
        }
    return tuple(
        BaselineEffortAllocation(
            subtask_id=subtask.subtask_id,
            effort=allocated.get(subtask.subtask_id),
            weight_ratio=request.effort_weights[subtask.subtask_id] / total,
        )
        for subtask in subtasks
    )


__all__ = ["decompose_task"]
