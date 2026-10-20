# Application

Provider-agnostic orchestration. This layer takes a host-supplied provider (something that implements an `interfaces/` protocol), drives the staged flow, treats every provider result as untrusted, and ends in deterministic canonical accounting. No I/O, no vendor SDK, no environment variable, no persistence.

Dependency direction: `application/` → `interfaces/` (behavioral protocols) and `contracts/` (data schemas); concrete providers live in `providers/`.

## How to read this layer

Two kinds of module sit here:

- **Provider-driven services** call a provider through an interface and validate the result — `task_decomposition.py`, `transformation_decomposition.py`, `provider_service.py`.
- **The provider-independent accounting handoff** validates already-typed stages and delegates all arithmetic to canonical accounting — internal `staged_pipeline.py`.

`_provider_stage.py` holds the shared helpers for the provider-driven side: the `provider_id` guard, `call_stage`, and the three `validate_*_response` wrappers.

## Entry points

| Function | Module | Input → output | Calls a provider? |
| --- | --- | --- | --- |
| `decompose_task` | `task_decomposition.py` | task + provider → `TaskDecomposition` (operational only, optional baseline effort) | Yes |
| `decompose_transformation` | `transformation_decomposition.py` | existing `TaskDecomposition` + provider → `TransformationDecompositionResult` | Yes |
| `decompose` | `provider_service.py` | canonical task request + transformation context + provider + explicit accounting → `TransformationDecompositionResult` | Yes |
Only the three decomposition functions are application entry points. The staged handoff is internal to transformation decomposition.

## `staged_pipeline.py` — the provider-independent core

The internal `_run_staged_pipeline` function is a **boundary checker, not a calculator**. It computes no formulas; every W0/W1/gross/net/effect number comes from `domain/accounting` and it returns the canonical accounting impact directly.

Flow:

1. **Validate the chain** — `validate_stage_chain` coerces dicts to typed models and checks the three stages are mutually consistent (IDs, classifications, dependencies).
2. **Cross-check the effort handoff** — `_validate_effort_handoff` requires the explicit accounting input to agree with the classified subtask effort. This is the "must not invent effort" guard.
3. **Receive resolved support work** — `added_work_estimation.resolve_support_work` selects host or estimate support inputs before the staged handoff.
4. **Delegate to canonical accounting** — dispatch on input type to `account_absolute` or `account_normalized`, injecting the resolved support work.
5. **Return accounting** — transformation orchestration assembles the public `TransformationDecompositionResult` from the validated stage values and accounting impact.

The four private helpers:

- `_validate_effort_handoff` — the heaviest (~100 of 269 lines). *Absolute*: per-subtask effort is all-present or all-absent; if present, units must match and RETAIN/REMOVE sums must equal `retained_human_work` / `gross_removed_work`. *Normalized*: baseline ratios (or normalized per-row totals) must equal `retained_work_ratio` / `gross_removed_work_ratio`. Any mismatch raises `MissingAccountingInputError`.
- `_require_matching_units` — all classified efforts must share one unit and time basis.

Load-bearing invariants:

- **Explicit effort only** — `accounting_input` is required; the pipeline never infers effort from missing provider data.
- **No silent coercion** — mixed present/absent effort is an error, not a default; mixed bases/units raise `SupportBasisConflictError` / `IncompatibleEffortUnitError`.
- **Pure and host-neutral** — deterministic given inputs.
- **Single source of truth for formulas** — this file only validates and routes.

## Note

`provider_service.py` (`decompose`) reimplements its own `_provider_id` / `_call_stage` / `_validate_*` helpers instead of importing the equivalents from `_provider_stage.py`, which the other two provider-driven services do use. Behaviour is the same; the duplication is the one wrinkle in this layer.

## `task_decomposition.py` — build a reusable decomposition

`decompose_task` runs only the first stage: a provider proposes operational subtasks, with no transformation context and no accounting. The result (`TaskDecomposition`) is the reusable input the transformation path consumes.

Flow: check the provider implements `TaskDecompositionProvider` → `call_stage(OPERATIONAL_DECOMPOSITION)` → deterministic structural validation → `SemanticEvaluator` evaluation → bounded targeted repair through the provider's optional `repair_operational_decomposition` hook → structural revalidation and complete-decomposition re-evaluation → `_allocate_baseline`. Only an accepted decomposition reaches allocation; evaluator capability is provider-default or explicit via `decompose_task(..., evaluator=...)`.

`_allocate_baseline` decides the baseline effort, in three cases:

- **Allocator given** — requires explicit `baseline_effort`; the allocator must return exactly one allocation per subtask with a positive total. A missing `weight_ratio` is derived as effort / total.
- **Neither weights nor baseline effort and no provider estimates** — returns no allocations (operational decomposition only).
- **Weights given** — `effort_weights` must hold exactly one weight per subtask with a positive total; a `baseline_effort` without weights or an allocator is an error.

Built-in provider outputs may also include positive, unnormalized
`relative_effort_weight` values on each operational subtask. When host weights
and an allocator are absent, the application normalizes those provider
estimates into `BaselineEffortAllocation.weight_ratio` values that sum to one;
supplied baseline effort is distributed using the same ratios. These rows are
marked with `allocation_source="estimated"`, while host-supplied allocations
remain marked `allocation_source="host"`.

So baseline effort is optional, and the optional `EffortAllocator` interface is the plug for host-supplied allocation.

## `transformation_decomposition.py` — classify and account a reusable decomposition

`decompose_transformation` mirrors `decompose_task`: it takes an existing `TaskDecomposition`, runs the two classification stages, and ends in accounting.

Flow: check the provider implements `TransformationDecompositionProvider` → `classify_retain_remove` → `validate_classification_response` → `_apply_baseline_allocation` → `classify_added_work` → strict `validate_added_response` → resolve support work → internal `_run_staged_pipeline` (passing concrete resolved support) → assemble `TransformationDecompositionResult`.

`_apply_baseline_allocation` injects the baseline effort already carried by the incoming decomposition into each classified subtask, so the provider need not restate it: absolute mode sets `effort`, normalized mode sets `baseline_effort_ratio`. `decompose_task` → `decompose_transformation` is the intended two-call composition.
