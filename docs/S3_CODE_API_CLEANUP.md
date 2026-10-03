# S3 Code and API Cleanup

## Files changed

- `main.py` was deleted as an unreferenced hello-world scaffold.
- `src/task_decomposition/ports/benchmark.py` was deleted.
- `src/task_decomposition/ports/__init__.py` and `src/task_decomposition/__init__.py` no longer export benchmark symbols.
- `pyproject.toml` and `uv.lock` no longer declare unused Black, Pylint, or Pylance tooling.
- `src/task_decomposition/ports/README.md` no longer documents the deleted benchmark port.
- `README.md` no longer advertises the deleted benchmark abstraction.
- This report was added.

## Deleted and internalized symbols

`BenchmarkProvider`, `BenchmarkQuery`, and `BenchmarkReference` were deleted after repository-wide caller evidence showed no implementation, test, or external AgenticAICompass import. They were only self-exported and represented a speculative future extension.

The tracked top-level `main.py` hello-world function had no package entry-point declaration, imports, tests, or documentation usage. It was deleted as extraction residue. The unrelated untracked `tree.py` was preserved.

No other production symbol was deleted. `DecompositionRequest` and `transformation_intent` had already been removed in S2A-4.

## Public API

The primary root API remains `decompose_task()`, `decompose_transformation()`, and `decompose()`. `BenchmarkProvider`, `BenchmarkQuery`, and `BenchmarkReference` are no longer public because no caller evidence justified them.

The low-level `account_absolute()`, `account_normalized()`, `classify_effect()`, `allocate_effort()`, and `aggregate_baseline_rows()` exports remain because they are deterministic domain operations with active application or test callers. `run_staged_pipeline()` and `StagedDecompositionResult` remain because `decompose_transformation()` uses the staged handoff internally and the provider-independent staged pipeline has direct tests and a legitimate deterministic library use case.

## Ports disposition

- `provider.py`: `KEEP`; required provider boundary with separate task and transformation capabilities plus the composite protocol.
- `effort_allocator.py`: `KEEP`; `decompose_task()` accepts and invokes `EffortAllocator`, and its contracts represent a real replaceable host dependency.
- `benchmark.py`: `DELETE`; no callers, implementation, or tests existed.

## Validation and ownership review

No duplicate validation layer was removed. Contract validators enforce local value invariants, `validation/` enforces cross-stage identity/cardinality/dependency and semantic rules, and `application/_provider_stage.py` converts untrusted provider failures into standalone errors before stage advancement. Domain accounting remains in `domain/accounting.py`; application code only prepares inputs and composes stages.

## Provider and contract review

OpenAI, Gemini, DeepSeek, `_shared.py`, and prompts have active stage callers and shared provider-boundary responsibilities. No obsolete provider adapter or duplicated transport helper had sufficient evidence for removal. Canonical task, transformation, accounting, effort, provenance, and stage contracts remain in use by the application, providers, tests, or AgenticAICompass.

## Tooling cleanup

Ruff is the configured and exercised linter/formatter. Black had no configuration or repository invocation, so it was removed as redundant. Pylint and Pylance likewise had no repository configuration or invocation and were removed from the development dependency group. `pytest` and `ruff` remain as the active development tools.

## LOC

Standalone production Python under `src/task_decomposition/` decreased from 3,077 lines before this cleanup to 3,044 lines after it, a reduction of 33 lines from the deleted benchmark port. The deleted top-level `main.py` contained 6 additional scaffold lines outside the package.

## Verification

- `pytest -q`: `68 passed, 3 skipped`.
- `ruff check src tests`: passed.
- `ruff format --check src tests`: passed.
- `python -m compileall -q src`: passed using a temporary bytecode cache.
- Public import smoke test: passed.
- Provider import isolation and framework import-boundary tests: passed as part of the suite.
- No Bot0/workflow/provider-forbidden imports were introduced.
- No legacy decomposition symbols were reintroduced.
- `uv lock --check`: passed.
- `uv sync --dev --offline`: passed.
- `git diff --check`: passed.

## Intentionally retained questionable-looking code

`EffortAllocator` is not dead: `application/task_decomposition.py` invokes it when a host supplies an allocator. `run_staged_pipeline()` and `StagedDecompositionResult` are not compatibility shims: transformation decomposition uses the handoff and its direct deterministic behavior is covered by tests. `TransformationRow` and `aggregate_baseline_rows()` remain because the accounting utility is exercised directly and Bot0 consumes the row contract. The broad root exports for canonical contracts, errors, validators, and deterministic functions remain to avoid breaking supported library and consumer imports without evidence of a safe migration.

## Remaining cleanup debt

No S3 cleanup blocker remains. The root export surface is broader than the three primary application functions, but each retained symbol has active internal, test, or AgenticAICompass evidence. Further API narrowing would require an explicit public-contract decision rather than dead-code cleanup.

CODE/API CLEAN — PROCEED TO S4A
