# Agent Guidance

## Purpose

This repository is a task and transformation decomposition library. It does not own workflow execution, capacity computation, scenarios, simulation, Monte Carlo, grid search, workforce planning, or alternative-scenario management.

## Canonical flow

```text
decompose_task()
      ↓
TaskDecomposition
      ↓
decompose_transformation()
      ↓
TransformationDecompositionResult
```

`decompose()` is convenience composition only.

## Ownership rules

- Task decomposition owns operational subtasks and baseline effort allocation.
- Transformation decomposition owns RETAIN/REMOVE and added/support human work.
- `src/task_decomposition/domain/accounting.py` owns deterministic accounting mathematics.
- Providers propose semantic facts; they do not provide authoritative accounting metrics.
- Transformation decomposition consumes an existing `TaskDecomposition` and must not regenerate it.
- Provider-generated `relative_effort_weight` values are the canonical allocation source.
- Normalize those weights to `W0 = 1.0` by calling the deterministic allocation utility; measured `baseline_effort` is optional and only materializes absolute values.
- Do not add host-weight or allocator alternatives, equal-effort fallbacks, or a separate public allocation stage.

## Accounting semantics

- `baseline_human_effort` is the total original human effort (`W0`), not an additional component to sum.
- Preserve the baseline partition: `W0 = retained_human_work + gross_removed_work`.
- `gross_removed_work` is baseline work classified `REMOVE`; do not include newly introduced support work in it.
- Preserve the post-transformation relationship: `W1 = retained_human_work + resolved_support_work`.
- Gross removal is not net reduction; support work can reduce, eliminate, or exceed the gross reduction.
- Do not invent or duplicate accounting formulas. `src/task_decomposition/domain/accounting.py` is the sole accounting authority.
- Do not mix incompatible units, time bases, ratio denominators, or normalization bases.

See [`docs/reference/ACCOUNTING_MODEL.md`](docs/reference/ACCOUNTING_MODEL.md) for the detailed definitions, provenance, conversions, and edge behavior.

## Forbidden regressions

- Do not reintroduce `transformation_intent` or legacy `DecompositionRequest`.
- Do not duplicate W0/W1 or derived accounting formulas outside the accounting domain.
- Do not add scenario, simulation, Monte Carlo, grid-search, or alternative-management orchestration.
- Do not make core imports eagerly require optional provider SDKs.
- Do not add compatibility shims without concrete caller evidence.
- Do not silently change accounting semantics, support-ratio bases, units, tolerances, or zero-denominator behavior.

## Change guidance

- Contract changes require checking public exports and validation.
- Provider changes must preserve provider parity, untrusted-output validation, and SDK isolation.
- Accounting changes require independent known-answer regression tests.
- Effort changes require allocation-to-accounting handoff tests.
- Public export changes require checking external consumers, especially AgenticAICompass.

## Verification

Run `pytest`, `ruff check src tests`, `ruff format --check src tests`, `python -m compileall -q src`, and `git diff --check`. Keep tests credential-free unless an explicitly opt-in live benchmark is being run.
