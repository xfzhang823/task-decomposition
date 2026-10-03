# S2A-3 Boundary Restoration Verification

**Repository:** `/home/xzhang/dev/task_decomposition`
**Scope:** independent verification of S2A-2
**Reference:** `/home/xzhang/dev/AgenticAICompass` was not modified.

## Verified call graph

The implemented canonical path is:

```text
decompose_task(TaskDecompositionRequest, TaskDecompositionProvider)
  ├─ generate_operational_decomposition()
  ├─ validate_operational_response()
  ├─ establish explicit baseline allocations when supplied
  └─ return TaskDecomposition

decompose_transformation(TransformationDecompositionRequest, provider)
  ├─ consume request.task_decomposition
  ├─ classify_retain_remove()
  ├─ validate classification
  ├─ apply frozen baseline allocations
  ├─ classify_added_work()
  ├─ validate added work
  ├─ run_staged_pipeline()
  │    └─ domain.accounting.account_absolute() or account_normalized()
  └─ return TransformationDecompositionResult

decompose(legacy DecompositionRequest, composite provider)
  └─ compatibility adapter
       ├─ decompose_task(...)
       └─ decompose_transformation(...)
```

Concrete evidence is in `application/task_decomposition.py:27-60`, `application/transformation_decomposition.py:25-84`, and `application/provider_service.py:23-67`.

## Task-decomposition verification

`decompose_task()` is independently callable and requires only `TaskDecompositionRequest` plus a `TaskDecompositionProvider`. It generates one operational stage, validates it through `_provider_stage.py`, and performs no RETAIN/REMOVE classification, added-work classification, or accounting call.

`TaskDecompositionRequest` has `task_context`, optional explicit `baseline_effort`, and explicit `effort_weights`; it has no `transformation_intent` field (`contracts/provider.py:26-36`). `TaskDecomposition` is a frozen Pydantic contract containing `OperationalDecomposition`, `baseline_effort_allocations`, provenance, and provider provenance (`contracts/stages.py:64-89`). `BaselineEffortAllocation` stores the subtask ID and explicit effort or weight ratio (`contracts/stages.py:47-61`).

Explicit weights are normalized and, when a parent effort is supplied, converted into `EffortQuantity` allocations in `application/task_decomposition.py:103-132`. An injected `EffortAllocator` is invoked at lines 65-102 and its allocations are copied into the frozen baseline contract. No provider or application-local hidden effort state is used.

The contract permits an operational-only result with no allocation when the caller intentionally supplies neither baseline effort nor weights. This is a documented compatibility/estimation boundary: canonical transformation evaluation should supply explicit baseline quantities or an allocator. The absence is visible as an empty `baseline_effort_allocations` tuple, not hidden state.

## Transformation-decomposition verification

`decompose_transformation()` accepts `TransformationDecompositionRequest`, which contains an existing `TaskDecomposition`, `transformation_context`, and explicit accounting input (`contracts/provider.py:39-48`). It reads the supplied operational decomposition at `application/transformation_decomposition.py:35` and never invokes `generate_operational_decomposition()`.

The function validates RETAIN/REMOVE before added-work generation (`:36-57`). `_apply_baseline_allocation()` copies the frozen effort or normalized weight values into classification rows using `model_copy`; it does not mutate the supplied task decomposition (`:87-122`). The added-work result and canonical impact are returned in `TransformationDecompositionResult` (`contracts/stages.py:187-197`).

Transformation-specific data is represented by `transformation_context`, while baseline task/process data is represented by `TaskDecomposition`. No transformation-specific field is stored in the task result.

## Accounting authority

`domain/accounting.py` remains the single production authority for W0, W1, gross removed work, normalized ratios, net substitution, net augmentation, and effect classification (`:86-218`). `decompose_transformation()` only prepares validated inputs and calls `run_staged_pipeline()` (`:58-64`). `run_staged_pipeline()` delegates to `account_absolute()` or `account_normalized()` and does not redefine the formulas.

The production search found no application-level `account_transformation()` and no duplicate production implementation of the canonical formulas. `run_staged_pipeline()` remains a lower-level compatibility/integration primitive, not a third sibling application capability.

## Provider and context findings

`ports/provider.py` now has the intended semantic capability split:

- `TaskDecompositionProvider` exposes operational decomposition only.
- `TransformationDecompositionProvider` exposes RETAIN/REMOVE and added-work classification.
- `DecompositionProvider` composes both capabilities for compatibility.

OpenAI, Gemini, and DeepSeek remain single concrete provider implementations with shared provider configuration/transport patterns. No provider owns accounting, scenario management, simulation, or repeated evaluation. The shared `_shared.py` adapter supports both canonical requests and the historical compatibility request shape.

Canonical request context is separated as `task_context` and `transformation_context`. The new application APIs do not accept or require `transformation_intent`.

## Remaining `transformation_intent` occurrences

Production occurrences are classified as follows:

- `contracts/provider.py:51-61`, `DecompositionRequest.transformation_intent`: `COMPATIBILITY_ONLY`. This is the historical combined request retained for existing callers.
- `providers/_shared.py:42`, legacy request serialization: `COMPATIBILITY_ONLY` and provider-internal handling of the historical request shape. The canonical task and transformation request branches do not emit this field.

The compatibility adapter in `application/provider_service.py:70-98` retains the legacy request while invoking the underlying provider. The canonical `TaskDecompositionRequest` passed into `decompose_task()` has no such field, and the boundary test explicitly verifies this. Test fixtures and audit documentation contain historical compatibility references but do not create canonical runtime dependencies.

## Compatibility façade

`decompose()` still accepts the historical `DecompositionRequest` and returns the historical `StagedDecompositionResult`. Its implementation now constructs a clean `TaskDecompositionRequest`, calls `decompose_task()`, constructs a `TransformationDecompositionRequest`, calls `decompose_transformation()`, and maps the result back to the compatibility result (`provider_service.py:40-67`).

There is no parallel operational-generation, classification, or accounting implementation in the façade. The `_CompatibilityProvider` only adapts request shapes and preserves the historical provider call contract.

## Effort ownership

The verified ownership flow is:

```text
task request
  ↓
decompose_task()
  ↓
explicit weights or EffortAllocator
  ↓
TaskDecomposition.baseline_effort_allocations
  ↓
decompose_transformation()
  ↓
classification rows receive frozen baseline effort/ratios
  ↓
domain accounting
```

Bot0 row-level effort adaptation remains outside this repository's new canonical path and was not redesigned. The compatibility façade preserves the existing provider/adapter behavior.

## Test verification

`tests/test_task_transformation_boundaries.py` proves task-only execution, operational validation, explicit baseline allocation, transformation execution from a supplied baseline, no task regeneration, unchanged baseline state, accounting handoff, compatibility composition, provider capability checks, and `transformation_intent` isolation.

The frozen-baseline test invokes transformation decomposition twice with one baseline and verifies one task-generation call, identity reuse, unchanged allocations, and different resulting impacts. This is an immutability and boundary test, not scenario management or alternative-transformation orchestration.

The full non-live suite result is `68 passed, 3 skipped`. The skipped tests are live-provider smoke tests. No live provider call is required for ordinary tests.

## Ownership-boundary check

No standalone production ownership of scenarios, simulation orchestration, Monte Carlo, grid search, alternative management, or repeated-evaluation orchestration was found. The only related language is in documentation, test import-boundary assertions, or the approved baseline-reuse rationale.

The enforced invariant is that transformation decomposition consumes an existing task decomposition and does not perform task decomposition itself.

## Public API

The root package now exposes the intended application surface:

- `decompose_task(...)` for task decomposition only;
- `decompose_transformation(...)` for transformation decomposition over an existing baseline;
- `decompose(...)` for compatibility/full convenience composition.

The low-level `account_absolute()`, `account_normalized()`, and `run_staged_pipeline()` APIs remain available according to the existing public surface. No additional scenario or simulation APIs were added.

## Corrections made

No production correction was required during this verification wave. No Bot0 file was modified. The only new file for this wave is this verification report.

## Verification commands and results

- `pytest -q`: `68 passed, 3 skipped`.
- `ruff check src tests`: passed.
- `ruff format --check` on the touched Python files: passed.
- `python -m compileall -q src`: passed.
- Package import smoke test for `decompose_task`, `decompose_transformation`, and `decompose`: passed.
- Forbidden dependency scan: no AgenticAICompass, SQLAlchemy, FastAPI, workflow_compute, or vendor SDK imports in core contracts/domain/validation/application/ports. Vendor imports remain isolated to concrete provider adapters.
- `git diff --check`: passed.
- Markdown trailing-whitespace check: passed for this report.

## Remaining compatibility debt

- The legacy `DecompositionRequest` and its `transformation_intent` field remain publicly available for compatibility.
- The compatibility façade deliberately preserves the historical provider request shape.
- Baseline allocation can be omitted for operational-only task decomposition; transformation accounting still requires explicit accounting quantities, and canonical baseline reuse should provide explicit allocations.
- Bot0 still owns its row-level effort adaptation and has not migrated to the new standalone capability APIs.

These are bounded compatibility concerns, not architectural blockers for the next wave.

## Recommendation for S2B

The approved two-capability boundary is implemented and independently verified. S2B may proceed without beginning scenario management, simulation, benchmark orchestration, or Bot0 migration in this wave.

**BOUNDARY RESTORATION VERIFIED WITH MINOR DEBT — PROCEED TO S2B**

## S2A-4 post-verification note

S2A-4 subsequently removed the compatibility debt listed above. The standalone legacy `DecompositionRequest`, `transformation_intent`, request translation, and `_CompatibilityProvider` path were removed. AgenticAICompass now crosses the boundary through canonical task and transformation requests and consumes `TransformationDecompositionResult`. The historical findings above remain unchanged as the S2A-3 snapshot.
