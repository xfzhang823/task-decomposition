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
- `src/task_transmorph/domain/accounting.py` owns deterministic accounting mathematics.
- Providers propose semantic facts; they do not provide authoritative accounting metrics.
- Transformation decomposition consumes an existing `TaskDecomposition` and must not regenerate it.
- Complete bottom-up effort estimates are mandatory for canonical baseline decomposition.
- Calculate each subtask's expected effort per parent output as `expected_occurrences_per_parent_output × active_effort_per_occurrence`; those products are the canonical allocation source.
- Normalize the derived weights to `W0 = 1.0` by calling the deterministic allocation utility; measured `baseline_effort` is optional and only materializes absolute values.
- Do not add host-weight or allocator alternatives, equal-effort fallbacks, or a separate public allocation stage.

## Accounting semantics

- `baseline_human_effort` is the total original human effort (`W0`), not an additional component to sum.
- Preserve the baseline partition: `W0 = retained_human_work + gross_removed_work`.
- `gross_removed_work` is baseline work classified `REMOVE`; do not include newly introduced support work in it.
- Preserve the post-transformation relationship: `W1 = retained_human_work + resolved_support_work`.
- Gross removal is not net reduction; support work can reduce, eliminate, or exceed the gross reduction.
- Do not invent or duplicate accounting formulas. `src/task_transmorph/domain/accounting.py` is the sole accounting authority.
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

## Invariant-driven development

`docs/invariants/registry.yaml` is the canonical machine-readable invariant
index. Before changing decomposition, estimation, validation, or accounting
behavior:

1. Identify the affected invariant IDs in the registry.
2. Review each definition, owner, enforcement mechanism, and referenced test.
3. Check the relevant evidence in [`docs/invariants/AUDIT.md`](docs/invariants/AUDIT.md)
   and [`docs/invariants/BEHAVIORAL_COVERAGE_AUDIT.md`](docs/invariants/BEHAVIORAL_COVERAGE_AUDIT.md).
4. Preserve established contracts unless an intentional change is explicitly
   authorized.

After changing relevant behavior:

1. Run focused regression tests for the affected invariants, then broader tests
   as appropriate.
2. Keep implementation, tests, registry metadata, and audit evidence
   consistent. Update registry metadata when ownership, enforcement, or a
   contract definition changes; update audit evidence when behavioral coverage
   changes.
3. Report the affected invariant IDs and verification results.

`verified` invariants are established by implementation and focused evidence;
`partial` invariants are not fully machine-enforced; `proposed` invariants are
non-authoritative. Do not promote proposed invariants into mandatory behavior,
silently weaken an invariant, or change production formulas merely to satisfy a
failing test. The registry is descriptive and is not loaded at runtime.

The behavioral coverage audit identifies `CMP-001` (baseline effort product),
`CMP-005` (W0 baseline partition), and `CMP-010` (bottom-up allocation
precedence) as important computational contracts with dedicated regression
coverage.

## Verification

When the repository virtual environment is available, use the project
environment explicitly:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python -m compileall -q src
git diff --check
```

Run the invariant metadata check when registry files change:

```bash
.venv/bin/python -m pytest tests/test_invariant_registry.py
```

The pytest, Ruff, or compileall commands may be unavailable in a partial local
environment, and unrelated pre-existing findings may remain. Report those
conditions rather than changing dependencies or unrelated files to make the
checks pass. Keep tests credential-free; live semantic benchmarks are opt-in
and must not be run as part of ordinary verification.
