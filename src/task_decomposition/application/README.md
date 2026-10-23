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
| `estimate_transformation` | `normalized_estimation.py` | existing `TaskDecomposition` + provider → normalized `TransformationDecompositionResult` | Yes |
| `decompose` | `provider_service.py` | canonical task request + transformation context + provider + explicit accounting → `TransformationDecompositionResult` | Yes |
The staged handoff is internal to transformation decomposition and normalized estimation.

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

Flow: resolve a built-in provider name through the provider factory (or preserve an already-constructed provider object) → check the provider implements `TaskDecompositionProvider` → `call_stage(OPERATIONAL_DECOMPOSITION)` → deterministic structural validation → `SemanticEvaluator` evaluation → bounded targeted repair through the provider's optional `repair_operational_decomposition` hook → structural revalidation and complete-decomposition re-evaluation → deterministic normalization of provider weights in `_allocate_baseline`. Only an accepted decomposition reaches allocation; evaluator capability is provider-default or explicit via `decompose_task(..., evaluator=...)`.

`_allocate_baseline` uses provider-generated positive
`relative_effort_weight` values as the sole allocation source. The
deterministic `allocate_effort` utility normalizes those weights against a
synthetic `W0 = 1.0` parent, producing `BaselineEffortAllocation.weight_ratio`
values. When measured `baseline_effort` is present, the same utility derives
compatible absolute values. Baseline effort is optional; no user-supplied
hours or alternate host-weight pathway is required.

These weights are ratio estimates of aggregate baseline human working-time
shares; their absolute numeric scale is not meaningful because normalization
removes it. The current application validates positivity and allocation
invariants, but it does not validate the provider's estimation assumptions or
effort plausibility. See the [decomposition model reference](../../../docs/reference/DECOMPOSITION_MODEL.md)
and [baseline effort weighting audit](../../../docs/audits/baseline-effort-weighting.md)
for the semantic boundary and evidence.

## `transformation_decomposition.py` — classify and account a reusable decomposition

`decompose_transformation` mirrors `decompose_task`: it takes an existing `TaskDecomposition`, resolves a provider name when requested, runs the two classification stages, and ends in accounting. Both application APIs accept an optional per-call `model`; provider objects are never mutated.

`estimate_transformation` is an opt-in bridge for exploratory or notebook runs without host-supplied ratios. It uses the completed task allocation and provider RETAIN/REMOVE labels to construct a normalized 100-unit accounting input, records per-subtask estimate assumptions and rationales, and reuses the same support-work and deterministic accounting handoff. It does not change the strict explicit-input contract of `decompose_transformation`.

Flow: check the provider implements `TransformationDecompositionProvider` → `classify_retain_remove` → `validate_classification_response` → `_apply_baseline_allocation` → `classify_added_work` → strict `validate_added_response` → resolve support work → internal `_run_staged_pipeline` (passing concrete resolved support) → assemble `TransformationDecompositionResult`.

`_apply_baseline_allocation` injects the baseline effort already carried by the incoming decomposition into each classified subtask, so the provider need not restate it: absolute mode sets `effort`, normalized mode sets `baseline_effort_ratio`. `decompose_task` → `decompose_transformation` is the intended two-call composition.
