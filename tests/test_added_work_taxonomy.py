"""Focused contract tests for the execution-level added-work taxonomy."""

import pytest
from pydantic import ValidationError

from task_decomposition import (
    EffortUnit,
    SupportWorkInput,
    SupportWorkInputs,
    TimeBasis,
    AddedWorkCategory,
    AddedWorkClassification,
    AddedWorkItem,
    OperationalDecomposition,
    OperationalSubtask,
    RetainRemoveClassification,
    TaskReference,
    TransformationClassification,
    validate_added_work_classification,
)
from task_decomposition.contracts.provenance import ProviderStage
from task_decomposition.providers.openai import _provider_text_format
from task_decomposition.providers.prompts import ADDED_WORK_PROMPT

TASK = TaskReference(
    task_id="taxonomy-task",
    task_name="Process request",
    task_description="Process a request with AI assistance.",
)
OPERATIONAL = OperationalDecomposition(
    task=TASK,
    operational_subtasks=(
        OperationalSubtask(
            sequence_index=1,
            subtask_id="baseline-1",
            subtask_name="Review request",
        ),
    ),
)
CLASSIFICATION = RetainRemoveClassification(
    task=TASK,
    classified_subtasks=(
        {
            "subtask_id": "baseline-1",
            "classification": TransformationClassification.RETAIN,
        },
    ),
)


@pytest.mark.parametrize(
    "category",
    [AddedWorkCategory.AI_INTERACTION, AddedWorkCategory.AI_VERIFICATION],
)
def test_added_work_accepts_both_execution_level_categories(category):
    row = AddedWorkItem(
        work_id="new-human-1",
        workload_name="New AI activity",
        category=category,
    )
    assert row.category is category


@pytest.mark.parametrize(
    "category", ["GOVERNANCE", "OPERATIONAL_SUPPORT", "LIFECYCLE_SUPPORT"]
)
def test_added_work_rejects_obsolete_categories(category):
    with pytest.raises(ValidationError):
        AddedWorkItem(
            work_id="obsolete-1",
            workload_name="Obsolete category",
            category=category,
        )


def test_added_work_allows_empty_result_and_requires_complete_root_fields():
    output = AddedWorkClassification(
        task=TASK,
        added_work_rows=(),
        provenance_refs=(),
    )
    assert output.added_work_rows == ()
    assert set(output.model_dump()) == {"task", "added_work_rows", "provenance_refs"}
    assert (
        validate_added_work_classification(OPERATIONAL, CLASSIFICATION, output)
        == output
    )

    dumped = output.model_dump(mode="json")
    assert set(dumped) == {"task", "added_work_rows", "provenance_refs"}
    assert dumped["provenance_refs"] == []


def test_added_work_provider_schema_requires_complete_root_fields():
    schema = _provider_text_format(
        ProviderStage.ADDED_WORK_CLASSIFICATION,
        AddedWorkClassification,
    )["schema"]
    assert schema["required"] == ["task", "added_work_rows", "provenance_refs"]


def test_accounting_contract_uses_only_canonical_execution_categories():
    assert set(SupportWorkInputs.model_fields) == {"ai_interaction", "ai_verification"}
    quantity = SupportWorkInput(
        value=0,
        basis="absolute_effort",
        unit=EffortUnit.EFFORT,
        time_basis=TimeBasis.PER_OPERATION,
    )
    with pytest.raises(ValidationError):
        SupportWorkInputs(
            governance=quantity,
            operational_support=quantity,
            lifecycle_support=quantity,
        )


def test_added_work_is_separate_from_baseline_retain_remove_rows():
    added = AddedWorkClassification(
        task=TASK,
        added_work_rows=(
            AddedWorkItem(
                work_id="new-ai-check",
                workload_name="Verify AI-generated response",
                category=AddedWorkCategory.AI_VERIFICATION,
            ),
        ),
        provenance_refs=(),
    )
    assert CLASSIFICATION.classified_subtasks[0].subtask_id == "baseline-1"
    assert (
        added.added_work_rows[0].work_id
        != CLASSIFICATION.classified_subtasks[0].subtask_id
    )
    assert added.added_work_rows[0].category is AddedWorkCategory.AI_VERIFICATION


def test_prompt_defines_interaction_verification_and_exclusions():
    assert "AI_INTERACTION" in ADDED_WORK_PROMPT
    assert "AI_VERIFICATION" in ADDED_WORK_PROMPT
    assert "retrying" in ADDED_WORK_PROMPT
    assert "approving AI-generated outputs" in ADDED_WORK_PROMPT
    assert "implementation" in ADDED_WORK_PROMPT
    assert "ongoing system maintenance" in ADDED_WORK_PROMPT
    assert "passive AI waiting time" in ADDED_WORK_PROMPT
    assert (
        "top-level `task`, `added_work_rows`, and `provenance_refs`"
        in ADDED_WORK_PROMPT
    )
    assert "Return only added-work rows in a JSON object" not in ADDED_WORK_PROMPT
