import importlib

import pytest
from test_provider_application import FakeProvider, account_input, request

from task_decomposition import (
    ProviderOutputError,
    TransformationDecompositionRequest,
    decompose_task,
    decompose_transformation,
)
from task_decomposition.application.provider_factory import create_provider
from task_decomposition.providers.deepseek import (
    DEFAULT_DEEPSEEK_MODEL,
    DeepSeekProviderConfig,
)
from task_decomposition.providers.gemini import (
    DEFAULT_GEMINI_MODEL,
    GeminiProviderConfig,
)
from task_decomposition.providers.openai import (
    DEFAULT_OPENAI_MODEL,
    OpenAIProviderConfig,
)


@pytest.mark.parametrize(
    ("provider_name", "module_name", "class_name", "config_type"),
    [
        (
            "openai",
            "task_decomposition.providers.openai",
            "OpenAIDecompositionProvider",
            OpenAIProviderConfig,
        ),
        (
            "gemini",
            "task_decomposition.providers.gemini",
            "GeminiDecompositionProvider",
            GeminiProviderConfig,
        ),
        (
            "deepseek",
            "task_decomposition.providers.deepseek",
            "DeepSeekDecompositionProvider",
            DeepSeekProviderConfig,
        ),
    ],
)
def test_factory_forwards_explicit_model_without_constructing_an_sdk_client(
    monkeypatch, provider_name, module_name, class_name, config_type
):
    module = importlib.import_module(module_name)
    captured = {}

    class FakeConstructedProvider:
        provider_id = provider_name

    def constructor(config):
        captured["config"] = config
        return FakeConstructedProvider()

    monkeypatch.setattr(module, class_name, constructor)
    provider = create_provider(provider_name, model="premium-test-model")

    assert isinstance(provider, FakeConstructedProvider)
    assert isinstance(captured["config"], config_type)
    assert captured["config"].model == "premium-test-model"


@pytest.mark.parametrize(
    ("config_type", "default_model"),
    [
        (OpenAIProviderConfig, DEFAULT_OPENAI_MODEL),
        (GeminiProviderConfig, DEFAULT_GEMINI_MODEL),
        (DeepSeekProviderConfig, DEFAULT_DEEPSEEK_MODEL),
    ],
)
def test_provider_configs_preserve_existing_defaults(config_type, default_model):
    assert config_type().model == default_model


def test_factory_omitted_model_uses_provider_default(monkeypatch):
    module = importlib.import_module("task_decomposition.providers.openai")
    captured = {}

    def constructor(config):
        captured["config"] = config
        return object()

    monkeypatch.setattr(module, "OpenAIDecompositionProvider", constructor)
    create_provider("openai")

    assert captured["config"].model == DEFAULT_OPENAI_MODEL


def test_public_task_api_accepts_provider_name_and_model(monkeypatch):
    task_module = importlib.import_module(
        "task_decomposition.application.task_decomposition"
    )
    captured = {}

    def resolve(provider, *, model, max_output_tokens):
        captured.update(
            provider=provider, model=model, max_output_tokens=max_output_tokens
        )
        return FakeProvider()

    monkeypatch.setattr(task_module, "resolve_provider", resolve)
    decompose_task(request(), provider="openai", model="premium-test-model")

    assert captured == {
        "provider": "openai",
        "model": "premium-test-model",
        "max_output_tokens": None,
    }


def test_existing_provider_object_call_remains_supported():
    provider = FakeProvider()
    decompose_task(request(), provider)
    assert provider.calls == ["operational"]


def test_provider_object_and_model_override_raise_clear_error():
    with pytest.raises(
        ProviderOutputError,
        match="model override requires a provider name",
    ):
        decompose_task(request(), FakeProvider(), model="premium-test-model")


def test_public_transformation_api_accepts_provider_name_and_model(monkeypatch):
    task_provider = FakeProvider()
    baseline = decompose_task(request(), task_provider)
    transformation_module = importlib.import_module(
        "task_decomposition.application.transformation_decomposition"
    )
    captured = {}

    def resolve(provider, *, model, max_output_tokens):
        captured.update(
            provider=provider, model=model, max_output_tokens=max_output_tokens
        )
        return task_provider

    monkeypatch.setattr(transformation_module, "resolve_provider", resolve)
    transformation_request = TransformationDecompositionRequest(
        task_decomposition=baseline,
        accounting_input=account_input(),
    )
    decompose_transformation(
        transformation_request,
        provider="openai",
        model="premium-test-model",
    )

    assert captured == {
        "provider": "openai",
        "model": "premium-test-model",
        "max_output_tokens": None,
    }
