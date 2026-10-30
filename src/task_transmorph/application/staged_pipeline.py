"""Provider-independent staged orchestration ending in Wave 1 accounting."""

from decimal import Decimal

from task_transmorph.contracts.accounting import CanonicalTransformationImpact
from task_transmorph.contracts.decomposition import TransformationClassification
from task_transmorph.contracts.effort import (
    AbsoluteEffortInput,
    NormalizedAccountingInput,
    SupportWorkInputs,
)
from task_transmorph.contracts.stages import (
    OperationalDecomposition,
    RetainRemoveClassification,
)
from task_transmorph.domain.accounting import account_absolute, account_normalized
from task_transmorph.errors import (
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
    StageValidationError,
)
from task_transmorph.validation.stages import validate_stage_chain


def _run_staged_pipeline(
    operational: OperationalDecomposition | dict,
    classification: RetainRemoveClassification | dict,
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    *,
    support_work: SupportWorkInputs,
) -> CanonicalTransformationImpact:
    """Validate typed stage outputs and delegate all formulas to Wave 1.

    Support work is resolved by the application estimator before this handoff.
    No provider, prompt, environment variable, persistence layer, or API is
    consulted here. ``accounting_input`` is explicit because staged reasoning
    must not invent effort when provider output does not contain enough
    information.
    """
    _, classification_output = validate_stage_chain(operational, classification)
    _validate_effort_handoff(classification_output, accounting_input)
    try:
        if isinstance(accounting_input, AbsoluteEffortInput):
            accounting = account_absolute(
                accounting_input.model_copy(update={"support_work": support_work})
            )
        elif isinstance(accounting_input, NormalizedAccountingInput):
            accounting = account_normalized(
                accounting_input.model_copy(update={"support_work": support_work})
            )
        else:
            raise MissingAccountingInputError(
                "accounting_input must be an explicit Wave 1 absolute or normalized contract"
            )
    except (ValueError, TypeError) as exc:
        if isinstance(exc, StageValidationError):
            raise
        raise StageValidationError(
            f"canonical accounting handoff failed: {exc}"
        ) from exc
    return accounting


def _validate_effort_handoff(classification, accounting_input) -> None:
    items = classification.classified_subtasks
    if isinstance(accounting_input, AbsoluteEffortInput):
        provided = [item.effort is not None for item in items]
        if any(provided) and not all(provided):
            raise MissingAccountingInputError(
                "absolute classification effort must be present for every classified subtask or none"
            )
        if not all(provided):
            return
        _require_matching_units(
            item.effort for item in items if item.effort is not None
        )
        retained = sum(
            (
                item.effort.value
                for item in items
                if item.classification is TransformationClassification.RETAIN
            ),
            Decimal(0),
        )
        removed = sum(
            (
                item.effort.value
                for item in items
                if item.classification is TransformationClassification.REMOVE
            ),
            Decimal(0),
        )
        if (
            retained != accounting_input.retained_human_work.value
            or removed != accounting_input.gross_removed_work.value
        ):
            raise MissingAccountingInputError(
                "absolute Wave 1 accounting does not match classified subtask effort"
            )
    elif isinstance(accounting_input, NormalizedAccountingInput):
        provided = [item.baseline_effort_ratio is not None for item in items]
        if any(provided) and not all(provided):
            raise MissingAccountingInputError(
                "baseline_effort_ratio must be present for every classified subtask or none"
            )
        if not all(provided) and all(item.effort is not None for item in items):
            total = sum((item.effort.value for item in items), Decimal(0))
            if total <= 0:
                raise MissingAccountingInputError(
                    "classified effort must have a positive total for normalization"
                )
            retained = sum(
                (
                    item.effort.value
                    for item in items
                    if item.classification is TransformationClassification.RETAIN
                ),
                Decimal(0),
            )
            removed = sum(
                (
                    item.effort.value
                    for item in items
                    if item.classification is TransformationClassification.REMOVE
                ),
                Decimal(0),
            )
            if (
                retained / total != accounting_input.retained_work_ratio
                or removed / total != accounting_input.gross_removed_work_ratio
            ):
                raise MissingAccountingInputError(
                    "normalized Wave 1 accounting does not match classified effort"
                )
            return
        if not all(provided):
            return
        retained = sum(
            (
                item.baseline_effort_ratio
                for item in items
                if item.classification is TransformationClassification.RETAIN
            ),
            Decimal(0),
        )
        removed = sum(
            (
                item.baseline_effort_ratio
                for item in items
                if item.classification is TransformationClassification.REMOVE
            ),
            Decimal(0),
        )
        if (
            retained != accounting_input.retained_work_ratio
            or removed != accounting_input.gross_removed_work_ratio
        ):
            raise MissingAccountingInputError(
                "normalized Wave 1 accounting does not match classified effort ratios"
            )
    else:
        raise MissingAccountingInputError("missing explicit Wave 1 accounting input")


def _require_matching_units(values) -> None:
    values = tuple(values)
    if not values:
        return
    first = values[0]
    if any(
        value.unit != first.unit or value.time_basis != first.time_basis
        for value in values[1:]
    ):
        raise IncompatibleEffortUnitError(
            "classified subtask effort must share one unit/time basis"
        )
