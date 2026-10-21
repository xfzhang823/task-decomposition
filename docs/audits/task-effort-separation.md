# Audit: Task Decomposition and Effort Allocation Separation

## Scope and conclusion

This audit reviews the current task-decomposition contracts, task-stage
application, allocation utilities, provider prompts, transformation handoff,
tests, notebook, and the accessible AgenticAICompass consumer.

The current design keeps provider-generated relative effort weights and performs
deterministic allocation inside `decompose_task()`. The remaining coupling is
that task requests also accept alternate host effort weights and an optional
allocator protocol. Those alternatives duplicate the provider-weight path.
The smallest canonical design is to retain provider weights, normalize them to
`W0 = 1.0` by the existing deterministic allocator, and keep measured absolute
effort only as an optional materialization of the same allocation. Removing
provider-generated relative weights is explicitly out of scope.

Normalized accounting can operate without absolute hours. It requires an
explicit normalized baseline partition and resolved support inputs, but it does
not require per-subtask absolute effort. Meaningful relative per-subtask
weights still need an explicit source; they should come from a separate
allocation capability, not from the operational decomposition provider.

## Current flow

```text
TaskDecompositionRequest
  ├─ task and context
  └─ optional measured baseline_effort
          ↓
provider.generate_operational_decomposition()
  └─ OperationalSubtask.relative_effort_weight (currently provider-generated)
          ↓
decompose_task()
  └─ _allocate_baseline()  [provider weights → deterministic normalized allocation]
          ↓
TaskDecomposition
  ├─ operational_decomposition
  └─ baseline_effort_allocations (possibly empty, estimated, or host-supplied)
          ↓
decompose_transformation()
  ├─ RETAIN/REMOVE classification
  ├─ added-work classification
  ├─ support-work resolution
  └─ deterministic accounting
```

`decompose()` composes the same two application capabilities, but currently
calls `decompose_task(request, provider)` without an explicit allocation step.
Allocation therefore comes from provider-generated relative weights. An
optional request baseline only determines whether compatible absolute amounts
are materialized in addition to normalized shares.

## Findings

### 1. Where effort enters task decomposition

`TaskDecompositionRequest` in `contracts/provider.py` has one effort-related
field:

- `baseline_effort: EffortQuantity | None`: a measured parent effort that can
  be distributed to subtasks.

`decompose_task()` accepts a third effort-related input as a keyword-only
argument:

```python
decompose_task(request, provider, *, evaluator=None)
```

After provider validation and semantic evaluation, it calls the private
`_allocate_baseline()` helper. That helper normalizes provider
`relative_effort_weight` values through `domain.allocate_effort()` using
`W0 = 1.0`. If a measured baseline is present, the same provider weights are
allocated against that parent and stored as compatible absolute effort. If
provider weights are absent or incomplete, the result has no baseline
allocations.

The `TaskDecomposition` contract therefore combines an operational result with
an optional frozen allocation. `BaselineEffortAllocation` can contain either
absolute `effort` or normalized `weight_ratio`, and records whether the source
was `estimated` or `host`.

### 2. Providers currently generate effort weights

Yes. `providers/prompts.py` explicitly instructs the operational provider to:

- assign each subtask a positive `relative_effort_weight`;
- estimate its share of baseline human working time;
- use duration, frequency, workload volume, benchmarks, or occupational
  estimates; and
- return positive, unnormalized weights during repair.

`OperationalSubtask.relative_effort_weight` is optional in the Pydantic
contract, but the concrete provider prompt makes it a normal expected output.
The OpenAI adapter also has stage-schema handling for the field, and the
effort-estimation tests verify that provider weights become normalized task
allocations.

This means the current operational provider is responsible for both:

1. identifying what work exists; and
2. estimating relative effort for that work.

That is the principal architectural coupling identified by this audit.

### 3. What `allocate_effort()` does

`domain/allocation.py:allocate_effort()` is deterministic. It accepts:

```python
allocate_effort(parent_effort, weights)
```

It validates that weights exist, are non-negative, and have a positive total;
normalizes them by their sum; multiplies each normalized weight by the supplied
parent effort; and verifies that the allocated values reconcile to the parent
within `DEFAULT_TOLERANCE`.

It does not estimate weights, consult a provider, infer equal effort, or
perform accounting. Provider output is the semantic source of relative
weights; this utility is the sole deterministic normalization and allocation
authority.

### 4. Downstream operations that require allocation

Transformation decomposition consumes an existing `TaskDecomposition`. Its
`_apply_baseline_allocation()` helper copies:

- absolute allocation effort into classified subtasks for absolute accounting;
- normalized allocation ratios into classified subtasks for normalized
  accounting.

If the task decomposition has no allocations, this helper is a no-op. The
staged pipeline can still validate and account from explicit aggregate
`AbsoluteEffortInput` or `NormalizedAccountingInput` values when provider
classification rows do not carry per-subtask effort.

Allocation becomes materially important in these cases:

- transformation consumers need per-subtask retained/removed effort for
  review, projection, or reconciliation;
- the application wants the transformation classification to reconcile to
  the explicit accounting input at row level;
- added-work estimation references a baseline subtask, because the estimator
  needs that reference subtask's absolute effort or normalized ratio; and
- downstream consumers persist or display subtask-level baseline amounts.

The current added-work estimator can use an external quantitative normalized or
absolute anchor, but a reference-subtask estimate without an allocated
`effort`/`baseline_effort_ratio` is not computable.

`decompose()` also depends on the current coupling: it runs `decompose_task()`
and immediately passes the returned task result to transformation
decomposition. A complete separation requires it to make the allocation step
explicit or to accept an already allocated baseline.

### 5. Downstream AgenticAICompass integration

The accessible checkout is `/home/xzhang/dev/AgenticAICompass`. Its
`app/services/assumption_trail/task_decomposition_adapter.py` currently:

- defines `Bot0TaskDecompositionRequest.effort_weights`;
- maps those weights into canonical `TaskDecompositionRequest.effort_weights`;
- calls `decompose_task()`; and
- uses `_EffortAllocatingProvider` to allocate classified rows before
  transformation accounting when provider rows do not carry effort.

AgenticAICompass also has a separate `app/services/effort_weighting` service
that performs benchmark-grounded and/or LLM-assisted effort-weight estimation,
with deterministic fallback and normalization. That service is evidence that
allocation can be owned outside operational decomposition, but the adapter's
current canonical request still carries effort weights through the task-stage
request.

The downstream integration is therefore an active breaking-change surface, not
dead code. The accessible adapter currently passes the old task-request
`effort_weights` field, so it must migrate to provider-derived normalized
allocations before adopting this repository change. Removing that field or
changing the task result shape requires coordinated adapter, transformation
handoff, fixtures, and tests changes in AgenticAICompass. This repository does
not add a compatibility shim for that migration.

## Proposed canonical architecture

### Operational decomposition

`decompose_task()` should be responsible only for:

- validating the task reference and context;
- asking the provider for operational subtasks;
- validating identity, sequence, dependencies, and semantic quality; and
- returning an operational decomposition with provider provenance.

The operational provider schema and prompt should not contain
`relative_effort_weight`. Operational output should not include an effort
estimate merely because a provider can produce one.

The result may remain named `TaskDecomposition` for a minimal migration, but
its allocation collection should be empty by construction. A cleaner long-term
contract is for `decompose_task()` to return `OperationalDecomposition` and for
an explicit allocation operation to produce the allocated baseline required by
transformation.

### Explicit allocation

Introduce one canonical allocation capability at the application boundary. It
should accept the validated operational decomposition plus an explicit
allocation source, such as:

- host-provided absolute effort and weights;
- host-provided normalized weights with `W0 = 1.0` semantics; or
- a dedicated effort-weight estimator that returns validated relative weights.

The capability should return a complete allocation covering every operational
subtask, with either absolute effort, normalized ratios, or both when an
absolute parent is supplied. It should delegate arithmetic to the existing
deterministic allocation utility and preserve the existing tolerance and
non-negative/positive-total validation.

The existing low-level `allocate_effort()` should remain the arithmetic utility.
It should not become an LLM estimator or acquire accounting responsibilities.

### Transformation and accounting

`decompose_transformation()` should accept the allocated baseline contract when
subtask-level accounting or reference-based added-work estimation is needed.
Its existing behavior of consuming an existing decomposition must remain.

Normalized accounting remains valid with no absolute hours:

```text
W0 = 1.0
retained_work_ratio + gross_removed_work_ratio = 1.0
W1 = retained_work_ratio + resolved_support_work
```

This supports meaningful normalized per-subtask weights, but only after an
explicit allocation source supplies those weights. Normalization is not a
license to assign equal effort or to infer missing weights.

Absolute accounting remains optional. When measured baseline effort is
available, the same normalized allocation can be converted to compatible
absolute quantities using the existing allocation utility.

## Contract and API changes

The normalized-first cleanup is breaking for callers that use the redundant
host allocation paths:

1. Remove `effort_weights` from `TaskDecompositionRequest`.
2. Remove the unused `EffortAllocator` protocol and `contracts.allocation`
   request/result models; retain the deterministic `allocate_effort` utility.
3. Keep `baseline_effort` optional because it has a distinct use: materializing
   absolute quantities from normalized provider weights.
4. Keep `relative_effort_weight` in the provider schema and prompts; removing
   provider-generated weights is explicitly out of scope.
5. Keep the three canonical entry points and their composition. No public
   allocation stage is added.
6. Update the notebook so the first task test and subsequent transformation
   analysis can run from normalized allocations without measured hours.
7. Migrate downstream callers that pass `effort_weights` or import
   `EffortAllocator` before adopting this contract.

No compatibility alias should preserve the old implicit behavior. A caller
that needs transformation accounting must migrate to an allocated baseline or
to an explicitly supported aggregate-accounting path.

## Recommended implementation sequence

1. Add contract-level tests that construct an operational decomposition without
   any effort fields and assert that task decomposition returns no allocation.
2. Introduce the explicit allocation capability around the existing allocation
   contracts and utility, first supporting normalized weights with `W0 = 1.0`
   and then absolute parent effort.
3. Remove relative weight fields from the provider operational schema and
   prompts; update provider parity and semantic validation fixtures.
4. Make transformation entry requirements explicit: require an allocation for
   row-level/reference-based paths, while retaining normalized aggregate
   accounting where the canonical contract supports it.
5. Update `decompose()` to expose the explicit allocation boundary.
6. Migrate AgenticAICompass's adapter and effort-weighting service, then run its
   adapter, transformation, and effort-weighting tests.
7. Update the notebook and documentation to show task decomposition, allocation,
   transformation, and accounting as separate stages.
8. Remove the old request fields, implicit allocation path, and provider weight
   prompts only after downstream migration is complete.

## Verification plan

The implementation should add or update tests for:

- task decomposition with no baseline effort and provider-generated normalized
  allocations in the result;
- explicit normalized allocation whose shares sum to one without absolute
  hours;
- explicit absolute allocation that reconciles to its parent effort;
- rejection of incomplete, negative, zero-total, or unknown-subtask weights;
- transformation with an allocated normalized baseline;
- transformation with an allocated absolute baseline;
- aggregate normalized accounting without per-subtask absolute hours;
- reference-based added-work estimation with and without required allocation;
- `decompose()` explicit composition and no hidden allocation; and
- AgenticAICompass adapter and effort-weighting integration.

Provider tests should remain credential-free except for explicitly opt-in live
benchmarks.

## Audit limitations

The AgenticAICompass source was inspected read-only. No downstream code was
modified. Remote consumers beyond that accessible checkout were not verified.
The current library also permits a `TaskDecomposition` with no allocations,
which means some aggregate normalized accounting paths already work without
hours; the stricter requirement that every transformation have a complete
allocation is a proposed architectural boundary, not current behavior.
