"""Provider-independent staged orchestration ending in Wave 1 accounting."""

from collections import defaultdict
from decimal import Decimal

from task_decomposition.contracts.accounting import AccountingMode
from task_decomposition.contracts.decomposition import TransformationClassification
from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
)
from task_decomposition.contracts.stages import (
    AddedWorkCategory,
    AddedWorkClassification,
    OperationalDecomposition,
    RetainRemoveClassification,
    StagedDecompositionResult,
)
from task_decomposition.domain.accounting import account_absolute, account_normalized
from task_decomposition.errors import (
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
    StageValidationError,
    SupportBasisConflictError,
)
from task_decomposition.validation.stages import validate_stage_chain


def run_staged_pipeline(
    operational: OperationalDecomposition | dict,
    classification: RetainRemoveClassification | dict,
    added_work: AddedWorkClassification | dict,
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    *,
    support_work_override: SupportWorkInputs | None = None,
) -> StagedDecompositionResult:
    """Validate typed stage outputs and delegate all formulas to Wave 1.

    No provider, prompt, environment variable, persistence layer, or API is
    consulted. ``accounting_input`` is explicit because staged reasoning must
    not invent effort when provider output does not contain enough information.
    """
    operational_output, classification_output, added_output = validate_stage_chain(
        operational, classification, added_work
    )
    _validate_effort_handoff(classification_output, accounting_input)
    support_inputs = (
        support_work_override
        if support_work_override is not None
        else _support_inputs(added_output, accounting_input)
    )
    try:
        if isinstance(accounting_input, AbsoluteEffortInput):
            accounting = account_absolute(
                accounting_input.model_copy(update={"support_work": support_inputs})
            )
        elif isinstance(accounting_input, NormalizedAccountingInput):
            accounting = account_normalized(
                accounting_input.model_copy(update={"support_work": support_inputs})
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
    provenance = (
        *operational_output.provenance_refs,
        *classification_output.provenance_refs,
        *added_output.provenance_refs,
    )
    return StagedDecompositionResult(
        operational_decomposition=operational_output,
        retain_remove_classification=classification_output,
        added_work_classification=added_output,
        accounting=accounting,
        provenance_refs=provenance,
    )


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
            Decimal("0"),
        )
        removed = sum(
            (
                item.effort.value
                for item in items
                if item.classification is TransformationClassification.REMOVE
            ),
            Decimal("0"),
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
            total = sum((item.effort.value for item in items), Decimal("0"))
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
                Decimal("0"),
            )
            removed = sum(
                (
                    item.effort.value
                    for item in items
                    if item.classification is TransformationClassification.REMOVE
                ),
                Decimal("0"),
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
            Decimal("0"),
        )
        removed = sum(
            (
                item.baseline_effort_ratio
                for item in items
                if item.classification is TransformationClassification.REMOVE
            ),
            Decimal("0"),
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


def _support_inputs(
    added: AddedWorkClassification, accounting_input
) -> SupportWorkInputs:
    groups = defaultdict(list)
    for row in added.added_work_rows:
        if row.amount is None:
            raise MissingAccountingInputError(
                f"added-work row {row.work_id!r} has no explicit support amount/basis"
            )
        groups[row.category].append(row.amount)
    mode = (
        AccountingMode.ABSOLUTE
        if isinstance(accounting_input, AbsoluteEffortInput)
        else AccountingMode.NORMALIZED
    )
    category_values = {
        category: _sum_support_values(
            groups.get(category, []),
            category=category,
            mode=mode,
            accounting_input=accounting_input,
        )
        for category in (
            AddedWorkCategory.GOVERNANCE,
            AddedWorkCategory.OPERATIONAL_SUPPORT,
            AddedWorkCategory.LIFECYCLE_SUPPORT,
        )
    }
    return SupportWorkInputs(
        governance=category_values[AddedWorkCategory.GOVERNANCE],
        operational_support=category_values[AddedWorkCategory.OPERATIONAL_SUPPORT],
        lifecycle_support=category_values[AddedWorkCategory.LIFECYCLE_SUPPORT],
    )


def _sum_support_values(
    values, *, category, mode, accounting_input
) -> SupportWorkInput:
    if not values:
        if mode is AccountingMode.ABSOLUTE:
            baseline = accounting_input.baseline_human_effort
            return SupportWorkInput(
                value=0,
                basis=RatioBasis.ABSOLUTE_EFFORT,
                unit=baseline.unit,
                time_basis=baseline.time_basis,
            )
        return SupportWorkInput(value=0, basis=RatioBasis.NORMALIZED_CONTRIBUTION)
    first = values[0]
    if any(value.basis is not first.basis for value in values[1:]):
        raise SupportBasisConflictError(
            f"added-work category {category} contains incompatible support bases"
        )
    if first.basis is RatioBasis.ABSOLUTE_EFFORT:
        if any(
            value.unit != first.unit or value.time_basis != first.time_basis
            for value in values[1:]
        ):
            raise IncompatibleEffortUnitError(
                f"added-work category {category} contains incompatible effort units"
            )
    return first.model_copy(
        update={"value": sum((value.value for value in values), Decimal("0"))}
    )


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


__all__ = ["run_staged_pipeline"]
