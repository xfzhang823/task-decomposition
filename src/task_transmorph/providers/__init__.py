"""Concrete provider adapters; importing the core does not require SDKs."""

from task_transmorph.providers.deepseek import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DeepSeekDecompositionProvider,
    DeepSeekProviderConfig,
)
from task_transmorph.providers.gemini import (
    DEFAULT_GEMINI_MODEL,
    GeminiDecompositionProvider,
    GeminiProviderConfig,
)
from task_transmorph.providers.openai import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_TRANSFORMATION_EVALUATOR_MODEL,
    OpenAIDecompositionProvider,
    OpenAIProviderConfig,
)

__all__ = [
    "DEFAULT_DEEPSEEK_BASE_URL",
    "DEFAULT_DEEPSEEK_MODEL",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_TRANSFORMATION_EVALUATOR_MODEL",
    "DeepSeekDecompositionProvider",
    "DeepSeekProviderConfig",
    "GeminiDecompositionProvider",
    "GeminiProviderConfig",
    "OpenAIDecompositionProvider",
    "OpenAIProviderConfig",
]
