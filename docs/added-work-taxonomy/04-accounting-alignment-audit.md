# Added-Work Accounting Alignment Audit

## Scope and conclusion

The standalone `task_transmorph` code can aggregate classified added-work rows, but the legacy accounting buckets cannot be replaced safely in this pass. The fields are not only an internal mirror of `AI_INTERACTION` and `AI_VERIFICATION`; they are an existing explicit accounting and integration contract with three independently supplied values.

Per the task constraint, implementation stops here rather than silently reclassifying those values or adding compatibility aliases.

## Standalone contracts

`src/task_transmorph/contracts/effort.py` defines `SupportWorkInputs` with `governance`, `operational_support`, and `lifecycle_support`, each carrying its own value, ratio basis, unit, and time basis. `AbsoluteEffortInput` and `NormalizedAccountingInput` expose that object as explicit accounting input.

`src/task_transmorph/contracts/accounting.py` serializes the corresponding derived fields as `governance_work`, `operational_support_work`, and `lifecycle_support_work`. These are public Pydantic fields and are returned in `CanonicalTransformationImpact`.

`src/task_transmorph/domain/accounting.py` converts all three support inputs independently according to their ratio basis, validates absolute units/time bases for each, and sums them into `added_human_work`. W0/W1 formulas do not depend on the category names, but the three fields are independently observable and independently validated.

`src/task_transmorph/application/added_work_estimation.py` is the canonical support resolver. It preserves separate `AI_INTERACTION` and `AI_VERIFICATION` support inputs and applies host/estimate/auto precedence before the internal accounting handoff passes concrete inputs to deterministic accounting.

## Direct consumers and serialization

The documented external consumer exists at `/home/xzhang/dev/AgenticAICompass` and is outside this repository's writable scope. Evidence of an active dependency includes:

- `api/schemas/task_transformation_decomposition.py`, with `governance_effort`, `operational_support_effort`, and `lifecycle_support_effort` API fields;
- `agent/assumption_trail/schemas/transformation_decomposition.py`, with typed effort totals, work ratios, validators, serialization defaults, and legacy projections for all three buckets;
- `agent/assumption_trail/reasoning/transformation_decomposition.py` and `validation/transformation_decomposition.py`, which calculate and independently validate the three totals and ratios;
- frontend transformation-decomposition wizard and summary components, which render and edit the three workload fields;
- AgenticAICompass fixtures and tests asserting the three fields, their totals, ratios, and compatibility projections;
- standalone adapter tests that pass `SupportWorkInputs` through `task_decomposition_accounting_input`.

This is not a dead or speculative contract. Removing the fields from the standalone models would break external request construction and response parsing. Removing them only from derived output would break downstream field access and validation. Renaming them would require coordinated API, persistence/artifact, frontend, fixture, and migration changes in AgenticAICompass.

## Semantic assessment

The three buckets have a broader accounting meaning than the new execution taxonomy. In the external consumer, governance represents oversight/compliance work, operational support represents enablement or operational support, and lifecycle support represents recurring maintenance work. The consumer also preserves historical aliases such as oversight, enablement, and recurring effort. Those meanings include explicit human-work inputs that are not necessarily rows classified by the current AI execution taxonomy.

Therefore the old fields cannot be safely treated as one-to-one aliases for `AI_INTERACTION` and `AI_VERIFICATION`. Mapping both canonical categories into `operational_support` preserves the numeric sum but loses contractual category information and changes the meaning of explicit governance/lifecycle inputs. Mapping verification to governance or lifecycle would be an equally unsupported reinterpretation.

## W0/W1 and double-counting findings

The accounting formulas are independent of the category labels:

- W0 is baseline human effort;
- W1 is retained human work plus the converted sum of support inputs;
- `added_human_work` is the sum of the three converted support values.

The single resolver prevents added-work rows from being counted again through a second quantitative path. Empty categories produce explicit zero support values, and the two canonical execution categories remain independently observable.

## Required migration decision

Before replacing the accounting contract, the owning AgenticAICompass change must decide whether to:

1. migrate all explicit and persisted three-bucket inputs into two execution-level fields;
2. preserve the three-bucket accounting contract as a separate financial/reporting model while adding a two-category execution-work model; or
3. define an authoritative mapping and migration for historical governance, operational-support, and lifecycle-support values.

Option 2 is the safest architectural direction because it preserves existing explicit accounting and downstream reporting while allowing classified AI-introduced work to use the canonical two-category model. It is outside a safe standalone-only change because it requires coordinated external consumer changes.

## Status

No implementation changes were made for accounting alignment. The existing two-category classification change remains intact, but its current derived-accounting mapping is intentionally identified as an unresolved compatibility boundary rather than being presented as a complete canonical alignment.
