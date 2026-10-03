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
