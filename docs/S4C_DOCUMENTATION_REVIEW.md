# S4C Documentation Review

## Documentation created or updated

- `README.md` was rewritten as the current architecture entry point.
- `docs/DECOMPOSITION_MODEL.md` documents task decomposition, transformation decomposition, provider boundaries, and downstream ownership.
- `docs/ACCOUNTING_MODEL.md` documents the implemented equations, units, support bases, ranges, tolerances, and edge behavior.
- `AGENTS.md` defines concise maintenance invariants for coding agents.
- `docs/S4C_DOCUMENTATION_REVIEW.md` records this review.
- `examples/openai_decompose.py` was checked against the documented `AbsoluteEffortInput` contract.

## Final documented architecture

The documented flow is `decompose_task(...)` → `TaskDecomposition` → `decompose_transformation(...)` → `TransformationDecompositionResult`. `decompose(...)` is documented only as convenience composition. Task decomposition establishes reusable baseline work; transformation decomposition consumes it, classifies RETAIN/REMOVE and added work, and invokes deterministic accounting.

## Ownership boundaries

The documentation distinguishes standalone decomposition and accounting ownership from host-owned workflow execution, capacity computation, scenarios, simulation, Monte Carlo, grid search, workforce planning, and alternative management.

## Accounting terminology and equations

The documentation explicitly distinguishes gross removed work from net substitution, defines W0 and W1, added human work categories, normalized and absolute modes, explicit support-ratio bases, effort units and time basis, effect tolerance, unclamped degradation, zero baseline, zero W1, and scale invariance.

## API examples

The examples were checked against the current exports and signatures. `TaskDecompositionRequest`, `TaskReference`, `decompose`, `AbsoluteEffortInput`, and `OpenAIDecompositionProvider` are current symbols. The provider-driven example keeps accounting input explicit.

## Agent guidance

`AGENTS.md` records the two-capability flow, ownership rules, accounting authority, provider trust boundary, frozen-baseline invariant, forbidden regressions, external-consumer caution, and standard verification commands.

## Stale documentation

The current README and new model documents no longer describe `transformation_intent`, legacy `DecompositionRequest`, compatibility provider machinery, or `BenchmarkPort` as current architecture. Historical audit documents retain those terms where they record earlier findings, implementation snapshots, or removed migration residue. `docs/S2A3_BOUNDARY_VERIFICATION.md` explicitly labels its old compatibility findings as subsequently removed by S2A-4, so it was not rewritten as history.

The repository-wide search still finds historical references in `docs/STANDALONE_FINAL_AUDIT.md`, `docs/TASK_TRANSFORMATION_BOUNDARY_AUDIT.md`, and prior wave reports, plus test assertions that verify absence or rejection. These are intentionally retained historical evidence rather than current API guidance.

## Checks

- `pytest -q`: run after documentation changes.
- `ruff check src tests`: run after documentation changes.
- `ruff format --check src tests`: run after documentation changes.
- `git diff --check`: run after documentation changes.
- Markdown examples and public imports were checked against the implementation.

## Remaining documentation gaps

Live provider semantic quality is not established because S4B-2 had no configured provider credentials. Detailed human review of live benchmark artifacts remains deferred. No implementation redesign is required by this documentation pass.

DOCUMENTATION COMPLETE — PROCEED TO S5
