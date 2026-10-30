import importlib
import sys

import pytest


def test_core_imports_are_framework_and_host_neutral():
    before = set(sys.modules)
    importlib.import_module("task_transmorph")
    imported = set(sys.modules) - before
    forbidden_fragments = (
        "AgenticAICompass",
        "bot0",
        "sqlalchemy",
        "fastapi",
        "workflow_compute",
        "scenario",
        "transformation_service",
        "openai",
        "anthropic",
        "litellm",
    )
    assert not any(
        any(fragment.lower() in name.lower() for fragment in forbidden_fragments)
        for name in imported
    )


def test_interfaces_are_canonical_and_old_modules_are_absent():
    interfaces = importlib.import_module("task_transmorph.interfaces")
    assert hasattr(interfaces, "TaskDecompositionProvider")
    assert hasattr(interfaces, "TransformationDecompositionProvider")
    assert hasattr(interfaces, "SemanticEvaluator")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("task_transmorph.ports")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("task_transmorph.evaluation.ports")


def test_public_surface_excludes_internal_staged_handoff_contracts():
    package = importlib.import_module("task_transmorph")
    assert not hasattr(package, "run_staged_pipeline")
    assert not hasattr(package, "StagedDecompositionResult")
    assert hasattr(package, "DecompositionProvider")
