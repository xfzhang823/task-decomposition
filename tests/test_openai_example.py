import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "openai_decompose_example",
    Path(__file__).parents[1] / "examples" / "openai_decompose.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)
_parse_args = _MODULE._parse_args
_derive_accounting_input = _MODULE._derive_accounting_input

from test_staged_pipeline import make_classification, make_operational

from task_decomposition import (
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecomposition,
    TransformationClassification,
)
from task_decomposition.errors import (
    MissingAccountingInputError,
    MissingEffortAllocationError,
)


def accounting_fixture(weights, labels):
    operational = make_operational().model_copy(
        update={
            "operational_subtasks": tuple(
                subtask.model_copy(update={"relative_effort_weight": weight})
                for subtask, weight in zip(
                    make_operational().operational_subtasks, weights
                )
            )
        }
    )
    baseline = TaskDecomposition(operational_decomposition=operational)
    classification = make_classification().model_copy(
        update={
            "classified_subtasks": tuple(
                row.model_copy(update={"classification": label})
                for row, label in zip(make_classification().classified_subtasks, labels)
            )
        }
    )
    return baseline, classification


def zero_support():
    return SupportWorkInputs(
        ai_interaction=SupportWorkInput(
            value=0,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=_MODULE.EffortUnit.EFFORT,
            time_basis=_MODULE.TimeBasis.PER_OPERATION,
        ),
        ai_verification=SupportWorkInput(
            value=0,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=_MODULE.EffortUnit.EFFORT,
            time_basis=_MODULE.TimeBasis.PER_OPERATION,
        ),
    )


def test_production_scheduling_example_uses_domain_neutral_context(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "openai_decompose.py",
            "--task-name",
            "Production Scheduling",
            "--task-description",
            "Review production orders and develop a feasible schedule.",
        ],
    )

    args = _parse_args()

    assert args.domain == "production_scheduling"


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        ((TransformationClassification.RETAIN,) * 3, (Decimal(100), Decimal(0))),
        ((TransformationClassification.REMOVE,) * 3, (Decimal(0), Decimal(100))),
        (
            (
                TransformationClassification.RETAIN,
                TransformationClassification.REMOVE,
                TransformationClassification.RETAIN,
            ),
            (Decimal(70), Decimal(30)),
        ),
    ],
)
def test_example_accounting_derives_retain_remove_effort(labels, expected):
    baseline, classification = accounting_fixture((2, 3, 5), labels)
    support = zero_support()

    result = _derive_accounting_input(
        baseline,
        classification,
        baseline_human_effort=_MODULE.EffortQuantity(
            value=100,
            unit=_MODULE.EffortUnit.EFFORT,
            time_basis=_MODULE.TimeBasis.PER_OPERATION,
        ),
        support_work=support,
    )

    assert (
        result.retained_human_work.value,
        result.gross_removed_work.value,
    ) == expected
    assert (
        result.retained_human_work.value + result.gross_removed_work.value
        == result.baseline_human_effort.value
    )


def test_example_accounting_fails_without_weights_or_complete_classification():
    baseline, classification = accounting_fixture(
        (None, None, None), (TransformationClassification.RETAIN,) * 3
    )
    effort = _MODULE.EffortQuantity(
        value=100,
        unit=_MODULE.EffortUnit.EFFORT,
        time_basis=_MODULE.TimeBasis.PER_OPERATION,
    )
    support = zero_support()
    with pytest.raises(MissingEffortAllocationError):
        _derive_accounting_input(
            baseline,
            classification,
            baseline_human_effort=effort,
            support_work=support,
        )

    baseline, classification = accounting_fixture(
        (2, 3, 5), (TransformationClassification.RETAIN,) * 3
    )
    incomplete = classification.model_copy(
        update={"classified_subtasks": classification.classified_subtasks[:-1]}
    )
    with pytest.raises(MissingAccountingInputError):
        _derive_accounting_input(
            baseline,
            incomplete,
            baseline_human_effort=effort,
            support_work=support,
        )


def test_example_accounting_accepts_small_decimal_allocation_residual():
    baseline, classification = accounting_fixture(
        (1, 2, 3, 2, 3, 2, 2),
        (TransformationClassification.RETAIN,) * 7,
    )
    effort = _MODULE.EffortQuantity(
        value=100,
        unit=_MODULE.EffortUnit.EFFORT,
        time_basis=_MODULE.TimeBasis.PER_OPERATION,
    )

    result = _derive_accounting_input(
        baseline,
        classification,
        baseline_human_effort=effort,
        support_work=zero_support(),
    )

    assert result.gross_removed_work.value == Decimal(0)
    assert (
        abs(result.retained_human_work.value - Decimal(100))
        <= _MODULE.DEFAULT_TOLERANCE
    )
