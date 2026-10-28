from decimal import Decimal

import pytest
from pydantic import ValidationError
from test_staged_pipeline import make_agentic
from test_task_transformation_boundaries import (
    TASK,
    BoundaryProvider,
    operational,
    task_request,
    transform_request,
)

from task_decomposition import (
    CardinalityError,
    HumanAgentActivity,
    HumanAgentActivityCategory,
    HumanAgentActivityModel,
    UnknownReferenceError,
    decompose_task,
    decompose_transformation,
    validate_human_agent_activity_model,
)
from task_decomposition.contracts.stages import (
    RetainRemoveClassification,
)
from task_decomposition.providers.prompts import HUMAN_AGENT_ACTIVITY_MODELING_PROMPT


def activity(
    activity_id, task_ids, category=HumanAgentActivityCategory.AI_VERIFICATION
):
    return HumanAgentActivity(
        activity_id=activity_id,
        activity_name=f"Activity {activity_id}",
        description="Perform the required human action around agent output.",
        category=category,
        agentic_task_ids=tuple(task_ids),
        trigger="The agent produces an output requiring human action.",
        expected_action="Review or intervene and record the result.",
    )


def model(activities):
    return HumanAgentActivityModel(task=TASK, activities=tuple(activities))


def all_removed_classification():
    return RetainRemoveClassification(
        task=TASK,
        classified_subtasks=tuple(
            {"subtask_id": f"sub-{index}", "classification": "REMOVE"}
            for index in range(1, 4)
        ),
    )


def two_agentic_tasks():
    first = make_agentic().agentic_tasks[0]
    second = first.model_copy(
        update={
            "agentic_task_id": "AGT002",
            "agentic_task_name": "Apply account update",
            "source_subtask_ids": ("sub-3",),
        }
    )
    return make_agentic().model_copy(update={"agentic_tasks": (first, second)})


def test_one_agentic_task_can_have_multiple_human_activities():
    result = validate_human_agent_activity_model(
        operational(),
        all_removed_classification(),
        make_agentic(),
        model(
            (
                activity(
                    "HAA001", ("AGT001",), HumanAgentActivityCategory.AI_INTERACTION
                ),
                activity("HAA002", ("AGT001",)),
            )
        ),
    )

    assert len(result.activities) == 2


def test_one_shared_verification_activity_can_reference_multiple_agentic_tasks():
    synthesis = two_agentic_tasks()
    result = validate_human_agent_activity_model(
        operational(),
        all_removed_classification(),
        synthesis,
        model((activity("HAA001", ("AGT001", "AGT002")),)),
    )

    assert result.activities[0].agentic_task_ids == ("AGT001", "AGT002")


def test_independent_agentic_tasks_can_have_distinct_activities():
    synthesis = two_agentic_tasks()
    result = validate_human_agent_activity_model(
        operational(),
        all_removed_classification(),
        synthesis,
        model(
            (
                activity("HAA001", ("AGT001",)),
                activity(
                    "HAA002", ("AGT002",), HumanAgentActivityCategory.EXCEPTION_HANDLING
                ),
            )
        ),
    )

    assert [item.activity_id for item in result.activities] == ["HAA001", "HAA002"]


def test_agentic_tasks_may_require_no_additional_human_activities():
    result = validate_human_agent_activity_model(
        operational(), all_removed_classification(), make_agentic(), model(())
    )

    assert result.activities == ()


def test_zero_agentic_tasks_require_zero_activities():
    empty = make_agentic().model_copy(update={"agentic_tasks": ()})
    with pytest.raises(CardinalityError, match="zero agentic"):
        validate_human_agent_activity_model(
            operational(),
            all_removed_classification(),
            empty,
            model((activity("HAA001", ("AGT001",)),)),
        )


def test_unknown_agentic_task_references_are_rejected():
    with pytest.raises(UnknownReferenceError, match="unknown agentic"):
        validate_human_agent_activity_model(
            operational(),
            all_removed_classification(),
            make_agentic(),
            model((activity("HAA001", ("missing",)),)),
        )


def test_duplicate_activity_ids_are_rejected():
    with pytest.raises(CardinalityError, match="duplicate human activity"):
        validate_human_agent_activity_model(
            operational(),
            all_removed_classification(),
            make_agentic(),
            model((activity("HAA001", ("AGT001",)), activity("HAA001", ("AGT001",)))),
        )


def test_activity_contract_requires_nonempty_fields_and_supported_category():
    with pytest.raises(ValidationError):
        HumanAgentActivity(
            activity_id="HAA001",
            activity_name="",
            description="description",
            category="NOT_SUPPORTED",
            agentic_task_ids=("AGT001",),
            trigger="trigger",
            expected_action="action",
        )


def test_external_provider_without_modeling_capability_remains_compatible():
    provider = BoundaryProvider()
    baseline = decompose_task(task_request(), provider)
    result = decompose_transformation(transform_request(baseline), provider)

    assert result.human_agent_activity_modeling is None
    assert result.accounting.w0 == Decimal(100)


def test_modeling_prompt_preserves_retained_human_boundaries_and_no_effort_semantics():
    assert "Do not recreate REMOVE work" in HUMAN_AGENT_ACTIVITY_MODELING_PROMPT
    assert "Retained approval" in HUMAN_AGENT_ACTIVITY_MODELING_PROMPT
    assert "Do not estimate occurrences" in HUMAN_AGENT_ACTIVITY_MODELING_PROMPT
