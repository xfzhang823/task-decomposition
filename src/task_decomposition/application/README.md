# Application

Provider-agnostic orchestration. This layer takes a host-supplied provider (something that implements a `ports/` interface), drives the staged flow, treats every provider result as untrusted, and ends in deterministic canonical accounting. No I/O, no vendor SDK, no environment variable, no persistence.

Dependency direction: `application/` → `ports/` (interfaces) and `contracts/` (models); concrete providers live in `providers/`.

## How to read this layer

Two kinds of module sit here:

- **Provider-driven services** call a provider through a port and validate the result — `task_decomposition.py`, `transformation_decomposition.py`, `provider_service.py`.
- **The provider-independent core** validates already-typed stages and delegates all arithmetic to canonical accounting — `staged_pipeline.py`.

`_provider_stage.py` holds the shared helpers for the provider-driven side: the `provider_id` guard, `call_stage`, and the three `validate_*_response` wrappers.

## Entry points

| Function | Module | Input → output | Calls a provider? |
| --- | --- | --- | --- |
| `decompose_task` | `task_decomposition.py` | task + provider → `TaskDecomposition` (operational only, optional baseline effort) | Yes |
| `decompose_transformation` | `transformation_decomposition.py` | existing `TaskDecomposition` + provider → `TransformationDecompositionResult` | Yes |
| `decompose` | `provider_service.py` | canonical task request + transformation context + provider + explicit accounting → `TransformationDecompositionResult` | Yes |
| `run_staged_pipeline` | `staged_pipeline.py` | three typed stages + accounting input → `StagedDecompositionResult` | No |

All four are re-exported from `application/__init__.py`.

## `staged_pipeline.py` — the provider-independent core

The one function here, `run_staged_pipeline`, is a **boundary checker, not a calculator**. It computes no formulas; every W0/W1/gross/net/effect number comes from `domain/accounting`.

Flow:

1. **Validate the chain** — `validate_stage_chain` coerces dicts to typed models and checks the three stages are mutually consistent (IDs, classifications, dependencies).
2. **Cross-check the effort handoff** — `_validate_effort_handoff` requires the explicit accounting input to agree with the classified subtask effort. This is the "must not invent effort" guard.
3. **Resolve support work** — use `support_work_override` if given, else derive it from the added-work rows via `_support_inputs`.
4. **Delegate to canonical accounting** — dispatch on input type to `account_absolute` or `account_normalized`, injecting the resolved support work.
5. **Reassemble** — build `StagedDecompositionResult` and concatenate provenance refs from all three stages.

The four private helpers:

- `_validate_effort_handoff` — the heaviest (~100 of 269 lines). *Absolute*: per-subtask effort is all-present or all-absent; if present, units must match and RETAIN/REMOVE sums must equal `retained_human_work` / `gross_removed_work`. *Normalized*: baseline ratios (or normalized per-row totals) must equal `retained_work_ratio` / `gross_removed_work_ratio`. Any mismatch raises `MissingAccountingInputError`.
- `_support_inputs` — groups added-work rows into the three canonical categories (governance, operational support, lifecycle support); every row must carry an explicit amount/basis.
- `_sum_support_values` — enforces one basis per category (and, for absolute values, one unit and time basis); empty group yields a zero input with a mode-appropriate basis.
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

Flow: check the provider implements `TaskDecompositionProvider` → `call_stage(OPERATIONAL_DECOMPOSITION)` → `validate_operational_response` → bounded semantic repair through the provider's optional `repair_operational_decomposition` hook → `_allocate_baseline`. Every repaired response returns through the same structural and semantic validation.

`_allocate_baseline` decides the baseline effort, in three cases:

- **Allocator given** — requires explicit `baseline_effort`; the allocator must return exactly one allocation per subtask with a positive total. A missing `weight_ratio` is derived as effort / total.
- **Neither weights nor baseline effort** — returns no allocations (operational decomposition only).
- **Weights given** — `effort_weights` must hold exactly one weight per subtask with a positive total; a `baseline_effort` without weights or an allocator is an error.

So baseline effort is optional, and the optional `EffortAllocator` port is the plug for host-supplied allocation.

## `transformation_decomposition.py` — classify and account a reusable decomposition

`decompose_transformation` mirrors `decompose_task`: it takes an existing `TaskDecomposition`, runs the two classification stages, and ends in accounting.

Flow: check the provider implements `TransformationDecompositionProvider` → `classify_retain_remove` → `validate_classification_response` → `_apply_baseline_allocation` → `classify_added_work` → `validate_added_response` → `run_staged_pipeline` (passing the request's own `support_work` as the override) → assemble `TransformationDecompositionResult`.

`_apply_baseline_allocation` injects the baseline effort already carried by the incoming decomposition into each classified subtask, so the provider need not restate it: absolute mode sets `effort`, normalized mode sets `baseline_effort_ratio`. `decompose_task` → `decompose_transformation` is the intended two-call composition.
