import pytest
from test_provider_application import FakeProvider, request
from test_staged_pipeline import TASK, make_operational

from task_decomposition import (
    ProviderContractValidationError,
    ProviderProvenance,
    ProviderSemanticValidationError,
    ProviderStage,
    ProviderStageResponse,
    SemanticAssertionError,
    decompose_task,
    validate_operational_decomposition,
)


def response(provider, payload):
    return ProviderStageResponse(
        stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
        payload=payload,
        provenance=ProviderProvenance(
            provider_id=provider.provider_id,
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            model_id="repair-test",
            request_id="request-1",
            references=(),
        ),
    )


def invalid_operational(*names):
    operational = make_operational()
    subtasks = tuple(
        item.model_copy(update={"subtask_name": name, "description": None})
        for item, name in zip(operational.operational_subtasks, names)
    )
    return operational.model_copy(update={"operational_subtasks": subtasks})


class RepairProvider(FakeProvider):
    def __init__(self, repairs):
        super().__init__(
            operational=invalid_operational(
                "Make approval decision", "Invoice approved", "Complete review"
            )
        )
        self.repairs = list(repairs)
        self.repair_calls = []

    def repair_operational_decomposition(
        self, request, *, rejected_response, validation_errors
    ):
        self.repair_calls.append((rejected_response, tuple(validation_errors)))
        return response(self, self.repairs.pop(0))


def test_valid_initial_decomposition_does_not_repair():
    provider = FakeProvider()
    result = decompose_task(request(), provider)
    assert result.operational_decomposition == provider.operational
    assert not hasattr(provider, "repair_operational_decomposition")


def test_semantic_failure_is_repaired_and_revalidated():
    repaired = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(
                    update={
                        "subtask_name": "Determine whether the invoice meets approval criteria"
                    }
                ),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    provider = RepairProvider([repaired])
    result = decompose_task(request(), provider)
    assert result.operational_decomposition.operational_subtasks[
        0
    ].subtask_name.startswith("Determine")
    assert len(provider.repair_calls) == 1
    assert "sub-1" in provider.repair_calls[0][1][0]


def test_specific_decision_work_is_valid_but_outcome_is_not():
    valid = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(
                    update={
                        "subtask_name": "Determine whether the invoice meets approval criteria"
                    }
                ),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    validate_operational_decomposition(valid)
    with pytest.raises(SemanticAssertionError):
        validate_operational_decomposition(
            make_operational().model_copy(
                update={
                    "operational_subtasks": (
                        make_operational()
                        .operational_subtasks[0]
                        .model_copy(
                            update={
                                "subtask_name": "Invoice approved",
                                "description": None,
                            }
                        ),
                        *make_operational().operational_subtasks[1:],
                    )
                }
            )
        )


def test_multiple_semantic_failures_are_reported_and_repair_is_bounded():
    provider = RepairProvider(
        [
            invalid_operational(
                "Make approval decision", "Invoice approved", "Complete review"
            ),
            invalid_operational(
                "Make approval decision", "Invoice approved", "Complete review"
            ),
        ]
    )
    with pytest.raises(ProviderSemanticValidationError) as error:
        decompose_task(request(), provider)
    assert error.value.repair_attempts == 2
    assert error.value.rejected_response is not None
    assert error.value.final_response is not None
    assert len(provider.repair_calls) == 2
    assert "sub-1" in str(error.value)
    assert "sub-2" in str(error.value)
    assert "sub-3" in str(error.value)


def test_malformed_repair_cannot_bypass_structural_validation():
    malformed = {
        "task": TASK.model_dump(mode="python"),
        "operational_subtasks": [
            {
                "sequence_index": 1,
                "subtask_id": "duplicate",
                "subtask_name": "Review invoice",
            },
            {
                "sequence_index": 2,
                "subtask_id": "duplicate",
                "subtask_name": "Record invoice decision",
            },
        ],
    }
    provider = RepairProvider([malformed])
    with pytest.raises(ProviderContractValidationError):
        decompose_task(request(), provider)
