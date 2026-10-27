"""Deterministic resolution of reference-class added-work estimates."""

from collections import defaultdict
from decimal import Decimal

from task_decomposition.contracts.effort import (
    AbsoluteEffortInput,
    EffortQuantity,
    NormalizedAccountingInput,
    RatioBasis,
    SupportWorkInput,
    SupportWorkInputs,
)
from task_decomposition.contracts.stages import (
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkEstimateDetail,
    SupportWorkMode,
    SupportWorkResolution,
)
from task_decomposition.errors import (
    AddedWorkEstimationError,
    IncompatibleEffortUnitError,
    MissingAccountingInputError,
)


def resolve_support_work(
    added: AddedWorkClassification,
    classification,
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    *,
    mode: SupportWorkMode,
) -> tuple[SupportWorkInputs, SupportWorkResolution]:
    selected, resolution, _ = resolve_support_work_with_details(
        added, classification, accounting_input, mode=mode
    )
    return selected, resolution


def resolve_support_work_with_details(
    added: AddedWorkClassification,
    classification,
    accounting_input: AbsoluteEffortInput | NormalizedAccountingInput,
    *,
    mode: SupportWorkMode,
) -> tuple[
    SupportWorkInputs,
    SupportWorkResolution,
    tuple[AddedWorkEstimateDetail, ...],
]:
    host = accounting_input.support_work
    estimates = None
    details = ()
    if mode is SupportWorkMode.ESTIMATE or (
        mode is SupportWorkMode.AUTO and host is None
    ):
        details = _derive_estimate_details(added, classification, accounting_input)
        estimates = _support_inputs_from_details(details, accounting_input)
    if mode is SupportWorkMode.HOST:
        if host is None:
            raise MissingAccountingInputError("host support work is required")
        selected = host
        source = "host"
    elif mode is SupportWorkMode.ESTIMATE:
        selected = estimates
        source = "estimate"
    elif host is not None:
        selected = host
        source = "host"
    else:
        selected = estimates
        source = "estimate"
    reconciliation = "not_applicable"
    if host is not None and estimates is not None:
        reconciliation = "match" if _support_equal(host, estimates) else "difference"
    return (
        selected,
        SupportWorkResolution(
            mode=mode,
            source_by_category={
                AddedWorkCategory.AI_INTERACTION: source,
                AddedWorkCategory.AI_VERIFICATION: source,
            },
            host_support_work=host,
            estimated_support_work=estimates,
            reconciliation=reconciliation,
        ),
        details,
    )


def _derive_estimate_details(added, classification, accounting_input):
    details = []
    by_id = {item.subtask_id: item for item in classification.classified_subtasks}
    for row in added.added_work_rows:
        if row.estimate is None:
            raise AddedWorkEstimationError(
                f"added-work row {row.work_id!r} has no computable estimate"
            )
        estimate = row.estimate
        occurrences = estimate.occurrences_per_parent_execution.typical
        relative = estimate.relative_effort_per_occurrence.typical
        if estimate.reference_subtask_id is not None:
            reference_count = (
                estimate.reference_occurrences_per_parent_execution.typical
            )
            if reference_count <= 0:
                raise AddedWorkEstimationError(
                    f"added-work row {row.work_id!r} has nonpositive reference frequency"
                )
            reference = by_id[estimate.reference_subtask_id]
            aggregate = _baseline_effort(reference, accounting_input, row.work_id)
            anchor = aggregate / reference_count
            reference_source = "baseline_subtask"
            reference_effort = _effort_representation(aggregate, accounting_input)
            reference_effort_per_occurrence = _effort_representation(
                anchor, accounting_input
            )
            external_reference_activity = None
        else:
            external = estimate.external_reference
            if external is None or external.effort_per_occurrence is None:
                raise AddedWorkEstimationError(
                    f"added-work row {row.work_id!r} lacks a quantitative external anchor"
                )
            external_anchor = external.effort_per_occurrence
            anchor = _external_effort(external_anchor, accounting_input, row.work_id)
            reference_source = "external_reference"
            reference_effort = None
            reference_effort_per_occurrence = external_anchor
            external_reference_activity = external.activity
        details.append(
            AddedWorkEstimateDetail(
                work_id=row.work_id,
                workload_name=row.workload_name,
                description=row.description,
                category=row.category,
                source_removed_subtask_ids=row.source_removed_subtask_ids,
                occurrences_per_parent_execution=estimate.occurrences_per_parent_execution,
                relative_effort_per_occurrence=estimate.relative_effort_per_occurrence,
                reference_source=reference_source,
                reference_subtask_id=estimate.reference_subtask_id,
                external_reference_activity=external_reference_activity,
                reference_effort=reference_effort,
                reference_occurrences_per_parent_execution=estimate.reference_occurrences_per_parent_execution,
                reference_effort_per_occurrence=reference_effort_per_occurrence,
                calculated_added_effort=_support_value(
                    occurrences * relative * anchor, accounting_input
                ),
                estimate_basis=estimate.estimate_basis,
                rationale=estimate.rationale,
                provenance_refs=(
                    *row.provenance_refs,
                    *estimate.provenance_refs,
                ),
            )
        )
    return tuple(details)


def _support_inputs_from_details(details, accounting_input):
    rows = defaultdict(list)
    for detail in details:
        rows[detail.category].append(detail.calculated_added_effort.value)
    zero = _zero_support(accounting_input)
    return (
        SupportWorkInputs(
            ai_interaction=_support_value(
                sum(rows[AddedWorkCategory.AI_INTERACTION], Decimal(0)),
                accounting_input,
            ),
            ai_verification=_support_value(
                sum(rows[AddedWorkCategory.AI_VERIFICATION], Decimal(0)),
                accounting_input,
            ),
        )
        if details
        else zero
    )


def _effort_representation(value, accounting_input):
    if isinstance(accounting_input, AbsoluteEffortInput):
        baseline = accounting_input.baseline_human_effort
        return EffortQuantity(
            value=value,
            unit=baseline.unit,
            time_basis=baseline.time_basis,
        )
    return SupportWorkInput(value=value, basis=RatioBasis.NORMALIZED_CONTRIBUTION)


def _baseline_effort(item, accounting_input, work_id):
    if isinstance(accounting_input, AbsoluteEffortInput):
        if item.effort is None:
            raise AddedWorkEstimationError(
                f"added-work row {work_id!r} reference has no absolute effort"
            )
        _check_unit(item.effort, accounting_input.baseline_human_effort, work_id)
        return item.effort.value
    if item.baseline_effort_ratio is None:
        raise AddedWorkEstimationError(
            f"added-work row {work_id!r} reference has no baseline effort ratio"
        )
    return item.baseline_effort_ratio


def _external_effort(anchor, accounting_input, work_id):
    if isinstance(anchor, EffortQuantity):
        if not isinstance(accounting_input, AbsoluteEffortInput):
            raise AddedWorkEstimationError(
                f"added-work row {work_id!r} external anchor is not normalized"
            )
        _check_unit(anchor, accounting_input.baseline_human_effort, work_id)
        return anchor.value
    if isinstance(accounting_input, AbsoluteEffortInput):
        raise AddedWorkEstimationError(
            f"added-work row {work_id!r} external anchor must use absolute effort"
        )
    if anchor.basis not in (
        RatioBasis.NORMALIZED_CONTRIBUTION,
        RatioBasis.RATIO_OF_BASELINE_WORK,
    ):
        raise AddedWorkEstimationError(
            f"added-work row {work_id!r} external anchor has incompatible basis"
        )
    return anchor.value


def _support_value(value, accounting_input):
    if isinstance(accounting_input, AbsoluteEffortInput):
        baseline = accounting_input.baseline_human_effort
        return SupportWorkInput(
            value=value,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=baseline.unit,
            time_basis=baseline.time_basis,
        )
    return SupportWorkInput(value=value, basis=RatioBasis.NORMALIZED_CONTRIBUTION)


def _zero_support(accounting_input):
    return SupportWorkInputs(
        ai_interaction=_support_value(Decimal(0), accounting_input),
        ai_verification=_support_value(Decimal(0), accounting_input),
    )


def _check_unit(left, right, work_id):
    if left.unit is not right.unit or left.time_basis is not right.time_basis:
        raise IncompatibleEffortUnitError(
            f"added-work row {work_id!r} reference effort has incompatible units"
        )


def _support_equal(left, right):
    return (
        left.ai_interaction == right.ai_interaction
        and left.ai_verification == right.ai_verification
    )


__all__ = ["resolve_support_work", "resolve_support_work_with_details"]
