import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "openai_decompose_example",
    Path(__file__).parents[1] / "examples" / "openai_decompose.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)
_parse_args = _MODULE._parse_args


def test_production_scheduling_example_uses_domain_neutral_context(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "openai_decompose.py",
            "--task-name",
            "Production Scheduling",
            "--task-description",
            "Review production orders and develop a feasible schedule.",
        ],
    )

    args = _parse_args()

    assert args.domain == "production_scheduling"
