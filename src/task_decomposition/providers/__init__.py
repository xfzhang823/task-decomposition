"""Concrete provider adapters; importing the core does not require SDKs."""

from task_decomposition.providers.deepseek import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DeepSeekDecompositionProvider,
    DeepSeekProviderConfig,
)
from task_decomposition.providers.gemini import (
    DEFAULT_GEMINI_MODEL,
    GeminiDecompositionProvider,
    GeminiProviderConfig,
)
from task_decomposition.providers.openai import (
    DEFAULT_OPENAI_MODEL,
    OpenAIProviderConfig,
    OpenAIDecompositionProvider,
)

__all__ = [
    "DEFAULT_DEEPSEEK_BASE_URL",
    "DEFAULT_DEEPSEEK_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_GEMINI_MODEL",
    "DeepSeekDecompositionProvider",
    "DeepSeekProviderConfig",
    "GeminiDecompositionProvider",
    "GeminiProviderConfig",
    "OpenAIDecompositionProvider",
    "OpenAIProviderConfig",
]
