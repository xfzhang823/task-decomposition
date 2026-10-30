"""Construction and per-call resolution of built-in decomposition providers."""

# Provider SDKs are imported lazily so core imports do not require optional extras.
# pylint: disable=import-outside-toplevel

from task_transmorph.errors import ProviderOutputError


def create_provider(
    provider_name: str,
    model: str | None = None,
    *,
    max_output_tokens: int | None = None,
):
    """Construct a built-in provider with optional per-call execution settings.

    Args:
        provider_name: Built-in provider name: ``openai``, ``gemini``, or
            ``deepseek``.
        model: Optional model override for the selected provider.
        max_output_tokens: Optional output-token cap for every stage.

    Returns:
        A configured decomposition provider implementing the provider port.

    Raises:
        ProviderOutputError: If ``provider_name`` is empty or unsupported.
    """
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise ProviderOutputError("provider name must be a non-empty string")

    name = provider_name.strip().lower()
    if name == "openai":
        from task_transmorph.providers.openai import (
            OpenAIDecompositionProvider,
            OpenAIProviderConfig,
        )

        config_kwargs = {}
        if model is not None:
            config_kwargs["model"] = model
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        config = OpenAIProviderConfig(**config_kwargs)
        return OpenAIDecompositionProvider(config)
    if name == "gemini":
        from task_transmorph.providers.gemini import (
            GeminiDecompositionProvider,
            GeminiProviderConfig,
        )

        config_kwargs = {}
        if model is not None:
            config_kwargs["model"] = model
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        config = GeminiProviderConfig(**config_kwargs)
        return GeminiDecompositionProvider(config)
    if name == "deepseek":
        from task_transmorph.providers.deepseek import (
            DeepSeekDecompositionProvider,
            DeepSeekProviderConfig,
        )

        config_kwargs = {}
        if model is not None:
            config_kwargs["model"] = model
        if max_output_tokens is not None:
            config_kwargs["max_tokens"] = max_output_tokens
        config = DeepSeekProviderConfig(**config_kwargs)
        return DeepSeekDecompositionProvider(config)

    raise ProviderOutputError(
        f"unknown provider {provider_name!r}; expected 'openai', 'gemini', or 'deepseek'"
    )


def resolve_provider(
    provider, model: str | None = None, *, max_output_tokens: int | None = None
):
    """Resolve a provider name or validate an existing provider object.

    Args:
        provider: Built-in provider name or an already-constructed provider.
        model: Optional model override; valid only with a provider name.
        max_output_tokens: Optional output-token cap; valid only with a name.

    Returns:
        A provider instance suitable for the application entry points.

    Raises:
        ProviderOutputError: If overrides accompany an existing provider object.
    """
    if isinstance(provider, str):
        return create_provider(
            provider, model=model, max_output_tokens=max_output_tokens
        )
    if model is not None or max_output_tokens is not None:
        raise ProviderOutputError(
            "model override requires a provider name; output-token overrides also "
            "require a provider name and cannot be used with "
            "an already-constructed provider object"
        )
    return provider


__all__ = ["create_provider", "resolve_provider"]
