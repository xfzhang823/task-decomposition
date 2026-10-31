# Task Transmorph Invariant Audit

Status: read-only architectural and semantic audit. This document establishes provisional invariant candidates for a future machine-readable registry; it does not define new contracts or implement enforcement.

## 1. Scope and methodology

This audit covers the current package under `src/task_transmorph/`. The requested `src/task_decomposition/` path does not exist in this checkout; older audit documents still contain references to that former package path and are treated as historical evidence, not current implementation evidence.

The review followed the public application flow and its dependencies:

```text
decompose_task()
  → validated operational decomposition and baseline allocation
estimate_transformation()
  → provider-assisted normalized transformation accounting
decompose_transformation()
  → strict transformation accounting from explicit input
decompose()
  → composition of the strict baseline and transformation operations
```

Sources reviewed included:

- `AGENTS.md` for ownership and accounting constraints;
- `docs/reference/DECOMPOSITION_MODEL.md` and `docs/reference/ACCOUNTING_MODEL.md`;
- application orchestration in `src/task_transmorph/application/`;
- contracts in `src/task_transmorph/contracts/`;
- deterministic allocation and accounting in `src/task_transmorph/domain/`;
- structural validation in `src/task_transmorph/validation/`;
- provider protocols and prompts; and
- focused tests under `tests/`, especially effort estimation, activity estimation, staged pipeline, mathematical validation, accounting, and boundary tests.

Status meanings:

- **Verified** — the rule is enforced by current implementation and has focused test evidence, or is a direct ownership/boundary property enforced by the architecture.
- **Partial** — implementation or tests cover an important portion, but semantic or cross-boundary enforcement is incomplete.
- **Proposed** — desirable contract not currently established by code and tests.
- **Conflicting** — implementation, contracts, tests, or documentation disagree; no canonical interpretation should be inferred without a follow-up decision.
- **Superseded** — a historical proposed candidate is retained for traceability but is covered by a newer verified invariant and is not active in the registry.

## 2. Current architecture and ownership

| Concern | Current owner | Evidence |
| --- | --- | --- |
| Task identity, operational subtasks, dependencies, and baseline estimates | `contracts` plus application validation | `src/task_transmorph/contracts/stages.py`; `validation/stages.py:31-148` |
| Baseline relative allocation and optional absolute materialization | `application/task_decomposition.py` plus `domain/allocation.py` | `task_decomposition.py:300-375`; `domain/allocation.py:11-48` |
| RETAIN/REMOVE classification and transformation-stage orchestration | transformation provider plus application validation | `application/transformation_decomposition.py:120-220`; `validation/stages.py:151-218` |
| Added human interaction and verification estimates | transformation provider, application resolver | `contracts/stages.py:327-450`; `application/activity_effort_estimation.py:28-115` |
| W0/W1, ratios, effect, unit and ratio-basis arithmetic | accounting domain only | `domain/accounting.py:90-255` |
| Provider-output validation and provenance | application validation and contracts | `application/_provider_stage.py`; `validation/stages.py`; `contracts/provenance.py` |
| Capacity, staffing, workload volume, throughput, scenarios, and simulation | outside this package | `AGENTS.md`; `contracts/provider.py` module documentation; `docs/reference/DECOMPOSITION_MODEL.md` |

The package is output-unit anchored: baseline and activity estimates are intended to represent active human effort per completed parent output. External parent-output volume and resource capacity are not inputs to the canonical effort products or W0/W1 accounting.

Providers propose semantic facts and assumptions. Python validates identities, products, units, allocation, and stage handoffs. `domain/accounting.py` computes authoritative W0/W1 metrics; provider-generated accounting metrics are not authoritative.

## 3. Candidate invariant inventory

### Structural invariants

| ID | Name | Owner | Rule | Evidence | Status | Risk if violated | Recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STR-001 | Unique ordered operational subtasks | `validation/stages.py` | Operational subtask IDs are unique and sequence indexes are exactly 1-based and contiguous. | `validation/stages.py:35-45`; `tests/test_task_transformation_boundaries.py`; `tests/test_effort_estimation.py` | Verified | Ambiguous row identity and unstable allocation/classification joins. | Retain focused validation tests in the registry. |
| STR-002 | Dependency references are valid and forward-only | `validation/stages.py` | A subtask cannot depend on itself, duplicate a dependency, reference an unknown subtask, or depend on a later sequence index. | `validation/stages.py:57-81`; `tests/test_task_transformation_boundaries.py` | Verified | Invalid operational order and impossible decomposition graphs. | Add explicit named tests for each dependency failure if coverage is not already isolated. |
| STR-003 | Classification covers the frozen baseline exactly | `validation/stages.py` | Every operational subtask appears exactly once in RETAIN/REMOVE classification; no unknown IDs are accepted; task identity is preserved. | `validation/stages.py:151-218`; `tests/test_task_transformation_boundaries.py` | Verified | Missing or duplicated baseline work could silently alter W0/W1. | Retain as a cross-stage identity invariant. |
| STR-004 | Removed work has complete agentic coverage | `validation/stages.py` | Every REMOVE subtask is assigned to exactly one agentic task; retained or unknown subtasks cannot be assigned; zero REMOVE requires zero agentic tasks. | `validation/stages.py:221-270`; `tests/test_task_transformation_boundaries.py` | Verified | AI responsibility mapping can omit or duplicate transformed work. | Retain; distinguish this semantic transformation artifact from workflow execution. |
| STR-005 | Modeled activity references are valid | `validation/stages.py` | Activity IDs are unique; each activity references known agentic tasks; no activities are allowed when synthesis has no agentic tasks. | `validation/stages.py:273-303`; `tests/test_task_transformation_boundaries.py` | Verified | Support work could be attached to nonexistent or unrelated AI responsibilities. | Retain; add explicit tests for duplicate activity IDs if registry coverage needs one-to-one evidence. |
| STR-006 | Activity effort estimates have complete coverage | `validation/stages.py` | Exactly one activity-effort estimate is required for each modeled activity; unknown, missing, or duplicate activity IDs fail. | `validation/stages.py:306-369`; `tests/test_activity_effort_estimation.py:test_missing_and_duplicate_estimates_are_rejected` | Verified | Added support work can be omitted or counted more than once. | Retain as a cardinality invariant. |
| STR-007 | Complete bottom-up estimate collection | `validation/stages.py` and contracts | Canonical baseline validation requires a non-empty bottom-up estimate for every operational subtask. Each estimate is validated and canonicalized before allocation; provider-only relative weights are not a supported canonical baseline input. | `validation/stages.py:46-49,85-148`; `contracts/stages.py:79-105,115-151`; `tests/test_effort_estimation.py:test_missing_bottom_up_estimates_are_rejected`; `docs/reference/DECOMPOSITION_MODEL.md` | Verified | Missing or incomplete effort facts would prevent deterministic baseline allocation. | Retain as the canonical baseline-entry invariant; keep the empty contract default only for intermediate semantic/evaluation models that do not enter canonical validation. |

### Computational invariants

| ID | Name | Owner | Rule | Evidence | Status | Risk if violated | Recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CMP-001 | Baseline effort product | validation/application | `expected_effort_per_parent_output = expected_occurrences_per_parent_output × active_effort_per_occurrence`, after compatible unit normalization. | `validation/stages.py:109-148`; `application/task_decomposition.py:343-375`; `tests/test_effort_estimation.py:test_inconsistent_provider_product_is_rejected` | Verified | Wrong baseline shares and incorrect W0 allocation. | Retain as a known-answer invariant; add a direct fractional-occurrence baseline test if desired. |
| CMP-002 | Activity effort product | validation/application | `expected_effort_per_parent_output = expected_occurrences_per_parent_output × active_effort_per_occurrence`; supplied products are checked and canonicalized. | `validation/stages.py:306-369`; `tests/test_activity_effort_estimation.py:test_expected_effort_is_optional_and_canonicalized_by_validation`; `test_product_and_units_are_validated_deterministically` | Verified | Incorrect AI interaction/verification support and W1. | Retain; use the same invariant ID family for baseline and activity products only if the registry distinguishes owner/context. |
| CMP-003 | One compatible effort basis per product | validation/resolver/accounting | Absolute values must use compatible units and time bases; baseline and activity calibration uses `PER_OPERATION`; compatible duration units may be converted. | `validation/stages.py:109-148`; `application/activity_effort_estimation.py:42-68`; `domain/accounting.py:17-28,166-213`; `tests/test_activity_effort_estimation.py:test_absolute_unit_boundary_is_rejected`; `tests/test_accounting.py:test_absolute_unit_mismatch_is_rejected` | Verified | Ratios and totals could combine incomparable quantities. | Retain as a computational boundary invariant. |
| CMP-004 | Allocation normalization and reconciliation | `domain/allocation.py` | Weights must be non-negative with a positive total; normalized allocations must reconcile to the parent effort within `DEFAULT_TOLERANCE`. | `domain/allocation.py:11-48`; `tests/test_domain_utilities.py:test_effort_allocation_is_deterministic_and_balanced`; `test_relative_weight_scale_does_not_change_allocation_proportions`; `tests/test_mathematical_validation.py:test_allocation_to_accounting_consistency` | Verified | Baseline allocations can lose work or depend on arbitrary weight scale. | Retain as the sole allocation invariant. |
| CMP-005 | Baseline partition | accounting domain | `W0 = retained_human_work + gross_removed_work`; baseline effort is not an additional summand. | `domain/accounting.py:166-196`; `contracts/effort.py:174-214`; `tests/test_accounting.py:test_invalid_balance_is_rejected`; `tests/test_mathematical_validation.py:test_algebraic_invariants` | Verified | Gross removal and retained work can be double-counted or leave W0 unreconciled. | Retain as a canonical accounting invariant. |
| CMP-006 | Post-transformation partition | accounting domain | `W1 = retained_human_work + resolved_support_work`; gross removed work is excluded from W1 and added support is not part of the original baseline partition. | `domain/accounting.py:171-178,210-238`; `tests/test_accounting.py:test_reference_absolute_case_has_distinct_gross_and_net_metrics`; `tests/test_mathematical_validation.py:test_algebraic_invariants` | Verified | Gross removal could be misreported as net reduction or support could be counted twice. | Retain and require every future aggregation path to delegate here. |
| CMP-007 | Ratio-basis conversion exactly once | accounting domain | Baseline-ratio, gross-removed-ratio, normalized-contribution, and absolute support inputs convert according to their declared denominator exactly once. | `domain/accounting.py:34-88`; `tests/test_accounting.py:test_removed_work_ratio_support_is_converted_once`; `test_absolute_support_can_be_supplied_as_ratio_of_baseline` | Verified | Support work may be inflated or attenuated by a second denominator conversion. | Retain as a basis-specific invariant. |
| CMP-008 | Zero and degradation edge semantics | accounting domain | Positive W0 is required for absolute accounting; W1 may be zero and then augmentation is `None`; ratios are not clamped and can represent degradation. | `domain/accounting.py:90-104,184-190,222-238`; `tests/test_accounting.py:test_degradation_is_unclamped`; `test_zero_baseline_is_error_but_zero_net_reports_undefined_multiplier`; `tests/test_mathematical_validation.py:test_full_removal_reports_undefined_augmentation_multiplier` | Verified | Consumers may infer false productivity gains or divide by zero. | Retain with explicit consumer-facing documentation. |
| CMP-009 | No external parent-volume multiplication | application boundary | Per-parent effort products must not be multiplied by external claims/tickets/invoices-per-period volume inside this package. | No workload-volume field exists in current contracts; `application/activity_effort_estimation.py:28-115`; `tests/test_activity_effort_estimation.py:test_repeated_activity_is_not_multiplied_by_external_volume`; `docs/reference/DECOMPOSITION_MODEL.md` | Partial | A future host or provider may multiply internal frequency and external demand, overstating workload. | Add an explicit boundary test or contract-level assertion when a volume-bearing integration is introduced; keep volume downstream. |
| CMP-010 | Bottom-up allocation precedence | application/validation/domain allocation | For canonical baseline decomposition, `expected_effort_per_parent_output` products determine relative allocation weights. Provider-supplied `relative_effort_weight` values are non-authoritative and cannot override bottom-up-derived weights; `allocate_effort()` performs the single normalization and reconciliation step. | `application/task_decomposition.py:300-375`; `validation/stages.py:46-148`; `domain/allocation.py:11-48`; `AGENTS.md`; `tests/test_effort_estimation.py:test_bottom_up_products_override_provider_relative_weights`; `tests/test_mathematical_validation.py:test_allocation_to_accounting_consistency` | Verified | A second or competing allocation source could produce irreproducible baseline partitions and downstream accounting. | Retain as the sole canonical allocation rule; add future known-answer tests only when allocation behavior changes. |

### Semantic invariants

| ID | Name | Owner | Rule | Evidence | Status | Risk if violated | Recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SEM-001 | Common parent-output denominator | provider/application/evaluator | Baseline and activity effort must describe expected active human effort per the same completed parent output and completion boundary. | `contracts/stages.py:39-60,103-143,368-450`; `providers/prompts.py`; `tests/test_evaluation_contracts.py:test_operational_prompt_defines_parent_output_and_effort_boundaries`; `docs/reference/DECOMPOSITION_MODEL.md` | Partial | Combining per-invoice, per-case, or per-escalation quantities can produce numerically valid but semantically false W0/W1. | Add structured denominator identity to every estimate or strengthen semantic validation; do not add external workload volume to these products. |
| SEM-002 | Conditional and repeated occurrences are expected frequencies | provider/application | `expected_occurrences_per_parent_output` may be fractional, zero, one, or greater than one; conditional work is represented by frequency and multiplied once, not treated as an unconditional duration or separate probability. | `contracts/stages.py:122-143,396-450`; `tests/test_activity_effort_estimation.py:test_expected_occurrences_are_multiplied_once_per_parent_output`; `test_expected_effort_is_optional_and_canonicalized_by_validation`; `docs/reference/DECOMPOSITION_MODEL.md` | Partial | Conditional and repeated work may be under- or over-counted, especially when internal workload is confused with external volume. | Preserve current arithmetic tests; add semantic fixtures for conditional baseline tasks and repeated rework. |
| SEM-003 | Active effort excludes passive or machine work | provider/evaluator boundary | Effort quantities represent active human work within the parent-output boundary; waiting, queue time, autonomous AI execution, and machine processing are excluded. | `contracts/stages.py:121-128,376-390`; `tests/test_evaluation_contracts.py:test_operational_prompt_defines_parent_output_and_effort_boundaries`; `docs/reference/DECOMPOSITION_MODEL.md` | Partial | Cycle time or machine time can be mistaken for human effort and distort substitution results. | Keep the prompt/rubric rule; add structured fields only if consumers need machine-checkable exclusion evidence. |
| SEM-004 | Supplied facts and model assumptions remain distinguishable | contracts/application/evaluator | Supplied parent contracts, estimates, assumptions, rationales, and provenance must not be presented as measured observations when they are provider- or application-inferred. | `contracts/stages.py:39-60,122-143`; `contracts/provenance.py`; `application/task_decomposition.py:378-390`; `tests/test_effort_estimation.py:test_supplied_parent_contract_is_preserved`; `tests/test_transformation_semantic_evaluation.py:test_reasonable_model_generated_occurrence_assumptions_are_not_rejected` | Partial | Planning estimates may be consumed as measured productivity or authoritative accounting. | Preserve `source`, `estimate_source`, rationale, and provenance; add a structured fact/assumption classification only after consumer requirements are known. |
| SEM-005 | Parent boundary is preserved across transformation | semantic validation/application | Transformation stages may change human work within the existing task boundary, but must not silently include downstream roles or later decisions outside the parent output contract. | `application/transformation_decomposition.py`; `tests/test_evaluation_contracts.py:test_transformation_prompts_preserve_task_scope_and_effort_denominator`; `docs/reference/DECOMPOSITION_MODEL.md` | Partial | Scope leakage creates false retained/removed work and incompatible denominators. | Continue semantic evaluation; add explicit boundary regression cases for high-risk task families. |

### Boundary invariants

| ID | Name | Owner | Rule | Evidence | Status | Risk if violated | Recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BND-001 | Provider output is untrusted semantic input | application/validation | Providers propose operational facts, classifications, and activity estimates; application validation controls identity, cardinality, products, units, and references. | `contracts/provider.py` module documentation; `application/_provider_stage.py`; `validation/stages.py`; `tests/test_import_boundary.py`, `tests/test_provider_import_isolation.py` | Verified | LLM output could become authoritative accounting or bypass stage invariants. | Retain provider parity and untrusted-output tests. |
| BND-002 | Deterministic accounting owns W0/W1 formulas | accounting domain | Derived W0/W1, ratios, effect, unit checks, and ratio-basis conversion are delegated to `domain/accounting.py`; providers do not calculate authoritative metrics. | `domain/accounting.py:90-255`; `application/staged_pipeline.py:27-68`; `tests/test_accounting.py`; `tests/test_staged_pipeline.py` | Verified | Duplicate formulas can diverge across provider or application paths. | Keep the domain as the sole formula authority. |
| BND-003 | Transformation consumes, never regenerates, the baseline | application/contracts | `decompose_transformation()` and `estimate_transformation()` operate on an existing frozen `TaskDecomposition`; classification references canonical subtask IDs and names. | `contracts/provider.py:73-105`; `application/transformation_decomposition.py`; `application/normalized_estimation.py:103-145`; `tests/test_task_transformation_boundaries.py` | Verified | A regenerated baseline makes before/after comparisons non-reproducible. | Retain frozen-baseline tests and provenance. |
| BND-004 | Normalized and absolute modes are explicit | contracts/accounting/application | Normalized accounting fixes `W0 = 1`; absolute accounting requires compatible `EffortQuantity` inputs and exposes quantities; normalized results expose ratios rather than absolute quantities. | `contracts/accounting.py:47-145`; `domain/accounting.py:107-239`; `tests/test_accounting.py:test_normalized_reference_is_semantically_equivalent_to_absolute`; `tests/test_staged_pipeline.py` | Verified | Consumers may treat comparative units as hours or mix incompatible bases. | Retain explicit mode and output-field semantics. |
| BND-005 | Capacity and workload aggregation remain downstream | repository boundary | This package does not own external output volume, staffing, calendars, throughput, capacity, scenarios, or simulation. | `AGENTS.md`; `contracts/provider.py` module documentation; `docs/reference/DECOMPOSITION_MODEL.md`; `tests/test_evaluation_contracts.py` prompt-boundary assertions | Verified | A host could apply task effort and volume/capacity transformations twice. | Add integration-level checks only in downstream consumers; do not add capacity abstractions here. |
| BND-006 | Provider capability requirements are explicit | interfaces/application | `decompose_task()` requires `TaskDecompositionProvider`; strict transformation requires the complete `TransformationDecompositionProvider`; `decompose()` requires the composite capability; normalized estimation requires transformation capability. | `interfaces/provider.py:16-88`; `application/task_decomposition.py`; `application/transformation_decomposition.py`; `application/provider_service.py`; `tests/test_task_transformation_boundaries.py` | Verified | Incomplete providers could silently fall back to partial or legacy behavior. | Retain explicit capability checks and failure tests. |

### Proposed registry candidates

These are not current contracts and should not be treated as implemented:

| ID | Name | Rationale | Status | Suggested owner/enforcement |
| --- | --- | --- | --- | --- |
| PROP-001 | Explicit parent-output identity on every estimate | A common denominator is currently semantic text/provenance, not a machine-checked identity shared by baseline and activity estimates. | Proposed | Extend contracts only after consumer requirements are confirmed; validate identity at stage boundaries. |
| PROP-002 | Structured fact-versus-assumption classification | Current `source`, `estimate_source`, assumptions, rationale, and provenance preserve useful distinctions but do not provide one uniform machine-readable fact type. | Proposed | Reuse existing provenance and source fields; avoid a parallel abstraction until a consumer requires it. |
| PROP-003 | Explicit external-volume boundary type | The current package has no volume field, which prevents direct double-counting but cannot validate a downstream integration payload. | Proposed | Enforce at integration boundaries, not inside per-parent effort contracts. |
| PROP-004 | Canonical baseline allocation precedence | Historical candidate for one explicit documented and tested allocation source. The requirement is now established by verified `CMP-010`, which makes bottom-up expected-effort products authoritative and provider relative weights non-authoritative. | Superseded by CMP-010 | Preserved for audit history; do not activate as a separate registry invariant. |

## 4. Gaps, contradictions, and ambiguous semantics

### 4.1 Baseline estimate requirement is now explicit

Canonical operational validation already required a complete non-empty bottom-up estimate collection, and the contract documentation now distinguishes that canonical requirement from the empty default retained for intermediate semantic/evaluation models. Focused tests cover both missing and incomplete collections. Provider-only relative weights are not a supported canonical baseline path.

### 4.2 Allocation precedence is now explicit

`_prepare_operational()` derives relative weights from validated bottom-up products before `_allocate_baseline()` calls the sole deterministic allocation utility. Provider-supplied relative weights remain compatibility fields but cannot override the derived weights. Focused tests use deliberately conflicting provider weights and assert the bottom-up allocation result.

### 4.3 Parent-output identity is semantic, not fully structural

The contracts carry `ParentOutputContract`, expected occurrences per parent output, rationale, and provenance, but baseline and activity estimates do not carry a machine-checked foreign key to the same parent-output contract. Prompts and semantic evaluation protect the denominator, and tests cover prompt wording, but structural validation cannot prove that two independently supplied estimates use the same output unit.

### 4.4 Workload volume is intentionally absent

No current public contract accepts external volume such as claims per month or invoices per day. That is consistent with ownership boundaries and prevents direct volume multiplication in this package. It also means the repository cannot validate a downstream integration that accidentally multiplies per-parent effort by internal workload twice or applies volume in both task decomposition and capacity computation. The reusable invariant is currently a boundary rule supported by tests and documentation, not a full integration contract.

### 4.5 Existing historical audit paths are stale

Several older audit documents reference `src/task_decomposition/` and former module names. Current implementation evidence for this audit uses `src/task_transmorph/`. The historical documents remain useful for design history but should not be machine-parsed as current source references without path normalization.

## 5. Recommended initial invariants, prioritized by correctness risk

### P0 — protect before a registry is authoritative

1. **SEM-001:** Establish how the shared parent-output denominator is represented and checked.
2. **CMP-005 and CMP-006:** Preserve the W0 and W1 partitions as the only accounting identities.

### P1 — protect existing arithmetic and stage boundaries

1. **CMP-001 and CMP-002:** Keep deterministic occurrence-by-effort products and canonicalization.
2. **CMP-003 and CMP-007:** Keep unit/time-basis and ratio-basis conversion checks.
3. **CMP-008:** Keep zero-baseline, zero-W1, tolerance, and unclamped degradation behavior.
4. **STR-003 through STR-006:** Keep identity, coverage, and no-duplicate guarantees across transformation stages.
5. **BND-001 through BND-004:** Keep provider/output separation and deterministic accounting ownership.

### P2 — improve semantic and integration evidence

1. **SEM-002 through SEM-005:** Add representative conditional, repeated, rework, scope, and assumption fixtures.
2. **CMP-009 / PROP-003:** Add an integration boundary test when any downstream workload-volume payload is introduced.
3. **SEM-004 / PROP-002:** Improve structured provenance only when a consumer needs machine-readable fact/assumption filtering.

## 6. Existing tests reusable for Phase 2

- `tests/test_effort_estimation.py` — parent-output contracts, baseline product validation, unit normalization, total effort, and zero-effort behavior.
- `tests/test_activity_effort_estimation.py` — conditional/repeated occurrence products, one-time multiplication, activity cardinality, unit conversion, and normalized/absolute calibration.
- `tests/test_accounting.py` — W0/W1 partitions, ratio bases, gross-versus-net distinction, degradation, zero-baseline, zero-W1, and unit errors.
- `tests/test_mathematical_validation.py` — algebraic identities, allocation-to-accounting handoff, scale equivalence, tolerances, and all-retained/all-removed cases.
- `tests/test_domain_utilities.py` — deterministic allocation, weight-scale invariance, retained/removed aggregation, and required row effort.
- `tests/test_task_transformation_boundaries.py` — identity, stage coverage, provider sequence, frozen-baseline consumption, and transformation handoff behavior.
- `tests/test_staged_pipeline.py` — parity between staged and direct canonical accounting for absolute and normalized inputs.
- `tests/test_evaluation_contracts.py` — parent-output boundaries, internal workload handling, conditional/repeated work guidance, scope, and semantic prompt protections.

## 7. Suggested enforcement mechanisms

1. Preserve the resolved STR-007 and CMP-010 behavior in future changes before creating `registry.yaml`; the registry should record the canonical validator and allocation-source decisions rather than reintroducing alternate paths.
2. Reuse `validate_operational_decomposition()`, `validate_baseline_effort_estimates()`, `validate_activity_effort_estimation()`, `validate_stage_chain()`, and `domain/accounting.py` as invariant owners rather than adding parallel validators.
3. Add known-answer tests around each resolved precedence decision and each parent-output denominator rule.
4. Keep provider tests focused on untrusted semantic output and keep arithmetic tests provider-free.
5. Treat external workload volume and capacity as integration-level invariants owned by downstream systems, with explicit anti-double-counting tests at those boundaries.
6. Normalize historical source paths before using existing audit documents as machine-readable evidence.

## Phase 2 boundary

The active registry supersedes `PROP-004` with verified `CMP-010`; the historical candidate and its rationale remain here for traceability. The STR-007 and CMP-010 decisions are reflected in implementation, focused tests, and documentation; future registry work should preserve them without expanding into capacity or workload-volume contracts.
