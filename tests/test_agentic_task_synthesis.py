from decimal import Decimal

import pytest
from pydantic import ValidationError
from test_task_transformation_boundaries import (
    TASK,
    BoundaryProvider,
    operational,
    task_request,
    transform_request,
)

from task_transmorph import (
    AgenticTask,
    AgenticTaskSynthesis,
    CardinalityError,
    ClassifiedSubtask,
    ProviderOutputError,
    ProviderStage,
    RetainRemoveClassification,
    StageValidationError,
    UnknownReferenceError,
    decompose_task,
    decompose_transformation,
    validate_agentic_task_synthesis,
)
from task_transmorph.errors import ProviderContractValidationError


def classification(*labels):
    return RetainRemoveClassification(
        task=TASK,
        classified_subtasks=tuple(
            ClassifiedSubtask(
                subtask_id=f"sub-{index}",
                classification=label,
            )
            for index, label in enumerate(labels, start=1)
        ),
    )


def agentic(task_id, sources):
    return AgenticTask(
        agentic_task_id=task_id,
        agentic_task_name=f"Agentic responsibility {task_id}",
        description="Complete the delegated assessment responsibility.",
        source_subtask_ids=tuple(sources),
        required_inputs=("request",),
        expected_outputs=("structured assessment",),
    )


def synthesis(tasks):
    return AgenticTaskSynthesis(task=TASK, agentic_tasks=tuple(tasks))


@pytest.mark.parametrize(
    ("labels", "tasks"),
    [
        (
            ("REMOVE", "RETAIN", "RETAIN"),
            (agentic("AGT001", ("sub-1",)),),
        ),
        (
            ("REMOVE", "REMOVE", "REMOVE"),
            (agentic("AGT001", ("sub-1", "sub-2", "sub-3")),),
        ),
        (
            ("REMOVE", "RETAIN", "REMOVE"),
            (
                agentic("AGT001", ("sub-1",)),
                agentic("AGT002", ("sub-3",)),
            ),
        ),
    ],
)
def test_agentic_tasks_cover_removed_work_in_coherent_groups(labels, tasks):
    result = validate_agentic_task_synthesis(
        operational(), classification(*labels), synthesis(tasks)
    )

    assert result.agentic_tasks == tasks


def test_retained_sources_are_rejected():
    with pytest.raises(StageValidationError, match="non-REMOVE"):
        validate_agentic_task_synthesis(
            operational(),
            classification("REMOVE", "RETAIN", "REMOVE"),
            synthesis((agentic("AGT001", ("sub-1", "sub-2", "sub-3")),)),
        )


def test_duplicate_sources_are_rejected():
    with pytest.raises(CardinalityError, match="more than once"):
        validate_agentic_task_synthesis(
            operational(),
            classification("REMOVE", "REMOVE", "RETAIN"),
            synthesis(
                (
                    agentic("AGT001", ("sub-1",)),
                    agentic("AGT002", ("sub-1", "sub-2")),
                )
            ),
        )


def test_unknown_sources_are_rejected():
    with pytest.raises(UnknownReferenceError, match="unknown source"):
        validate_agentic_task_synthesis(
            operational(),
            classification("REMOVE", "RETAIN", "RETAIN"),
            synthesis((agentic("AGT001", ("missing",)),)),
        )


def test_missing_removed_coverage_is_rejected():
    with pytest.raises(CardinalityError, match="missing agentic task coverage"):
        validate_agentic_task_synthesis(
            operational(),
            classification("REMOVE", "REMOVE", "RETAIN"),
            synthesis((agentic("AGT001", ("sub-1",)),)),
        )


def test_zero_removed_subtasks_produce_zero_agentic_tasks():
    result = validate_agentic_task_synthesis(
        operational(),
        classification("RETAIN", "RETAIN", "RETAIN"),
        synthesis(()),
    )

    assert result.agentic_tasks == ()


def test_agentic_task_requires_responsibility_inputs_and_outputs():
    with pytest.raises(ValidationError):
        AgenticTask(
            agentic_task_id="AGT001",
            agentic_task_name="Assess request",
            description="",
            source_subtask_ids=("sub-1",),
            required_inputs=(),
            expected_outputs=(),
        )


class SynthesisProvider(BoundaryProvider):
    def synthesize_agentic_tasks(self, request):
        self.calls.append("synthesis")
        return self._response(
            ProviderStage.AGENTIC_TASK_SYNTHESIS,
            synthesis((agentic("AGT001", ("sub-2",)),)),
        )


def test_canonical_synthesis_precedes_activity_effort_without_changing_accounting():
    provider = SynthesisProvider()
    baseline = decompose_task(task_request(), provider)
    result = decompose_transformation(transform_request(baseline), provider)

    assert provider.calls == [
        "task",
        "retain-remove",
        "synthesis",
        "activities",
        "activity-effort",
    ]
    assert result.agentic_task_synthesis is not None
    assert result.agentic_task_synthesis.agentic_tasks[0].source_subtask_ids == (
        "sub-2",
    )
    assert result.accounting.w0 == Decimal(100)
    assert result.accounting.w1 == Decimal(74)
    assert result.accounting.net_substitution_ratio == Decimal("0.26")


def test_all_removed_with_required_verification_produces_positive_w1():
    from test_task_transformation_boundaries import AllRemovedVerificationProvider

    provider = AllRemovedVerificationProvider()
    baseline = decompose_task(task_request(), provider)
    result = decompose_transformation(transform_request(baseline), provider)

    assert result.human_agent_activity_modeling.activities[0].category.value == (
        "AI_VERIFICATION"
    )
    assert result.accounting.w1 == Decimal(5)
    assert result.accounting.net_substitution_ratio == Decimal("0.95")


def test_all_removed_with_legitimate_zero_human_effort_is_valid():
    from test_task_transformation_boundaries import AllRemovedAutonomousProvider

    provider = AllRemovedAutonomousProvider()
    baseline = decompose_task(task_request(), provider)
    result = decompose_transformation(transform_request(baseline), provider)

    assert result.human_agent_activity_modeling.activities == ()
    assert result.activity_effort_estimation.activity_effort_estimates == ()
    assert result.accounting.w1 == Decimal(0)
    assert result.accounting.net_substitution_ratio == Decimal(1)
    assert result.accounting.net_augmentation_multiplier is None


def test_activity_effort_missing_for_modeled_activity_fails_explicitly():
    from test_task_transformation_boundaries import MissingActivityEffortProvider

    provider = MissingActivityEffortProvider()
    baseline = decompose_task(task_request(), provider)

    with pytest.raises(
        ProviderContractValidationError, match="missing activity effort"
    ):
        decompose_transformation(transform_request(baseline), provider)


def test_provider_without_canonical_capabilities_fails_explicitly():
    class IncompleteProvider:
        provider_id = "incomplete"

    with pytest.raises(
        ProviderOutputError, match="TransformationDecompositionProvider"
    ):
        decompose_transformation(
            transform_request(decompose_task(task_request(), BoundaryProvider())),
            IncompleteProvider(),
        )


class InvalidSynthesisProvider(SynthesisProvider):
    def synthesize_agentic_tasks(self, request):
        self.calls.append("synthesis")
        return self._response(
            ProviderStage.AGENTIC_TASK_SYNTHESIS,
            synthesis(()),
        )


def test_supported_provider_with_invalid_mapping_fails_instead_of_skipping():
    provider = InvalidSynthesisProvider()
    baseline = decompose_task(task_request(), provider)

    with pytest.raises(ProviderContractValidationError, match="missing agentic"):
        decompose_transformation(transform_request(baseline), provider)
