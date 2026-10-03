# S2A-4 Legacy Decomposition Removal

## Scope

This wave removed the obsolete standalone decomposition request and compatibility translation path while preserving the approved task-decomposition and transformation-decomposition boundaries.

## Removed legacy concepts

- `DecompositionRequest` was removed from the standalone contracts and public exports.
- `transformation_intent` was removed from standalone and Bot0 runtime request models and metadata.
- `_CompatibilityProvider` and legacy request serialization branches were removed.
- Bot0's `build_standalone_request` adapter was replaced by canonical task and transformation request construction.
- Standalone result projections now use `TransformationDecompositionResult` rather than `StagedDecompositionResult`.

Historical audit documents may still mention these names when describing the architecture that was audited or removed.

## Final public API

The standalone public application surface is:

- `decompose_task(TaskDecompositionRequest, provider)` for task decomposition and reusable operational baselines.
- `decompose_transformation(TransformationDecompositionRequest, provider)` for classification, added work, and deterministic accounting over an existing baseline.
- `decompose(TaskDecompositionRequest, provider, transformation_context=..., accounting_input=...)` as clean convenience composition of the two canonical operations.

The composite `DecompositionProvider` remains because it is the canonical intersection of the task and transformation provider capabilities. Concrete providers implement the capability protocols without legacy request translation.

## AgenticAICompass migration

`app/services/assumption_trail/task_decomposition_adapter.py` now builds `TaskDecompositionRequest` and `TransformationDecompositionRequest` directly and composes `decompose_task()` with `decompose_transformation()`. `run_standalone_decomposition()` returns `TransformationDecompositionResult`. Bot0 row-level effort allocation remains in its adapter wrapper because this wave does not redesign that behavior. The transformation demo now supplies `transformation_context` metadata instead of the removed field.

## Accounting and effort

No accounting formulas changed. `domain/accounting.py` remains the mathematical authority. Task decomposition and transformation decomposition retain their canonical ownership boundary. Bot0's explicit row-level allocation compatibility behavior remains at the consumer adapter seam rather than being represented as a legacy standalone request.

## Verification

- Standalone: `68 passed, 3 skipped`.
- Bot0 focused adapter and generation-cutover tests: `13 passed`.
- Standalone Ruff checks: passed.
- Bot0 touched-file Ruff checks: passed.
- Standalone and Bot0 touched-module compile checks: passed with caches redirected to `/tmp` where required by the sandbox.
- Standalone and Bot0 `git diff --check`: passed.
- Standalone production search found no runtime `transformation_intent`, exact `DecompositionRequest`, `_CompatibilityProvider`, or `build_standalone_request` references. Tests retain the historical term only for explicit absence/rejection assertions.
- No Bot0 imports were added to the standalone package, and no provider SDK dependency was added to the core.

## Remaining compatibility debt

No legacy standalone decomposition compatibility layer remains. Bot0 retains historical downstream export/projection contracts such as Path A `substitution_ratio`, but these are consumer-facing compatibility projections and are outside the removed standalone decomposition path.

## Recommendation

LEGACY PATH REMOVED — READY FOR S2B
