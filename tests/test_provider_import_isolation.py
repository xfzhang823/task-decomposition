import importlib
import sys


def test_core_import_does_not_import_any_concrete_provider_sdk():
    before = set(sys.modules)
    importlib.import_module("task_decomposition")
    imported = set(sys.modules) - before
    forbidden = ("openai", "google.genai", "anthropic")
    assert not any(
        any(fragment in name.lower() for fragment in forbidden) for name in imported
    )
