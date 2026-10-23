# Normalized transformation estimation audit

The notebook transformation path now uses an explicit estimation bridge rather than inventing retained or gross-removed ratios. A completed `TaskDecomposition` supplies frozen relative-effort allocations, and the provider supplies RETAIN/REMOVE classifications with rationales. The bridge applies each allocation to a 100-unit comparative baseline, aggregates retained and gross-removed units, validates the resulting normalized partition, and reuses the existing support-work resolver and deterministic accounting pipeline.

The 100-unit baseline is not an hour estimate, capacity measure, or productivity claim. It is a normalized comparison basis. Provider classification remains an estimate; the bridge records the model rationale and this assumption for auditability. Added work remains post-transformation support work and is resolved separately, so gross removal is not counted again in `W1`.

The strict `decompose_transformation()` and `decompose()` contracts remain unchanged and still require explicit `NormalizedAccountingInput` or `AbsoluteEffortInput`. The new `estimate_transformation()` entry point is an opt-in provider-assisted path for callers that want the classification stages to establish the normalized accounting input from an existing task decomposition.

Notebook runs write concise JSON artifacts to the gitignored `outputs/` directory. Artifacts include the run ID, timestamp, provider, effective model, case identifier, transformation result, normalized per-subtask estimates, accounting result, validation output, and assumptions. The notebook excludes its editable input payload from those persisted artifacts by default.
