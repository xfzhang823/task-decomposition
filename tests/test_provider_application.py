from decimal import Decimal

import pytest

from task_decomposition import (
    DecompositionProvider,
    DecompositionRequest,
    MissingAccountingInputError,
    OperationalDecompositionRequest,
    ProviderContractValidationError,
    ProviderExecutionError,
    ProviderProvenance,
    ProviderSemanticValidationError,
    ProviderStage,
    ProviderStageResponse,
    RetainRemoveClassificationRequest,
    EffortUnit,
    RatioBasis,
    SupportWorkInput,
    TimeBasis,
    decompose,
)
from task_decomposition.errors import ProviderOutputError

from test_staged_pipeline import (
    TASK,
    make_absolute_accounting,
    make_added,
    make_classification,
    make_normalized_accounting,
    make_operational,
)


class FakeProvider:
    provider_id = "fake-provider"

    def __init__(self, *, operational=None, classification=None, added=None):
        self.calls = []
        self.operational = operational or make_operational()
        self.classification = classification or make_classification()
        self.added = added or make_added()

    def _response(self, stage, payload):
        return ProviderStageResponse(
            stage=stage,
            payload=payload,
            provenance=ProviderProvenance(
                provider_id=self.provider_id,
                stage=stage,
                model_id="fake-model",
                request_id="request-1",
            ),
        )

    def generate_operational_decomposition(
        self, request: OperationalDecompositionRequest
    ):
        self.calls.append("operational")
        return self._response(ProviderStage.OPERATIONAL_DECOMPOSITION, self.operational)

    def classify_retain_remove(self, request: RetainRemoveClassificationRequest):
        self.calls.append("classification")
        return self._response(
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION, self.classification
        )

    def classify_added_work(self, request):
        self.calls.append("added")
        return self._response(ProviderStage.ADDED_WORK_CLASSIFICATION, self.added)


def request(*, accounting=True):
    return DecompositionRequest(
        task=TASK,
        transformation_intent="Reduce avoidable manual account-update work.",
        context={"domain": "customer_support"},
        request_id="request-1",
        accounting_input=make_absolute_accounting() if accounting else None,
    )


def test_provider_driven_reference_case_uses_wave1_metrics():
    provider = FakeProvider()
    result = decompose(request(), provider)

    assert isinstance(provider, DecompositionProvider)
    assert provider.calls == ["operational", "classification", "added"]
    assert result.accounting.w0 == Decimal("100")
    assert result.accounting.w1 == Decimal("74")
    assert result.accounting.gross_removed_work_ratio == Decimal("0.4")
    assert result.accounting.added_human_work_ratio == Decimal("0.14")
    assert result.accounting.net_remaining_work_ratio == Decimal("0.74")
    assert result.accounting.net_substitution_ratio == Decimal("0.26")
    assert result.accounting.net_augmentation_multiplier == Decimal(100) / Decimal(74)
    assert len(result.provider_provenance) == 3
    assert result.provider_provenance[0].model_id == "fake-model"


def test_provider_driven_normalized_case_uses_same_staged_semantics():
    provider = FakeProvider(
        classification=make_classification(with_effort=False),
        added=make_added(normalized=True),
    )
    result = decompose(
        request(
            accounting=False,
        ).model_copy(update={"accounting_input": make_normalized_accounting()}),
        provider,
    )
    assert result.accounting.w1 == Decimal("0.74")
    assert result.accounting.net_substitution_ratio == Decimal("0.26")


def test_provider_driven_degradation_remains_unclamped():
    # Replace the three support values while retaining their explicit basis.
    def amount(value):
        return SupportWorkInput(
            value=value,
            basis=RatioBasis.ABSOLUTE_EFFORT,
            unit=EffortUnit.EFFORT,
            time_basis=TimeBasis.PER_OPERATION,
        )

    added = make_added().model_copy(
        update={
            "added_work_rows": tuple(
                row.model_copy(update={"amount": amount(value)})
                for row, value in zip(make_added().added_work_rows, (10, 10, 5))
            )
        }
    )
    accounting = make_absolute_accounting().model_copy(
        update={
            "retained_human_work": make_absolute_accounting().retained_human_work.model_copy(
                update={"value": 100}
            ),
            "gross_removed_work": make_absolute_accounting().gross_removed_work.model_copy(
                update={"value": 0}
            ),
        }
    )
    provider = FakeProvider(
        classification=make_classification(with_effort=False), added=added
    )
    result = decompose(
        request().model_copy(update={"accounting_input": accounting}), provider
    )
    assert result.accounting.w1 == Decimal("125")
    assert result.accounting.net_remaining_work_ratio == Decimal("1.25")
    assert result.accounting.net_substitution_ratio == Decimal("-0.25")
    assert result.accounting.net_augmentation_multiplier == Decimal("0.8")


def test_invalid_operational_output_stops_before_next_stage():
    bad = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(update={"subtask_id": "duplicate"}),
                make_operational()
                .operational_subtasks[1]
                .model_copy(update={"subtask_id": "duplicate"}),
                make_operational().operational_subtasks[2],
            )
        }
    )
    provider = FakeProvider(operational=bad)
    with pytest.raises(ProviderContractValidationError):
        decompose(request(), provider)
    assert provider.calls == ["operational"]


def test_invalid_classification_stops_before_added_stage():
    bad = make_classification().model_copy(
        update={"classified_subtasks": make_classification().classified_subtasks[:-1]}
    )
    provider = FakeProvider(classification=bad)
    with pytest.raises(ProviderContractValidationError):
        decompose(request(), provider)
    assert provider.calls == ["operational", "classification"]


def test_invalid_added_work_stops_before_accounting():
    bad = {
        "task": TASK.model_dump(mode="python"),
        "added_work_rows": [
            {"work_id": "bad", "workload_name": "Bad", "category": "OTHER"}
        ],
    }
    provider = FakeProvider(added=bad)
    with pytest.raises(ProviderContractValidationError):
        decompose(request(), provider)
    assert provider.calls == ["operational", "classification", "added"]


def test_provider_failure_is_wrapped_without_vendor_exception_leak():
    class FailingProvider(FakeProvider):
        def generate_operational_decomposition(self, request):
            self.calls.append("operational")
            raise RuntimeError("vendor timeout")

    provider = FailingProvider()
    with pytest.raises(ProviderExecutionError, match="fake-provider") as error:
        decompose(request(), provider)
    assert isinstance(error.value.__cause__, RuntimeError)
    assert provider.calls == ["operational"]


def test_missing_added_effort_is_explicit_and_not_fabricated():
    added = make_added().model_copy(
        update={
            "added_work_rows": tuple(
                item.model_copy(update={"amount": None})
                for item in make_added().added_work_rows
            )
        }
    )
    provider = FakeProvider(added=added)
    with pytest.raises(MissingAccountingInputError):
        decompose(request(), provider)
    assert provider.calls == ["operational", "classification", "added"]


def test_provider_semantic_failure_is_distinguished():
    bad = make_operational().model_copy(
        update={
            "operational_subtasks": (
                make_operational()
                .operational_subtasks[0]
                .model_copy(update={"subtask_name": "Analyze request intake"}),
                *make_operational().operational_subtasks[1:],
            )
        }
    )
    provider = FakeProvider(operational=bad)
    with pytest.raises(ProviderSemanticValidationError):
        decompose(request(), provider)


def test_wrong_response_stage_and_provenance_are_rejected():
    class WrongStageProvider(FakeProvider):
        def generate_operational_decomposition(self, request):
            self.calls.append("operational")
            return self._response(
                ProviderStage.ADDED_WORK_CLASSIFICATION, self.operational
            )

    with pytest.raises(ProviderOutputError):
        decompose(request(), WrongStageProvider())

    class WrongProvenanceProvider(FakeProvider):
        def generate_operational_decomposition(self, request):
            self.calls.append("operational")
            return ProviderStageResponse(
                stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
                payload=self.operational,
                provenance=ProviderProvenance(
                    provider_id="different-provider",
                    stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
                ),
            )

    with pytest.raises(ProviderOutputError):
        decompose(request(), WrongProvenanceProvider())


def test_missing_request_effort_fails_before_provider_call():
    provider = FakeProvider()
    with pytest.raises(MissingAccountingInputError):
        decompose(request(accounting=False), provider)
    assert provider.calls == []
