from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_provider_application import account_input, request
from test_staged_pipeline import (
    make_activity_effort_estimation,
    make_added,
    make_agentic,
    make_classification,
    make_human_activities,
    make_operational,
)

from task_decomposition import decompose
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider
from task_decomposition.providers.gemini import GeminiDecompositionProvider
from task_decomposition.providers.openai import OpenAIDecompositionProvider


def classification_with_rationales():
    classification = make_classification()
    return classification.model_copy(
        update={
            "classified_subtasks": tuple(
                row.model_copy(update={"rationale": f"Reason for {row.subtask_id}."})
                for row in classification.classified_subtasks
            )
        }
    )


class OpenAIResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(
            output_parsed={
                "SemanticEvaluation": {
                    "decision": "accept",
                    "rubric_version": SEMANTIC_EVALUATION_RUBRIC_VERSION,
                }
            }[kwargs["text_format"].__name__]
        )

    def create(self, **kwargs):
        values = {
            "OperationalDecomposition": make_operational(),
            "RetainRemoveClassification": classification_with_rationales(),
            "AddedWorkClassification": make_added(),
            "AgenticTaskSynthesis": make_agentic(),
            "HumanAgentActivityModel": make_human_activities(),
            "ActivityEffortEstimation": make_activity_effort_estimation(),
        }
        value = values[kwargs["text"]["format"]["name"]]
        return SimpleNamespace(
            status="completed",
            output_text=value.model_dump_json(),
            output=(),
        )


class OpenAIClient:
    responses = OpenAIResponses()


class GeminiModels:
    def generate_content(self, **kwargs):
        return SimpleNamespace(
            parsed={
                "OperationalDecomposition": make_operational(),
                "RetainRemoveClassification": classification_with_rationales(),
                "AddedWorkClassification": make_added(),
                "AgenticTaskSynthesis": make_agentic(),
                "HumanAgentActivityModel": make_human_activities(),
                "ActivityEffortEstimation": make_activity_effort_estimation(),
                "SemanticEvaluation": {
                    "decision": "accept",
                    "rubric_version": SEMANTIC_EVALUATION_RUBRIC_VERSION,
                },
            }[kwargs["config"]["response_json_schema"]["title"]]
        )


class GeminiClient:
    models = GeminiModels()


class DeepSeekCompletions:
    def __init__(self):
        self.outputs = [
            make_operational().model_dump_json(),
            classification_with_rationales().model_dump_json(),
            make_agentic().model_dump_json(),
            make_human_activities().model_dump_json(),
            make_activity_effort_estimation().model_dump_json(),
            make_added().model_dump_json(),
        ]

    def create(self, **kwargs):
        import json

        request_payload = json.loads(
            kwargs["messages"][0]["content"].split("INPUT JSON:\n", 1)[1]
        )
        if "rubric_version" in request_payload:
            content = (
                '{"decision":"accept","rubric_version":"'
                + SEMANTIC_EVALUATION_RUBRIC_VERSION
                + '"}'
            )
        else:
            content = self.outputs.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class DeepSeekClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=DeepSeekCompletions())


@pytest.mark.parametrize(
    "provider",
    [
        lambda: OpenAIDecompositionProvider(client=OpenAIClient()),
        lambda: GeminiDecompositionProvider(client=GeminiClient()),
        lambda: DeepSeekDecompositionProvider(client=DeepSeekClient()),
    ],
    ids=["openai", "gemini", "deepseek"],
)
def test_equivalent_provider_outputs_have_identical_canonical_accounting(provider):
    result = decompose(
        request(),
        provider(),
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    accounting = result.accounting
    assert accounting.w0 == Decimal(100)
    assert accounting.w1 == Decimal(74)
    assert accounting.gross_removed_work_ratio == Decimal("0.40")
    assert accounting.added_human_work_ratio == Decimal("0.14")
    assert accounting.net_remaining_work_ratio == Decimal("0.74")
    assert accounting.net_substitution_ratio == Decimal("0.26")
    assert accounting.net_augmentation_multiplier == Decimal(100) / Decimal(74)
    assert accounting.effect.value == "gain"
    assert [
        row.classification
        for row in result.retain_remove_classification.classified_subtasks
    ] == [row.classification for row in make_classification().classified_subtasks]
    assert [
        row.rationale for row in result.retain_remove_classification.classified_subtasks
    ] == ["Reason for sub-1.", "Reason for sub-2.", "Reason for sub-3."]
