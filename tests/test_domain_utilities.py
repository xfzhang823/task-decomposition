from decimal import Decimal

import pytest

from task_decomposition import (
    EffortQuantity,
    EffortUnit,
    TimeBasis,
    TransformationClassification,
    TransformationRow,
    aggregate_baseline_rows,
    allocate_effort,
)
from task_decomposition.errors import AccountingInvariantError


def effort(value):
    return EffortQuantity(
        value=value, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION
    )


def test_effort_allocation_is_deterministic_and_balanced():
    result = allocate_effort(effort(100), {"a": 1, "b": 3})
    assert result["a"].value == Decimal("25")
    assert result["b"].value == Decimal("75")


def test_rows_aggregate_retain_and_gross_remove_only():
    rows = [
        TransformationRow(
            row_id="r1",
            classification=TransformationClassification.RETAIN,
            effort=effort(60),
        ),
        TransformationRow(
            row_id="r2",
            classification=TransformationClassification.REMOVE,
            effort=effort(40),
        ),
    ]
    assert aggregate_baseline_rows(rows) == (Decimal("60"), Decimal("40"))


def test_effort_bearing_rows_are_required_for_aggregation():
    row = TransformationRow(
        row_id="r1", classification=TransformationClassification.RETAIN
    )
    with pytest.raises(AccountingInvariantError):
        aggregate_baseline_rows([row])
