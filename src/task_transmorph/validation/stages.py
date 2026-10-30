"""Cross-stage validation for provider output before canonical accounting."""

from collections.abc import Iterable

from pydantic import ValidationError

from task_transmorph.contracts.decomposition import TransformationClassification
from task_transmorph.contracts.effort import (
    EffortQuantity,
    TimeBasis,
    convert_effort_quantity,
)
from task_transmorph.contracts.stages import (
    ActivityEffortEstimation,
    AgenticTaskSynthesis,
    BaselineSubtaskEffortEstimate,
    HumanAgentActivityModel,
    OperationalDecomposition,
    RetainRemoveClassification,
    TaskReference,
)
from task_transmorph.errors import (
    CardinalityError,
    IdentityMismatchError,
    StageDependencyError,
    StageValidationError,
    UnknownReferenceError,
)


def validate_operational_decomposition(
    value: OperationalDecomposition | dict,
) -> OperationalDecomposition:
    output = _validate_model(value, OperationalDecomposition)
    _require_unique(
        (item.subtask_id for item in output.operational_subtasks),
        "operational subtask IDs",
    )
    expected_indexes = list(range(1, len(output.operational_subtasks) + 1))
    if [
        item.sequence_index for item in output.operational_subtasks
    ] != expected_indexes:
        raise CardinalityError(
            "operational sequence indexes must be 1-based and contiguous"
        )
    weights = tuple(item.relative_effort_weight for item in output.operational_subtasks)
    if not output.baseline_effort_estimates:
        raise StageValidationError(
            "canonical operational decomposition requires bottom-up baseline effort estimates"
        )
    if any(weight is not None for weight in weights) and any(
        weight is None for weight in weights
    ):
        raise StageValidationError(
            "relative effort weights must be provided for every operational subtask"
        )
    subtask_ids = {item.subtask_id for item in output.operational_subtasks}
    positions = {
        item.subtask_id: item.sequence_index for item in output.operational_subtasks
    }
    for item in output.operational_subtasks:
        if item.subtask_id in item.depends_on:
            raise StageDependencyError(
                f"subtask {item.subtask_id!r} cannot depend on itself"
            )
        if len(set(item.depends_on)) != len(item.depends_on):
            raise StageDependencyError(
                f"subtask {item.subtask_id!r} contains duplicate dependencies"
            )
        unknown = set(item.depends_on) - subtask_ids
        if unknown:
            raise UnknownReferenceError(
                f"subtask {item.subtask_id!r} has unknown dependencies: {sorted(unknown)}"
            )
        if any(
            positions[dependency] >= item.sequence_index
            for dependency in item.depends_on
        ):
            raise StageDependencyError(
                f"subtask {item.subtask_id!r} dependencies must precede it"
            )
    return validate_baseline_effort_estimates(output)


def validate_baseline_effort_estimates(
    value: OperationalDecomposition,
) -> OperationalDecomposition:
    """Validate and canonicalize optional bottom-up baseline estimates.

    The canonical provider contract requires the collection. When present, it
    must cover every subtask exactly once. Compatible duration units are
    converted to the first estimate's unit before deterministic products are
    used by the application.
    """
    estimates = value.baseline_effort_estimates
    if not estimates:
        return value
    known = {item.subtask_id for item in value.operational_subtasks}
    actual = [item.subtask_id for item in estimates]
    _require_unique(actual, "baseline effort estimate IDs")
    unknown = set(actual) - known
    if unknown:
        raise UnknownReferenceError(
            f"baseline effort estimates have unknown subtasks: {sorted(unknown)}"
        )
    missing = known - set(actual)
    if missing:
        raise CardinalityError(f"missing baseline effort estimates: {sorted(missing)}")
    target_unit = estimates[0].active_effort_per_occurrence.unit
    normalized: list[BaselineSubtaskEffortEstimate] = []
    for estimate in estimates:
        active = estimate.active_effort_per_occurrence
        if active.time_basis is not TimeBasis.PER_OPERATION:
            raise StageValidationError(
                "baseline effort per parent output must use per_operation time basis"
            )
        try:
            active = convert_effort_quantity(active, target_unit)
            expected = (
                convert_effort_quantity(
                    estimate.expected_effort_per_parent_output, target_unit
                )
                if estimate.expected_effort_per_parent_output is not None
                else None
            )
        except Exception as exc:
            raise StageValidationError(
                f"baseline estimate {estimate.subtask_id!r} uses incompatible units"
            ) from exc
        product = EffortQuantity(
            value=estimate.expected_occurrences_per_parent_output * active.value,
            unit=target_unit,
            time_basis=active.time_basis,
        )
        if expected is not None and expected.value != product.value:
            raise StageValidationError(
                f"baseline estimate {estimate.subtask_id!r} expected effort does not "
                "equal occurrences multiplied by effort per occurrence"
            )
        normalized.append(
            estimate.model_copy(
                update={
                    "active_effort_per_occurrence": active,
                    "expected_effort_per_parent_output": product,
                }
            )
        )
    return value.model_copy(update={"baseline_effort_estimates": tuple(normalized)})


def validate_retain_remove_classification(
    operational: OperationalDecomposition,
    value: RetainRemoveClassification | dict,
) -> RetainRemoveClassification:
    output = _validate_model(value, RetainRemoveClassification)
    _require_task_identity(operational.task, output.task)
    _require_unique(
        (item.subtask_id for item in output.classified_subtasks),
        "classified subtask IDs",
    )
    _validate_optional_sequence_indexes(
        output.classified_subtasks, label="classification"
    )
    expected = {item.subtask_id for item in operational.operational_subtasks}
    actual = {item.subtask_id for item in output.classified_subtasks}
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise CardinalityError(
            f"missing classifications for subtasks: {sorted(missing)}"
        )
    if extra:
        raise UnknownReferenceError(f"unknown classified subtasks: {sorted(extra)}")
    if len(output.classified_subtasks) != len(operational.operational_subtasks):
        raise CardinalityError(
            "classification count must equal operational subtask count"
        )
    # Classification rows reference the frozen operational decomposition by ID.
    # Names and sequence metadata are descriptive echoes, so never let a provider
    # redefine them or cause downstream consumers to use a regenerated label.
    canonical_by_id = {
        item.subtask_id: item for item in operational.operational_subtasks
    }
    output = output.model_copy(
        update={
            "task": operational.task,
            "classified_subtasks": tuple(
                item.model_copy(
                    update={
                        "subtask_name": canonical_by_id[item.subtask_id].subtask_name,
                        "sequence_index": canonical_by_id[
                            item.subtask_id
                        ].sequence_index,
                    }
                )
                for item in output.classified_subtasks
            ),
        }
    )
    classified_indexes = tuple(
        item.sequence_index for item in output.classified_subtasks
    )
    if all(index is not None for index in classified_indexes):
        expected_order = tuple(
            item.subtask_id for item in operational.operational_subtasks
        )
        actual_order = tuple(
            item.subtask_id
            for item in sorted(
                output.classified_subtasks,
                key=lambda item: item.sequence_index,
            )
        )
        if actual_order != expected_order:
            raise IdentityMismatchError(
                "classification sequence does not preserve operational subtask order"
            )
    return output


def validate_agentic_task_synthesis(
    operational: OperationalDecomposition,
    classification: RetainRemoveClassification,
    value: AgenticTaskSynthesis | dict,
) -> AgenticTaskSynthesis:
    """Validate complete, non-overlapping coverage of removed subtasks."""
    output = _validate_model(value, AgenticTaskSynthesis)
    _require_task_identity(operational.task, output.task)
    _require_unique(
        (item.agentic_task_id for item in output.agentic_tasks), "agentic task IDs"
    )
    known = {item.subtask_id for item in operational.operational_subtasks}
    removed = {
        item.subtask_id
        for item in classification.classified_subtasks
        if item.classification is TransformationClassification.REMOVE
    }
    assigned: list[str] = []
    for task in output.agentic_tasks:
        if len(set(task.source_subtask_ids)) != len(task.source_subtask_ids):
            raise CardinalityError(
                f"agentic task {task.agentic_task_id!r} has duplicate source subtasks"
            )
        unknown = set(task.source_subtask_ids) - known
        if unknown:
            raise UnknownReferenceError(
                f"agentic task {task.agentic_task_id!r} has unknown source subtasks: "
                f"{sorted(unknown)}"
            )
        retained = set(task.source_subtask_ids) - removed
        if retained:
            raise StageValidationError(
                f"agentic task {task.agentic_task_id!r} references non-REMOVE subtasks: "
                f"{sorted(retained)}"
            )
        assigned.extend(task.source_subtask_ids)
    duplicates = {item for item in assigned if assigned.count(item) > 1}
    if duplicates:
        raise CardinalityError(
            f"agentic task sources cannot be assigned more than once: {sorted(duplicates)}"
        )
    assigned_set = set(assigned)
    missing = removed - assigned_set
    if missing:
        raise CardinalityError(
            f"missing agentic task coverage for removed subtasks: {sorted(missing)}"
        )
    if not removed and output.agentic_tasks:
        raise CardinalityError("zero REMOVE subtasks require zero agentic tasks")
    return output.model_copy(update={"task": operational.task})


def validate_human_agent_activity_model(
    operational: OperationalDecomposition,
    classification: RetainRemoveClassification,
    synthesis: AgenticTaskSynthesis,
    value: HumanAgentActivityModel | dict,
) -> HumanAgentActivityModel:
    """Validate activity IDs and references to the completed synthesis."""
    del (
        classification
    )  # Reserved for future semantic checks; synthesis is authoritative.
    output = _validate_model(value, HumanAgentActivityModel)
    _require_task_identity(operational.task, output.task)
    _require_unique(
        (item.activity_id for item in output.activities), "human activity IDs"
    )
    if not synthesis.agentic_tasks and output.activities:
        raise CardinalityError("zero agentic tasks require zero human-agent activities")
    known = {item.agentic_task_id for item in synthesis.agentic_tasks}
    for activity in output.activities:
        if len(set(activity.agentic_task_ids)) != len(activity.agentic_task_ids):
            raise CardinalityError(
                f"human activity {activity.activity_id!r} has duplicate agentic tasks"
            )
        unknown = set(activity.agentic_task_ids) - known
        if unknown:
            raise UnknownReferenceError(
                f"human activity {activity.activity_id!r} has unknown agentic tasks: "
                f"{sorted(unknown)}"
            )
    return output.model_copy(update={"task": operational.task})


def validate_activity_effort_estimation(
    operational: OperationalDecomposition,
    activities,
    value: ActivityEffortEstimation | dict,
) -> ActivityEffortEstimation:
    """Validate one deterministic effort estimate for every modeled activity."""
    output = _validate_model(value, ActivityEffortEstimation)
    _require_task_identity(operational.task, output.task)
    known = {item.activity_id for item in activities.activities}
    actual = [item.activity_id for item in output.activity_effort_estimates]
    _require_unique(actual, "activity effort estimate IDs")
    unknown = set(actual) - known
    if unknown:
        raise UnknownReferenceError(
            f"activity effort estimates have unknown activities: {sorted(unknown)}"
        )
    missing = known - set(actual)
    if missing:
        raise CardinalityError(f"missing activity effort estimates: {sorted(missing)}")
    if not actual and known:
        raise CardinalityError("modeled activities require effort estimates")
    units = {
        (
            estimate.active_effort_per_occurrence.unit,
            estimate.active_effort_per_occurrence.time_basis,
        )
        for estimate in output.activity_effort_estimates
    }
    if len(units) > 1:
        raise StageValidationError(
            "activity effort estimates must use one compatible unit/time basis"
        )
    for estimate in output.activity_effort_estimates:
        expected = (
            estimate.expected_occurrences_per_parent_output
            * estimate.active_effort_per_occurrence.value
        )
        supplied = estimate.expected_effort_per_parent_output
        if supplied is not None and (
            supplied.unit is not estimate.active_effort_per_occurrence.unit
            or supplied.time_basis
            is not estimate.active_effort_per_occurrence.time_basis
        ):
            raise StageValidationError(
                f"activity {estimate.activity_id!r} expected effort must use the "
                "same unit/time basis as effort per occurrence"
            )
        if supplied is not None and expected != supplied.value:
            raise StageValidationError(
                f"activity {estimate.activity_id!r} expected effort does not equal "
                "occurrences multiplied by effort per occurrence"
            )
    canonical = tuple(
        estimate.model_copy(
            update={
                "expected_effort_per_parent_output": EffortQuantity(
                    value=estimate.expected_occurrences_per_parent_output
                    * estimate.active_effort_per_occurrence.value,
                    unit=estimate.active_effort_per_occurrence.unit,
                    time_basis=estimate.active_effort_per_occurrence.time_basis,
                )
            }
        )
        for estimate in output.activity_effort_estimates
    )
    return output.model_copy(
        update={
            "task": operational.task,
            "activity_effort_estimates": canonical,
        }
    )


def validate_stage_chain(
    operational: OperationalDecomposition | dict,
    classification: RetainRemoveClassification | dict,
) -> tuple[OperationalDecomposition, RetainRemoveClassification]:
    """Validate all stage contracts and their cross-stage references."""
    operational_output = validate_operational_decomposition(operational)
    classification_output = validate_retain_remove_classification(
        operational_output, classification
    )
    return operational_output, classification_output


def _validate_model(value, model):
    if isinstance(value, model):
        return value
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise StageValidationError(f"invalid {model.__name__}: {exc}") from exc


def _require_task_identity(expected: TaskReference, actual: TaskReference) -> None:
    """Require the stable task identity while ignoring provider wording echoes."""
    if (expected.task_id, expected.task_name) != (
        actual.task_id,
        actual.task_name,
    ):
        raise IdentityMismatchError(
            "stage task identity does not match operational decomposition"
        )


def _require_unique(values: Iterable[str], label: str) -> None:
    values = tuple(values)
    if len(set(values)) != len(values):
        raise CardinalityError(f"duplicate {label} are not allowed")


def _validate_optional_sequence_indexes(rows: Iterable, *, label: str) -> None:
    values = tuple(row.sequence_index for row in rows)
    present = tuple(value for value in values if value is not None)
    if present and len(present) != len(values):
        raise CardinalityError(
            f"{label} sequence indexes must be all present or all omitted"
        )
    if present and list(present) != list(range(1, len(present) + 1)):
        raise CardinalityError(
            f"{label} sequence indexes must be 1-based and contiguous"
        )


__all__ = [
    "validate_activity_effort_estimation",
    "validate_agentic_task_synthesis",
    "validate_human_agent_activity_model",
    "validate_operational_decomposition",
    "validate_retain_remove_classification",
    "validate_stage_chain",
]
