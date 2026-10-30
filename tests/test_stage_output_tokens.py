import pytest

from task_transmorph.contracts.provenance import ProviderStage
from task_transmorph.providers._semantic import SEMANTIC_EVALUATION_STAGE
from task_transmorph.providers.deepseek import DeepSeekProviderConfig
from task_transmorph.providers.gemini import GeminiProviderConfig
from task_transmorph.providers.openai import OpenAIProviderConfig

CONFIGS = (OpenAIProviderConfig, GeminiProviderConfig, DeepSeekProviderConfig)

# DeepSeek Flash spends output tokens on hidden reasoning before emitting JSON.
DEFAULT_OUTPUT_TOKENS = {
    OpenAIProviderConfig: 2000,
    GeminiProviderConfig: 2000,
    DeepSeekProviderConfig: 16000,
}


STAGES = (
    ProviderStage.OPERATIONAL_DECOMPOSITION.value,
    "semantic_evaluation",
    ProviderStage.RETAIN_REMOVE_CLASSIFICATION.value,
)


@pytest.mark.parametrize("config_type", CONFIGS)
def test_stage_token_overrides_and_global_fallback(config_type):
    config = config_type(
        stage_output_tokens={stage: index + 101 for index, stage in enumerate(STAGES)}
    )
    assert [config.output_tokens_for(stage) for stage in STAGES] == [101, 102, 103]
    assert config.output_tokens_for("unknown") == DEFAULT_OUTPUT_TOKENS[config_type]


@pytest.mark.parametrize("config_type", CONFIGS)
def test_stage_token_overrides_accept_provider_stage_enum(config_type):
    config = config_type(
        stage_output_tokens={ProviderStage.RETAIN_REMOVE_CLASSIFICATION: 321}
    )
    assert (
        config.output_tokens_for(ProviderStage.RETAIN_REMOVE_CLASSIFICATION.value)
        == 321
    )
    assert (
        config.output_tokens_for(SEMANTIC_EVALUATION_STAGE)
        == DEFAULT_OUTPUT_TOKENS[config_type]
    )


@pytest.mark.parametrize("config_type", CONFIGS)
@pytest.mark.parametrize(
    "values",
    [
        {"unknown_stage": 100},
        {"semantic_evaluation": 0},
        {"semantic_evaluation": -1},
        {"semantic_evaluation": 1.5},
        {"semantic_evaluation": True},
        [("semantic_evaluation", 100)],
    ],
)
def test_invalid_stage_token_configuration_is_rejected(config_type, values):
    with pytest.raises((TypeError, ValueError)):
        config_type(stage_output_tokens=values)
