"""Credential-free metadata validation for the invariant registry."""

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "invariants" / "registry.yaml"
SUPPORTED_VERSION = 1
SUPPORTED_CATEGORIES = {"structural", "computational", "semantic", "boundary"}
SUPPORTED_STATUSES = {"verified", "partial", "proposed"}
INVARIANT_ID = re.compile(r"^(STR|CMP|SEM|BND|PROP)-[0-9]{3}$")
REQUIRED_FIELDS = {
    "id",
    "name",
    "category",
    "domain",
    "description",
    "status",
    "owner",
    "enforcement",
}


def load_registry():
    with REGISTRY_PATH.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_registry_metadata_is_valid():
    registry = load_registry()

    assert registry["version"] == SUPPORTED_VERSION
    records = registry["invariants"]
    assert isinstance(records, list)
    assert records

    ids = []
    for record in records:
        assert REQUIRED_FIELDS <= record.keys()
        assert isinstance(record["id"], str)
        assert INVARIANT_ID.fullmatch(record["id"])
        ids.append(record["id"])
        assert record["name"]
        assert record["category"] in SUPPORTED_CATEGORIES
        assert record["domain"]
        assert record["description"]
        assert record["status"] in SUPPORTED_STATUSES

        owners = record["owner"]
        assert isinstance(owners, list) and owners
        for owner in owners:
            assert_repository_path_exists(owner)

        enforcement = record["enforcement"]
        assert isinstance(enforcement, dict)
        assert {"type", "mechanism", "tests"} <= enforcement.keys()
        assert enforcement["type"]
        assert enforcement["mechanism"]
        assert isinstance(enforcement["tests"], list)
        for test_reference in enforcement["tests"]:
            assert_test_reference_exists(test_reference)

        if record["status"] == "proposed":
            assert record["id"].startswith("PROP-")
            assert enforcement["type"] == "proposed_non_authoritative"
            assert enforcement["tests"] == []
        else:
            assert not record["id"].startswith("PROP-")
            assert enforcement["type"] != "proposed_non_authoritative"

    assert len(ids) == len(set(ids))


def assert_repository_path_exists(relative_path):
    path = Path(relative_path)
    assert not path.is_absolute()
    assert ".." not in path.parts
    assert (ROOT / path).is_file(), relative_path


def assert_test_reference_exists(reference):
    assert isinstance(reference, str) and reference
    relative_path, separator, test_name = reference.partition("::")
    assert_repository_path_exists(relative_path)
    assert Path(relative_path).suffix == ".py"
    if not separator:
        return

    source = (ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative_path)
    test_functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert test_name in test_functions, reference
