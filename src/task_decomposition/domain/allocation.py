"""Small deterministic effort allocation utility for effort-bearing rows."""

from collections.abc import Mapping
from decimal import Decimal

from task_decomposition.contracts.effort import EffortQuantity
from task_decomposition.errors import AccountingInvariantError


def allocate_effort(
    parent_effort: EffortQuantity,
    weights: Mapping[str, Decimal | int | float | str],
    *,
    tolerance: Decimal = Decimal("0.000000001"),
) -> dict[str, EffortQuantity]:
    """Allocate a parent effort quantity by normalized, non-negative weights."""
    if not weights:
        raise AccountingInvariantError("at least one effort weight is required")
    normalized = {key: Decimal(str(value)) for key, value in weights.items()}
    if any(value < 0 for value in normalized.values()):
        raise AccountingInvariantError("effort weights cannot be negative")
    total = sum(normalized.values(), Decimal("0"))
    if total <= 0:
        raise AccountingInvariantError("effort weights must have a positive total")
    result = {
        key: EffortQuantity(
            value=parent_effort.value * value / total,
            unit=parent_effort.unit,
            time_basis=parent_effort.time_basis,
        )
        for key, value in normalized.items()
    }
    if (
        abs(
            sum((item.value for item in result.values()), Decimal("0"))
            - parent_effort.value
        )
        > tolerance
    ):
        raise AccountingInvariantError(
            "allocated effort does not reconcile to parent effort"
        )
    return result
