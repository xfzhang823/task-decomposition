"""Cross-stage validation for provider output before canonical accounting."""

from collections.abc import Iterable

from pydantic import ValidationError

from task_decomposition.contracts.decomposition import TransformationClassification
from task_decomposition.contracts.stages import (
    AddedWorkClassification,
    OperationalDecomposition,
    RetainRemoveClassification,
    TaskReference,
)
from task_decomposition.errors import (
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
    return output


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


def validate_added_work_classification(
    operational: OperationalDecomposition,
    classification: RetainRemoveClassification,
    value: AddedWorkClassification | dict,
) -> AddedWorkClassification:
    output = _validate_model(value, AddedWorkClassification)
    _require_task_identity(operational.task, output.task)
    _require_unique((row.work_id for row in output.added_work_rows), "added-work IDs")
    known_subtasks = {item.subtask_id for item in operational.operational_subtasks}
    classified = {
        item.subtask_id: item.classification
        for item in classification.classified_subtasks
    }
    for row in output.added_work_rows:
        unknown = set(row.depends_on_subtask_ids) - known_subtasks
        if unknown:
            raise UnknownReferenceError(
                f"added-work row {row.work_id!r} has unknown subtasks: {sorted(unknown)}"
            )
        if not row.source_removed_subtask_ids:
            raise StageValidationError(
                f"added-work row {row.work_id!r} requires causal removed subtasks"
            )
        if len(row.source_removed_subtask_ids) != len(
            set(row.source_removed_subtask_ids)
        ):
            raise CardinalityError(
                f"added-work row {row.work_id!r} has duplicate causal subtasks"
            )
        sources = set(row.source_removed_subtask_ids)
        unknown_sources = sources - known_subtasks
        if unknown_sources:
            raise UnknownReferenceError(
                f"added-work row {row.work_id!r} has unknown causal subtasks: "
                f"{sorted(unknown_sources)}"
            )
        if any(
            classified.get(subtask_id) is not TransformationClassification.REMOVE
            for subtask_id in sources
        ):
            raise StageValidationError(
                f"added-work row {row.work_id!r} causal sources must be REMOVE subtasks"
            )
        if (
            row.estimate
            and row.estimate.reference_subtask_id is not None
            and row.estimate.reference_subtask_id not in known_subtasks
        ):
            raise UnknownReferenceError(
                f"added-work row {row.work_id!r} has an unknown estimate reference"
            )
    _validate_optional_sequence_indexes(output.added_work_rows, label="added-work")
    return output.model_copy(update={"task": operational.task})


def validate_stage_chain(
    operational: OperationalDecomposition | dict,
    classification: RetainRemoveClassification | dict,
    added_work: AddedWorkClassification | dict,
) -> tuple[
    OperationalDecomposition, RetainRemoveClassification, AddedWorkClassification
]:
    """Validate all stage contracts and their cross-stage references."""
    operational_output = validate_operational_decomposition(operational)
    classification_output = validate_retain_remove_classification(
        operational_output, classification
    )
    added_output = validate_added_work_classification(
        operational_output, classification_output, added_work
    )
    return operational_output, classification_output, added_output


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
    "validate_added_work_classification",
    "validate_operational_decomposition",
    "validate_retain_remove_classification",
    "validate_stage_chain",
]
