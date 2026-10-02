import importlib
import sys


def test_core_imports_are_framework_and_host_neutral():
    before = set(sys.modules)
    importlib.import_module("task_decomposition")
    imported = set(sys.modules) - before
    forbidden_fragments = (
        "AgenticAICompass",
        "bot0",
        "sqlalchemy",
        "fastapi",
        "workflow_compute",
        "scenario",
        "transformation_service",
    )
    assert not any(
        any(fragment.lower() in name.lower() for fragment in forbidden_fragments)
        for name in imported
    )
