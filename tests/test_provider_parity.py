from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_provider_application import account_input, request
from test_staged_pipeline import make_added, make_classification, make_operational

from task_decomposition import decompose
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider
from task_decomposition.providers.gemini import GeminiDecompositionProvider
from task_decomposition.providers.openai import OpenAIDecompositionProvider


class OpenAIResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(
            output_parsed={
                "OperationalDecomposition": make_operational(),
                "RetainRemoveClassification": make_classification(),
                "AddedWorkClassification": make_added(),
                "SemanticEvaluation": {"decision": "accept", "rubric_version": "1.0"},
            }[kwargs["text_format"].__name__]
        )


class OpenAIClient:
    responses = OpenAIResponses()


class GeminiModels:
    def generate_content(self, **kwargs):
        return SimpleNamespace(
            parsed={
                "OperationalDecomposition": make_operational(),
                "RetainRemoveClassification": make_classification(),
                "AddedWorkClassification": make_added(),
                "SemanticEvaluation": {"decision": "accept", "rubric_version": "1.0"},
            }[kwargs["config"]["response_schema"].__name__]
        )


class GeminiClient:
    models = GeminiModels()


class DeepSeekCompletions:
    def __init__(self):
        self.outputs = [
            make_operational().model_dump_json(),
            make_classification().model_dump_json(),
            make_added().model_dump_json(),
        ]

    def create(self, **kwargs):
        if "semantic evaluation" in kwargs["messages"][0]["content"].lower():
            content = '{"decision":"accept","rubric_version":"1.0"}'
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
