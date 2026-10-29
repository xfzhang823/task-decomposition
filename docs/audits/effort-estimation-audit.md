# Effort Estimation Audit

## 1. Scope and Objectives

This audit reviews the current task-decomposition effort-estimation behavior, including provider prompts, application orchestration, Pydantic contracts, deterministic allocation/accounting, tests, tracing, and the existing effort documentation.

The audit is read-only. No production code, schemas, tests, or existing documentation were changed. The only artifact created by this phase is this audit record.

The audit distinguishes baseline effort estimation from transformation support work estimation. They use different contracts and references:

- Baseline estimation assigns each operational subtask a provider-generated relative share of aggregate baseline human effort.
- Transformation support estimation describes newly introduced human work and derives quantities from occurrence estimates and a baseline or external reference.
- Canonical W0/W1 accounting is deterministic and is not provider-owned.

## 2. Current Architecture and Ownership

| Concern | Current owner | Evidence and responsibility |
| --- | --- | --- |
| Operational decomposition and raw baseline weights | Provider prompt/provider | `OperationalSubtask.relative_effort_weight` and `effort_rationale`; [`prompts.py`](../../src/task_decomposition/providers/prompts.py:33-50) |
| Baseline normalization/allocation | Application plus deterministic utility | [`task_decomposition.py`](../../src/task_decomposition/application/task_decomposition.py:255-288) calls [`allocate_effort()`](../../src/task_decomposition/domain/allocation.py:12-45) |
| Baseline allocation contract | `BaselineEffortAllocation` / `TaskDecomposition` | [`stages.py`](../../src/task_decomposition/contracts/stages.py:55-96) |
| RETAIN/REMOVE classification | Transformation provider | [`transformation_decomposition.py`](../../src/task_decomposition/application/transformation_decomposition.py:60-72) |
| Added-work identification | Transformation provider | `AddedWorkClassification` and `ADDED_WORK_PROMPT`; [`stages.py`](../../src/task_decomposition/contracts/stages.py:213-241), [`prompts.py`](../../src/task_decomposition/providers/prompts.py:119-131) |
| Added-work quantitative resolution | Application | [`added_work_estimation.py`](../../src/task_decomposition/application/added_work_estimation.py:27-115) |
| W0/W1 and derived metrics | Accounting domain | [`accounting.py`](../../src/task_decomposition/domain/accounting.py:108-168) and absolute counterpart |
| Assumption/rationale evaluation | Semantic evaluator | [`rubric.py`](../../src/task_decomposition/evaluation/rubric.py:21-26) |
| Provider invocation/provenance | Provider adapters and tracing | [`_shared.py`](../../src/task_decomposition/providers/_shared.py:56-85), [`provenance.py`](../../src/task_decomposition/contracts/provenance.py:8-32), [`tracing.py`](../../src/task_decomposition/tracing.py:293-328) |

The public application entry points are documented in [`application/README.md`](../../src/task_decomposition/application/README.md:17-25): `decompose_task`, `decompose_transformation`, `estimate_transformation`, and the convenience composition `decompose`.

There is no second authoritative baseline calculator. The raw provider weight is normalized once by `allocate_effort()`. The transformation path consumes the frozen allocation. Added-work estimation is a separate, intentional path for post-transformation support work, not an alternative baseline allocator.

## 3. Current Estimation Pipeline

### 3.1 Baseline path

```text
TaskDecompositionRequest
  ↓
provider.generate_operational_decomposition()
  ↓
structural validation + semantic evaluation/repair
  ↓
_allocate_baseline()
  ├─ raw relative_effort_weight values
  ├─ deterministic normalization to W0 = 1.0
  └─ optional allocation against measured baseline_effort
  ↓
TaskDecomposition with BaselineEffortAllocation rows
```

`decompose_task()` validates the provider result, obtains semantic evaluation, and allocates only after acceptance ([`task_decomposition.py`](../../src/task_decomposition/application/task_decomposition.py:40-87)). `_allocate_baseline()` computes the normalized share as:

```text
weight_ratio_i = raw_weight_i / sum(raw_weights)
```

The utility validates positive/non-negative inputs and checks reconciliation within `DEFAULT_TOLERANCE`; it does not estimate weights or invent a fallback ([`allocation.py`](../../src/task_decomposition/domain/allocation.py:18-45)).

When `baseline_effort` is supplied, the same raw weights allocate compatible absolute values. When it is absent, the normalized `weight_ratio` remains the available baseline quantity. The measured parent effort is not sent to the operational provider: [`stage_payload()`](../../src/task_decomposition/providers/_shared.py:56-65) serializes only the task and task context for that stage.

### 3.2 Normalized transformation path

`estimate_transformation()` is an opt-in normalized bridge. It:

1. runs RETAIN/REMOVE classification and added-work proposal stages;
2. reads the completed `BaselineEffortAllocation` rows;
3. creates 100-unit per-subtask display estimates;
4. builds `NormalizedAccountingInput` from retained and removed ratios;
5. resolves added support work in `AUTO` mode; and
6. reuses the staged handoff and canonical accounting.

The implementation is in [`normalized_estimation.py`](../../src/task_decomposition/application/normalized_estimation.py:38-158). The per-subtask display quantity is:

```text
baseline_work_units_i = weight_ratio_i × 100
```

The current implementation accepts allocator rounding within the shared `DEFAULT_TOLERANCE` before handing ratios to canonical accounting.

### 3.3 Added/support-work path

Transformation orchestration runs classification, applies frozen baseline allocations to classification rows, validates added-work rows, resolves support work, and then calls the staged accounting handoff ([`transformation_decomposition.py`](../../src/task_decomposition/application/transformation_decomposition.py:60-139)).

For a baseline subtask reference, the resolver uses typical values:

```text
reference_effort_per_occurrence
    = reference_baseline_effort / reference_occurrences_per_parent_execution

added_support_work
    = occurrences_per_parent_execution
      × relative_effort_per_occurrence
      × reference_effort_per_occurrence
```

The exact implementation is [`added_work_estimation.py`](../../src/task_decomposition/application/added_work_estimation.py:69-100). Rows are summed by `AI_INTERACTION` and `AI_VERIFICATION` before accounting. The row-level proposals remain in `TransformationDecompositionResult`, but the canonical accounting input contains the category totals.

### 3.4 Canonical accounting path

The accounting domain owns the formulas:

```text
W0 = retained_human_work + gross_removed_work
W1 = retained_human_work + resolved_support_work
```

In normalized mode, `W0 = 1.0`; support contributions retain their explicit ratio basis. The domain computes `added_human_work`, net remaining work, substitution/augmentation metrics, and effect classification ([`accounting.py`](../../src/task_decomposition/domain/accounting.py:108-168)).

The staged pipeline is a validator/router, not a competing calculator ([`staged_pipeline.py`](../../src/task_decomposition/application/staged_pipeline.py:26-65)).

## 4. Estimation Semantics

### 4.1 Baseline semantics

The prompt defines a relative baseline estimate as:

```text
expected baseline effort per parent task
    = typical occurrences per parent task
      × relative human effort per occurrence
```

The resulting provider value is not stored with a unit or time basis. It is interpreted by the application as a share of aggregate baseline human effort, then normalized relative to sibling subtasks. This is documented in [`DECOMPOSITION_MODEL.md`](../reference/DECOMPOSITION_MODEL.md:3-11) and the existing baseline audit ([`baseline-effort-weighting.md`](baseline-effort-weighting.md:244-266)).

The implementation does not separately represent:

- occurrence frequency;
- per-occurrence duration or effort;
- parent-task workload volume;
- case mix or exception rates;
- active work versus elapsed waiting time; or
- uncertainty around the baseline weight.

Those concepts are requested in prompt prose and rationale, but they are not typed inputs. The prompt explicitly says not to require absolute minutes, hours, or workload volumes ([`prompts.py`](../../src/task_decomposition/providers/prompts.py:33-41)).

### 4.2 Parent-task volume and double counting

The only typed parent effort field is optional `TaskDecompositionRequest.baseline_effort`. It is a measured parent effort quantity used to materialize absolute allocations, not a workload-volume field ([`provider.py`](../../src/task_decomposition/contracts/provider.py:26-35)).

The current implementation therefore has no independent volume multiplier. Volume can only enter indirectly through the provider's relative weights or free-text rationale. This avoids an application-level second multiplication, but it also means the system cannot determine whether a provider has already included volume in a weight or occurrence assumption.

For added work, occurrences are explicitly multiplied by relative effort and the reference anchor. There is no additional volume multiplication in Python. The design is semantically consistent if `occurrences_per_parent_execution` already represents all conditional/repeated occurrences for one parent task. It is ambiguous when a provider's occurrence estimate and rationale both include workload volume.

### 4.3 Units and time bases

Absolute `EffortQuantity` values require an `EffortUnit` and `TimeBasis`, and the accounting layer checks compatibility before arithmetic ([`effort.py`](../../src/task_decomposition/contracts/effort.py:46-72), [`accounting.py`](../../src/task_decomposition/domain/accounting.py:171-220)).

Normalized baseline ratios and `NORMALIZED_CONTRIBUTION` support values are dimensionless baseline-relative quantities. Absolute support cannot be used in normalized accounting; the contract rejects incompatible bases ([`effort.py`](../../src/task_decomposition/contracts/effort.py:185-223)).

The synthetic normalized baseline uses `EffortUnit.EFFORT` and `PER_OPERATION` internally, but the resulting normalized ratios are not reported as hours or productivity. The notebook and application documentation correctly describe them as comparative units.

### 4.4 Competing estimation semantics

There are two intentionally different estimation domains:

| Path | Quantity | Formula/behavior |
| --- | --- | --- |
| Baseline task decomposition | Relative share of total baseline human effort | Provider proposes raw weights; Python normalizes by their sum |
| Added transformation work | New support effort | Occurrences × relative effort × reference per-occurrence anchor |

They should not be merged. The main consistency risk is that baseline weights are decomposition-relative while added-work references may select one baseline subtask. Changing the decomposition changes the reference anchor and can change the added-work result even when the parent task description is unchanged.

## 5. Assumption Handling

### 5.1 Baseline assumptions

The operational prompt asks each rationale to explain frequency, effort-per-occurrence, complexity, coordination, information availability, and conditional work, and to distinguish supplied facts from model assumptions ([`prompts.py`](../../src/task_decomposition/providers/prompts.py:43-50)).

The semantic rubric reviews whether those assumptions are transparent and directionally consistent with relative weights, but it does not require absolute measurements, numeric ranges, external evidence, or citations ([`rubric.py`](../../src/task_decomposition/evaluation/rubric.py:21-26)).

The baseline contract stores only:

- `relative_effort_weight`;
- free-text `effort_rationale`; and
- optional `provenance_refs`.

There is no structured `estimate_basis`, confidence/range, occurrence field, volume field, or per-assumption provenance for baseline work ([`stages.py`](../../src/task_decomposition/contracts/stages.py:29-40)).

### 5.2 Transformation assumptions

Added-work estimates have stronger structure:

- low/typical/high occurrence range;
- low/typical/high relative effort range;
- optional reference occurrence range;
- baseline or external reference;
- rationale;
- `estimate_basis` of `measured`, `documented`, or `assumed`; and
- optional provenance references.

See [`stages.py`](../../src/task_decomposition/contracts/stages.py:151-210). The application currently uses the `typical` value for each range in final accounting. Low/high values are retained as provider output but are not propagated into a low/high canonical accounting result.

### 5.3 Fact/assumption/default/unknown distinction

| Information type | Current representation | Assessment |
| --- | --- | --- |
| User/host-supplied fact | Task description, task context, optional measured baseline, explicit accounting input | Typed in parts; operational facts remain natural language |
| LLM-inferred assumption | Baseline `effort_rationale`; added-work `rationale`, ranges, and `estimate_basis` | Explicit in prose/metadata, not independently structured for baseline work |
| System default | `W0 = 1.0` normalization, 100-unit display scale, `DEFAULT_TOLERANCE`, support mode defaults | Deterministic and documented, but distinct from domain assumptions |
| Unknown/missing information | Often represented by a model assumption or omitted optional field | No uniform unknown marker or completeness status |

Provider provenance identifies provider/model/stage/request and portable references, but it does not attach evidence to an individual weight or assumption ([`provenance.py`](../../src/task_decomposition/contracts/provenance.py:23-32)). Tracing can preserve provider messages, responses, and validation events when enabled, but tracing is operationally optional and is not part of the returned estimation contract ([`tracing.py`](../../src/task_decomposition/tracing.py:293-328)).

## 6. Findings

| ID | Classification | Severity | Finding and evidence | Practical impact | Minimal correction |
| --- | --- | --- | --- | --- | --- |
| F-01 | Documentation gap | Medium | The canonical docs describe normalized relative effort, but do not fully define whether “occurrence” means frequency, repetition, probability, or workload volume. The prompt mentions all of these concepts without typed fields ([`DECOMPOSITION_MODEL.md`](../reference/DECOMPOSITION_MODEL.md:7), [`prompts.py`](../../src/task_decomposition/providers/prompts.py:33-40)). | Different providers can satisfy the same contract using different denominators or hidden volume assumptions. | Clarify the parent-task execution basis and occurrence meaning in the canonical reference documentation during a later documentation phase. |
| F-02 | Semantic ambiguity | High | Baseline relative weights are dimensionless sibling shares, while the target effort formula refers to per-occurrence effort and expected occurrences. No structured baseline occurrence, per-occurrence effort, or volume fields exist ([`stages.py`](../../src/task_decomposition/contracts/stages.py:29-40)). | The output is comparable within one decomposition, but cannot independently demonstrate that a weight follows the proposed formula. | First clarify semantics and require explicit rationale conventions; add schema fields only if prose proves insufficient. |
| F-03 | Potential risk | High | Parent workload volume is not represented separately. The provider may encode volume in weights, occurrence assumptions, or both; application code cannot detect duplicate volume treatment. | Relative weights may be directionally inconsistent or unstable across cases with different volumes/case mix. | Establish one parent-task workload basis and test representative repeated/conditional workloads before adding a volume field. |
| F-04 | Documentation gap | Medium | Baseline assumptions are stored mainly as free-text `effort_rationale`; baseline has no `estimate_basis`, uncertainty range, or structured distinction between fact, inference, default, and unknown. Added work has stronger metadata ([`stages.py`](../../src/task_decomposition/contracts/stages.py:184-210)). | Consumers cannot reliably filter assumed versus measured baseline estimates or reconstruct which assumption drove a weight. | Reuse existing rationale/provenance first; define the minimum needed metadata before changing the public schema. |
| F-05 | Semantic ambiguity | Medium | Added-work estimates retain low/typical/high ranges, but `_derive_estimates()` uses only typical values for accounting ([`added_work_estimation.py`](../../src/task_decomposition/application/added_work_estimation.py:77-100)). | Users may interpret the stored range as an accounted uncertainty interval when the canonical result is only a typical point estimate. | Document “typical-only accounting” explicitly or define a separate range-reporting requirement; do not silently average or select another value. |
| F-06 | Potential risk | High | Added-work baseline references are selected by the provider and use a decomposition-relative baseline share. Equivalent parent tasks with different valid decompositions can produce different support estimates. | Results may vary because of decomposition granularity/reference choice rather than actual transformed work. | Require a stable semantic reference policy or an explicit external anchor for use cases needing cross-decomposition comparability. |
| F-07 | Confirmed behavior / boundary risk | Medium | Baseline weights are provider-generated and normalization is deterministic; semantic evaluation checks plausibility but does not recompute or calibrate the weights ([`task_decomposition.py`](../../src/task_decomposition/application/task_decomposition.py:255-288), [`rubric.py`](../../src/task_decomposition/evaluation/rubric.py:21-26)). | There is no authoritative evidence that a numeric proportion is calibrated; acceptance means transparent/directionally coherent, not measured. | Preserve provider ownership and deterministic normalization; improve calibration guidance/tests rather than adding an application-side estimator. |
| F-08 | Confirmed design limitation | Low | The optional measured `baseline_effort` materializes absolute allocations but is not provided to the operational provider ([`provider.py`](../../src/task_decomposition/contracts/provider.py:26-35), [`_shared.py`](../../src/task_decomposition/providers/_shared.py:56-65)). | The provider cannot use the measured parent effort to calibrate its relative weight proposal; this is appropriate for ratio semantics but should be explicit. | Document that measured effort is an application-side materialization input, not provider evidence. |
| F-09 | Confirmed behavior | Low | There is one deterministic baseline allocation path, but `provider_service.py` duplicates provider-stage helper behavior as noted by the application README ([`application/README.md`](../../src/task_decomposition/application/README.md:27-49)). | Maintenance divergence could eventually produce inconsistent validation/tracing, although no estimation arithmetic divergence was found. | Reuse the shared helper in a later maintenance change; do not create another estimation path. |
| F-10 | Potential risk | Medium | Provenance is stage/provider-level. Free-text rationales and returned ranges are preserved, but there is no structured trace record of the final per-row baseline calculation or added-work contribution. | Historical audits may require reconstructing calculations from raw results and may not know whether a fact was supplied or inferred. | Add diagnostic/reporting data only after confirming consumer need; reuse existing result fields and tracing rather than adding parallel accounting. |

No confirmed arithmetic defect was found in the canonical W0/W1 accounting or the added-work resolver. Both are deterministic, check units/bases where required, and have focused mathematical tests. The findings above concern semantic definition, calibration, provenance, and comparability unless explicitly labeled otherwise.

## 7. Recommended Changes

The minimal improvement direction is:

1. Define baseline `relative_effort_weight` as a share of active human effort per one parent-task execution. State that conditional frequency belongs in the expected effort estimate and that parent workload volume must not also be multiplied elsewhere.
2. Keep provider-generated weights as the canonical allocation source and keep `allocate_effort()` as the only deterministic normalization utility.
3. Strengthen the existing prompt/rubric with a small calibration vocabulary: typical occurrence basis, conditional frequency, case mix, information availability, and active effort versus waiting time.
4. Make the distinction between fact, model assumption, system default, and unknown visible in the output/reporting path using existing rationale and provenance first.
5. Treat added-work low/typical/high values as an explicit reporting choice: either document that accounting uses typical values or add a separate, non-authoritative uncertainty presentation later.
6. For cross-decomposition comparability, prefer a stable semantic or external reference rather than inventing a fixed default ratio.
7. Add known-answer tests for conditional occurrences, repeated activities, parent-volume conventions, unit/time-basis boundaries, and reference-anchor stability.

Avoid introducing a separate public allocation stage, equal-effort fallback, host-weight alternative, scenario/simulation orchestration, or duplicate accounting formulas. Those would conflict with the current ownership model.

## 8. Implementation Plan

### Phase A — semantic decision, no schema change

- Confirm the parent-task execution basis for baseline weights.
- Decide whether “occurrence” is a conditional count/probability per parent execution and where workload volume is represented.
- Decide whether exceptions belong in subtask boundaries, occurrence assumptions, or both without double counting.
- Define the meaning of `typical` in final added-work accounting.

### Phase B — minimal prompt/rubric and observability refinement

- Update the operational prompt only after the semantic decisions are approved.
- Reuse `effort_rationale` and existing semantic evaluation rather than adding a second estimator.
- If required, add a compact diagnostic representation of calculation inputs and contributions without changing canonical W0/W1 formulas.
- Preserve provider parity and untrusted-output validation.

### Phase C — focused regression coverage

- Test provider raw weights against deterministic normalized allocations.
- Test repeated/conditional activities under the selected parent-volume basis.
- Test that volume is not applied twice.
- Test baseline and absolute materialization remain scale-equivalent.
- Test added-work occurrence/reference calculations and category aggregation.
- Test unit/time-basis incompatibility and zero/unknown behavior.
- Test that estimates remain traceable to source assumptions and provider provenance where the existing contract supports it.

### Phase D — canonical documentation follow-up

After implementation decisions are approved, update only the appropriate canonical documents:

- `docs/reference/DECOMPOSITION_MODEL.md`: stable semantics;
- `src/task_decomposition/application/README.md`: implementation ownership;
- root `README.md`: navigation only.

This audit remains the historical record of the findings and resolution.

## 9. Validation Requirements

Before implementation is considered complete, verify:

- `pytest` passes, including new known-answer estimation tests;
- `ruff check src tests` passes;
- `ruff format --check src tests` passes;
- `python -m compileall -q src` passes;
- `git diff --check` passes;
- no credentials or live provider calls are required by the new tests;
- provider parity remains intact;
- normalized and absolute paths retain compatible units and denominators;
- `W0 = retained + gross_removed` and `W1 = retained + resolved_support` remain the only canonical accounting relationships;
- baseline allocations still originate from provider-generated relative weights;
- transformation decomposition still consumes an existing `TaskDecomposition`;
- low/typical/high reporting semantics are explicit and not confused with canonical point accounting;
- provenance and assumptions are sufficient to reconstruct a representative estimate without relying on undocumented defaults.

## 10. Resolution Status

**Phase 2 implementation complete; follow-up items remain open.**

Confirmed current state:

- one canonical deterministic baseline normalization path;
- one separate deterministic added-work resolution path;
- canonical W0/W1 formulas centralized in `domain/accounting.py`;
- baseline assumptions primarily represented in provider rationale prose;
- added-work estimates have more structured ranges/basis/reference metadata;
- no independent parent-volume or baseline occurrence model;
- no confirmed canonical accounting arithmetic defect found in this audit.

Open decisions for the next phase are the exact parent-task/occurrence semantics, volume ownership, typical-versus-range reporting, and the minimum traceability needed by consumers. No production, schema, test, or existing documentation changes are authorized by this audit phase.

### Phase 2 resolution tracking

The following audit findings were addressed in Phase 2:

- F-01: parent output and occurrence semantics are now explicit in the operational prompt and canonical decomposition reference.
- F-02: expected occurrences, active effort per occurrence, expected effort per parent output, and relative allocation semantics are now stated together.
- F-03: internal workload is explicitly included once, while external parent output volume is assigned to downstream workload/capacity systems.
- F-04: prompt and rubric guidance now require material assumptions and the distinction between supplied facts and inferred assumptions; no new schema was added.
- F-07 and F-08: provider-generated relative weights, deterministic normalization, and optional measured absolute materialization remain the stated ownership boundary.

Files modified in Phase 2:

- `src/task_decomposition/providers/prompts.py`
- `src/task_decomposition/evaluation/rubric.py`
- `docs/reference/DECOMPOSITION_MODEL.md`
- `tests/test_evaluation_contracts.py`
- `tests/test_added_work_estimation.py`
- this audit file

Focused tests were added for zero/fractional/one/repeated added-work occurrences and rubric coverage. Existing normalized and absolute allocation, unit/time-basis, and transformation support-work tests remain the validation coverage for the unchanged contracts and accounting path.

Remaining open findings:

- F-05 remains open: added-work ranges are preserved, but canonical accounting intentionally continues to use typical values only.
- F-06 remains open: provider-selected baseline references can vary with decomposition granularity; no arbitrary default ratio was introduced.
- F-09 remains open: provider-service helper duplication is unrelated to the semantic change and was not refactored.
- F-10 remains open: stage-level provenance and existing tracing remain in place, but no new per-row calculation trace schema was added.

Deferred integration considerations: downstream systems may combine absolute effort per parent output with resource capacity and labor-calendar data, but this repository does not add a runtime dependency, resource-capacity model, FTE logic, external workload volume, or throughput calculation.

Validation results: the full `pytest -q` suite passed with 304 tests passed and 6 skipped. Changed-file Ruff checks and formatting checks passed. Source compilation via read-only `compile()` checks passed. Repository-wide `ruff check src tests` remains non-zero because of 64 pre-existing findings outside the changed files; repository-wide `ruff format --check src tests` remains non-zero because `src/task_decomposition/providers/_shared.py` is pre-existingly unformatted. The requested `python -m compileall -q src` command was attempted but could not overwrite pre-existing permission-restricted `__pycache__` files; no source compilation errors were reported by the read-only compile check. `git diff --check` passed.

### Phase 3 resolution tracking

Phase 3 addressed the auditability gap identified in F-10 without changing estimation behavior, reference selection, provider prompts, baseline allocation, or canonical W0/W1 accounting. The resolver now retains one `AddedWorkEstimateDetail` per computable added-work row and the transformation result exposes those details. Each detail carries the proposal identity and category, parent-output occurrence range, relative effort-per-occurrence range, reference source and identity, reference effort and occurrence range where available, derived reference effort per occurrence, calculated added effort, estimate basis, rationale, and provenance.

The existing resolver remains the calculation owner. The new detail values are built from the same occurrence, relative-effort, reference, and accounting-input values used for support-work resolution. Existing `resolve_support_work` callers retain the original two-value return contract; the detail-aware resolver is used by transformation orchestration to populate the result field. Host-selected support work can still have no per-row calculated details, and the notebook explicitly reports that limitation rather than inventing values.

The evaluation notebook now renders an added-work calculation table with explicit parent-output denominators, typical values plus low/high ranges, normalized-versus-absolute quantity metadata, references, assumptions, rationale, and provenance. It also renders reconciliation lines using canonical category support-work outputs and canonical W1. Normalized values remain explicitly identified as baseline-relative units and are not presented as time or capacity.

Files modified in Phase 3:

- `src/task_decomposition/contracts/stages.py`
- `src/task_decomposition/contracts/__init__.py`
- `src/task_decomposition/__init__.py`
- `src/task_decomposition/application/added_work_estimation.py`
- `src/task_decomposition/application/transformation_decomposition.py`
- `notebooks/task_decomposition_end_to_end.ipynb`
- `tests/test_added_work_estimation.py`
- this audit file

Remaining findings: F-05 remains open because canonical accounting intentionally uses typical values rather than changing point-accounting semantics to ranges. F-06 remains open because decomposition-specific reference anchors can vary with baseline granularity. F-09 remains unrelated and open. F-10 is addressed for transformation results and notebook reporting, while host-supplied support work and broader provider tracing remain limited by existing contracts.

Phase 3 validation: focused added-work, normalized-estimation, and provider-application tests passed (`26 passed`); the full suite passed (`304 passed, 6 skipped`). Changed-file lint, formatting, read-only source compilation, notebook JSON/code compilation, and `git diff --check` passed. Repository-wide lint, repository-wide format checking, and `compileall` retain the pre-existing failures described above.

## Phase 4 — Input/Output Contract and Invariant Audit

### Scope and evidence

This phase is a read-only architectural and semantic audit. It does not change production code, contracts, prompts, tests, or canonical documentation. The current implementation, existing effort audit, decomposition/accounting references, focused tests, notebook renderer, and the accessible read-only AgenticAICompass checkout were inspected. The current working tree already contains unrelated user changes in the notebook/output artifact and notebook-rendering regression test; they were preserved.

### Current pipeline and ownership map

| Stage | Input | Work and owner | Output | Accounting authority |
| --- | --- | --- | --- | --- |
| Parent task to subtasks | `TaskDecompositionRequest.task`, `task_context`, optional `baseline_effort` | Provider proposes operational subtasks; application validates and evaluates them | `OperationalDecomposition` and `OperationalSubtask` rows | No accounting yet |
| Subtasks to baseline allocation | Provider `relative_effort_weight` values | `decompose_task()` calls `_allocate_baseline()`; `domain.allocation.allocate_effort()` normalizes deterministically | `BaselineEffortAllocation.weight_ratio`, optional absolute `effort` | `allocate_effort()` for allocation only |
| Baseline to transformation facts | Existing frozen `TaskDecomposition` | Transformation provider classifies each subtask `RETAIN`/`REMOVE` and proposes added work; validators enforce identity, coverage, and causal removed sources | `RetainRemoveClassification`, `AddedWorkClassification` | No provider arithmetic |
| Removed work to added work | Added-work rows with occurrence/relative-effort ranges and references | `resolve_support_work_with_details()` uses typical values and resolves category totals | `SupportWorkInputs`, `SupportWorkResolution`, `AddedWorkEstimateDetail` | Resolver owns support-work estimation; it does not calculate W0/W1 |
| Retained plus added work to W0/W1 | Normalized or absolute accounting input plus resolved support | `_run_staged_pipeline()` validates the handoff and delegates to `account_normalized()` or `account_absolute()` | `CanonicalTransformationImpact` with W0, W1, ratios, multiplier, effect | `src/task_decomposition/domain/accounting.py` is the sole W0/W1 authority |
| Optional downstream integration | Absolute result when supplied; normalized result otherwise | Host adapter projects results into downstream review/capacity systems | External persistence, staffing, capacity, or throughput models | Outside this repository |

The end-to-end composition in `provider_service.py` is convenience orchestration only. Transformation decomposition consumes an existing baseline and does not regenerate it. Providers propose semantic facts; application code resolves inputs and routes them; domain code computes canonical accounting.

### Quantity and contract inventory

| Contract/field | Quantity and denominator | Unit/dimension | Status, provenance, validation, consumers |
| --- | --- | --- | --- |
| `OperationalSubtask.relative_effort_weight` | Raw provider estimate of one subtask's share of aggregate baseline human effort; numerator is the subtask contribution and denominator is the sibling-task aggregate | Dimensionless; arbitrary positive scale | Provider input, validated as positive and complete across rows when present; rationale/provenance are available; consumed only by `_allocate_baseline()` |
| `BaselineEffortAllocation.weight_ratio` | Normalized baseline share: raw weight divided by the sum of raw weights | Dimensionless fraction of W0 | Application-derived; `allocate_effort()` checks positive weights and allocation reconciliation; consumed by normalized transformation and downstream adapters |
| `BaselineEffortAllocation.effort` | Absolute allocation of the optional measured parent baseline | `EffortQuantity` unit plus time basis | Application-derived only when `TaskDecompositionRequest.baseline_effort` exists; allocation preserves unit/time basis; consumed by absolute transformation handoff |
| `NormalizedWorkEstimate.baseline_work_units` | Display quantity `weight_ratio × 100` for one parent execution; 100 is a reporting scale, not a measured workload | Normalized baseline-relative units | Derived in `normalized_estimation.py`; retained and removed fields partition the 100 display units; notebook reports the non-time meaning |
| `AddedWorkEstimate.occurrences_per_parent_execution` | Expected executions of one added activity per parent output; typical is used for point accounting | Nonnegative dimensionless occurrence count | Provider input, `EstimateRange` enforces finite ordered nonnegative values; stored in detail and consumed by resolver |
| `AddedWorkEstimate.relative_effort_per_occurrence` | Relative effort multiplier for one occurrence against the selected reference effort per occurrence | Dimensionless multiplier | Provider input, finite ordered nonnegative range; typical is used by resolver; no absolute unit is implied |
| `AddedWorkEstimate.reference_occurrences_per_parent_execution` | Expected occurrences of the referenced baseline activity per parent output, used to derive its per-occurrence anchor | Nonnegative occurrence count; baseline reference must be present, and resolver requires typical > 0 | Provider input and validator requirement for baseline references; consumed by resolver |
| `AddedWorkEstimateDetail.reference_effort` | The actual referenced aggregate baseline effort used by the resolver, or unavailable for an external reference | Absolute `EffortQuantity` or normalized `SupportWorkInput` | Resolver-derived from the classification/allocation; not independently reconstructed by the notebook; reporting/result consumer |
| `AddedWorkEstimateDetail.reference_effort_per_occurrence` | `reference_effort / reference_occurrences` for baseline references, or the supplied external anchor | Absolute or baseline-relative support quantity | Resolver-derived actual anchor; carries unit/time basis for absolute mode or explicit `RatioBasis` for normalized mode |
| `AddedWorkEstimateDetail.calculated_added_effort` | Expected added effort per parent output for one row | Absolute support effort or normalized contribution | Resolver-derived using typical operands; category aggregation consumes its value; notebook reports it |
| `EffortQuantity` | Nonnegative amount of human effort over its declared operation/period | `EffortUnit` plus `TimeBasis` | Absolute contract; finite/nonnegative validation and unit/time compatibility are enforced by accounting/allocation; does not identify the parent output name |
| `SupportWorkInput` | Added post-transformation support contribution whose meaning is selected by `RatioBasis` | Dimensionless ratio/contribution, or absolute effort with unit/time metadata | Explicit basis required; absolute metadata is validated; accounting converts only according to the declared basis |
| `NormalizedAccountingInput.retained_work_ratio` / `gross_removed_work_ratio` | Retained and gross-removed portions of W0 = 1 | Dimensionless fractions | Application-derived or host-supplied; canonical accounting requires the partition within tolerance |
| `AbsoluteEffortInput.baseline_human_effort` | Total original baseline W0, not an additive row | Absolute effort with unit/time basis | Host/application input; accounting requires positive W0 and compatible quantities |
| `CanonicalTransformationImpact.w0` / `w1` | Original baseline and post-transformation human effort; W1 includes retained baseline plus resolved support | Absolute amount in absolute mode, ratio-scale value in normalized mode | Domain-derived output; W0/W1 and all ratios/effect fields are canonical outputs |

The closest implementation of `reference_baseline_effort` is not a field with that name. For a baseline reference, `_baseline_effort()` reads `ClassifiedSubtask.effort` in absolute mode or `ClassifiedSubtask.baseline_effort_ratio` in normalized mode. `AddedWorkEstimateDetail.reference_effort` exposes that actual value after resolution. The same distinction applies to `normalized_effort`: the public model uses `NormalizedWorkEstimate.baseline_work_units`, while `BaselineEffortAllocation.weight_ratio` is the canonical dimensionless share.

### Candidate invariant compliance matrix

| # | Candidate invariant | Status | Evidence and interpretation |
| --- | --- | --- | --- |
| 1 | Every parent task has an explicit or unambiguous output unit | Documented only | The reference documentation and prompts describe one parent-task execution, but `TaskReference` has no `work_unit` field. The output unit remains implicit in task name/description and provider rationale. |
| 2 | All contributing effort uses the same parent output unit | Partially enforced | Added-work ranges explicitly say `per_parent_execution`; normalized baseline display is per task execution. Baseline `relative_effort_weight` and `EffortQuantity` do not carry the parent output identity, so the denominator is not structurally cross-checked. |
| 3 | Expected activity effort = occurrences × effort per occurrence | Partially enforced | Added-work resolution deterministically multiplies typical occurrences, relative effort per occurrence, and the reference per-occurrence anchor. Baseline decomposition stores only a raw relative share and rationale, so its operands are not independently enforced. |
| 4 | Occurrences are nonnegative and may be fractional or >1 | Partially enforced | `EstimateRange` enforces nonnegative finite ordered values and tests cover fractional/repeated support. Baseline subtasks have no typed occurrence field; baseline occurrence semantics remain prose. |
| 5 | Normalized baseline shares sum to one | Enforced at canonical paths | `allocate_effort()` normalizes and reconciles; normalized transformation rejects a partition outside `DEFAULT_TOLERANCE`; `account_normalized()` repeats the partition check. `BaselineEffortAllocation` alone permits individually valid ratios that do not sum to one, so this is not a standalone model invariant. |
| 6 | Raw provider weights are not automatically absolute effort | Enforced by application semantics | Provider weights are normalized to `weight_ratio`; absolute effort is materialized only from optional measured `baseline_effort`. Tests cover both relative-only and measured allocation. |
| 7 | W0 = retained baseline work + gross removed work | Enforced | `account_absolute()`, `account_normalized()`, and staged handoff validation enforce the partition; accounting tests cover known answers and invalid partitions. |
| 8 | W1 = retained baseline work + added human work | Enforced | `account_absolute()` and `account_normalized()` compute W1 from retained plus resolved interaction/verification support; gross removal is excluded from W1. |
| 9 | Absolute and normalized effort are not mixed without conversion | Enforced at accounting boundaries | Absolute quantities require compatible unit/time bases; normalized accounting rejects absolute support; explicit ratio bases define normalized conversion. The parent output name still is not typed. |
| 10 | Internal workload volume is counted once | Documented only | Prompts/docs assign internal workload to occurrence or per-occurrence effort, and application code has no second volume multiplier. No typed volume or provenance proves whether the provider already included it. |
| 11 | Resource availability, FTEs, calendars, and throughput remain outside ownership | Enforced boundary | No resource-capacity model or capacity calculation exists in production imports. `EffortUnit.FTE` exists as an allowed effort label, which is a terminology risk, but no FTE/calendar logic is owned here. |
| 12 | Transformation reduction is not applied twice downstream | Partially enforced / downstream-owned | This package exposes gross removal, W1, and net ratios once and does not compute capacity. It cannot enforce how a downstream consumer combines substitution, augmentation, throughput, or staffing multipliers. Consumer adapter review is required. |

These statuses distinguish semantic guarantees from runtime checks. For example, W0/W1 are runtime-enforced equations, while the parent output unit and internal-volume convention are currently documentation/provider responsibilities.

### Input/output boundary analysis

The parent output unit is conceptually one execution of the task, but it is not a first-class contract field. Native subtask units are also not first-class: document, request, claim, and escalation are represented in descriptions/rationales, while `EffortUnit` describes effort rather than the work output. `TimeBasis.PER_OPERATION` can preserve an execution basis for absolute effort but does not say which operation or output unit it refers to.

Expected occurrences and human effort per occurrence are explicit only for added-work estimates. Baseline decomposition has one dimensionless provider weight plus rationale. Absolute effort per parent output is representable when the host supplies `EffortQuantity` with an appropriate time basis, but the contract cannot independently distinguish “hours per claim” from “hours per generic operation” without host context. Relative allocation is explicit and stable within a frozen decomposition; absolute calibration is optional and application-owned. Transformation effects are explicit through classification, added support categories, W0/W1, and derived ratios.

No workflow execution, arrival rate, queueing, staffing, capacity conversion, or external workload volume is represented in the task-decomposition contracts. That boundary is consistent with the stated ownership model.

### AgenticAICompass compatibility assessment

The accessible checkout at `/home/xzhang/dev/AgenticAICompass` was inspected read-only. Its capacity semantics define a work/output unit such as claim or ticket, a time basis for output rates, and separate resource facts such as human FTE/hours. It explicitly distinguishes capacity from realized throughput and treats FTE fields as planning projections rather than foundational compute truth (`docs/invariants/capacity-semantics.md`). This is conceptually compatible with task-decomposition's relative baseline and optional absolute effort boundary.

The conceptual mapping is:

| AgenticAICompass concept | Task-decomposition counterpart | Compatibility |
| --- | --- | --- |
| `work_unit` | `TaskReference` name/description plus host interpretation | Conceptual only; no typed work-unit field |
| `effort_per_unit` | Absolute `EffortQuantity` materialized from measured parent effort, or normalized W0-relative values | Compatible only when host supplies the parent output interpretation and absolute calibration |
| `effort_time_unit` | `EffortQuantity.unit` and `TimeBasis` | Similar but not identical; `EffortUnit` includes generic `EFFORT` and `FTE`, and `TimeBasis` mixes per-operation and calendar periods |
| Resource capacity/FTE/calendar | No task-decomposition contract | Correctly outside ownership |
| Baseline/post-AI effort | `CanonicalTransformationImpact.w0` and `w1` | Direct semantic match for effort requirement; not itself a capacity or throughput result |

Code-level compatibility is not fully verified. The accessible AgenticAICompass adapter imports the canonical task-decomposition API, requires absolute accounting for its current persistence projection, and stores the standalone result in provider metadata. However, the inspected adapter still references legacy result attributes such as `operational_support_work`, `governance_work`, and `lifecycle_support_work`, which are not fields on the current `CanonicalTransformationImpact`; this is a confirmed downstream-version/schema mismatch in the checked-out consumer, not a defect to fix in this audit. The external repository has pre-existing changes and remains outside this repository's modification scope.

The principal double-counting risk is downstream: a consumer must not apply task-decomposition's `net_substitution_ratio` or `w1` reduction and then independently apply the same transformation reduction again in a capacity/augmentation multiplier. AgenticAICompass documentation describes separate substitution and augmentation/throughput paths, so the integration must choose one authoritative transformed human-effort input and document any subsequent capacity conversion.

### Prioritized findings

| ID | Category | Priority | Evidence and impact | Recommended canonical interpretation | Smallest viable change | Compatibility risk |
| --- | --- | --- | --- | --- | --- | --- |
| IO-01 | Unit/denominator ambiguity | High | `TaskReference` has no output-unit field; `EffortQuantity.PER_OPERATION` does not identify the operation. Baseline and transformation values can therefore share an implicit denominator without runtime proof. | One parent task execution equals one named parent output; all relative/absolute effort is per that output. | Document the host obligation to provide the output-unit interpretation; consider a future optional field only after consumer evidence. | Adding a required field would break provider/request schemas. |
| IO-02 | Duplicated/ambiguous semantics | High | Baseline weights encode aggregate sibling shares, while added-work estimates encode occurrence and per-occurrence reference calculations. Baseline occurrence/per-occurrence operands are not typed. | Keep baseline relative weights as the first-stage representation; treat the formula as semantic guidance, not a reconstructible baseline calculation. | Clarify terminology in canonical docs and evaluator guidance; do not add parallel estimation fields yet. | Low if documentation-only; high if schema changes. |
| IO-03 | Missing validation | High | No contract validates internal workload volume, parent-unit consistency, or whether rationale assumptions double-count workload. | Internal volume belongs once in expected per-parent effort; external volume belongs downstream. | Add evaluator/test cases for representative repeated/conditional work before adding fields. | Provider behavior may change if rubric becomes stricter. |
| IO-04 | Reference-anchor instability | High | Added-work baseline references use decomposition-relative effort and provider-selected reference subtasks. Granularity changes can change support estimates for the same parent task. | Reference anchors are valid local estimates, not cross-decomposition-stable measurements. | Require explicit external references for cross-decomposition comparisons; preserve current formula. | Changing reference policy could change reported W1. |
| IO-05 | Integration-boundary mismatch | High | AgenticAICompass adapter code still accesses legacy support-category attributes absent from the current accounting result. | Downstream adapters must consume current `ai_interaction_work`, `ai_verification_work`, `added_human_work`, W0/W1, and explicit units, or own an explicit compatibility projection. | Coordinate a consumer-side migration and run its adapter tests; no local shim. | Cross-repository API compatibility is affected. |
| IO-06 | Naming/ownership inconsistency | Medium | `EffortUnit` permits `FTE`, although resource capacity/FTE planning is outside this package. `TimeBasis` includes calendar periods as well as per-operation. | Absolute effort may use a host-selected unit/basis, but FTE capacity and calendars remain downstream concepts. | Document the boundary and audit consumers before narrowing enums. | Enum narrowing would be breaking. |
| IO-07 | Reporting-only issue | Medium | `AddedWorkEstimateDetail` exposes actual resolver operands, but baseline details remain only in allocation/rationale and `CanonicalTransformationImpact` aggregates category support. | Result reporting should distinguish raw weights, normalized shares, absolute effort, and support contributions. | Reuse existing detail/result fields in reports; avoid a second accounting representation. | Low. |
| IO-08 | Downstream double-counting risk | High | Task-decomposition returns gross removal, W1, and net ratios but does not own capacity; downstream systems can independently apply substitution/augmentation formulas. | Use W1/net human effort once as transformed effort requirement, then convert to capacity with external resource/time data. | Add an integration contract/test in the downstream owner, not here. | High if downstream semantics are changed without migration. |

### Minimal staged rationalization plan

1. Preserve the current contracts, provider prompts, deterministic allocation, added-work formula, and canonical W0/W1 accounting while adopting the interpretations above.
2. Update canonical documentation only if the project approves making “one parent execution/output unit” a stronger host contract obligation; do not imply a new runtime field from documentation alone.
3. Add semantic evaluation examples for conditional and repeated activities, internal workload counted once, passive waiting excluded, and relative-only versus absolute calibration. These should test direction and reconciliation, not invent absolute durations.
4. Coordinate the AgenticAICompass adapter migration separately. Confirm whether its current checkout is stale relative to the standalone result contract, then add a consumer-side known-answer test that maps current interaction/verification outputs exactly once.
5. If cross-decomposition stability becomes a requirement, choose an explicit external reference or stable parent-level calibration policy before changing reference selection. Do not introduce an arbitrary default ratio.
6. Only after evidence shows that prose/rationale is insufficient should the project consider a backward-compatible optional parent work-unit or structured baseline-assumption field. Any such change requires public export, provider, consumer, and serialization review.

### Deferred decisions

- Whether `TaskReference` should eventually carry an optional structured parent `work_unit`.
- Whether `EffortQuantity` should continue allowing `FTE` and calendar-period bases in this library or restrict those to downstream resource models.
- Whether baseline decomposition needs structured occurrence/per-occurrence inputs or should remain a relative-weight contract with rationale.
- Whether added-work ranges need a future range-accounting result rather than the current typical-only canonical point.
- Which downstream system owns prevention of applying both task-level transformation ratios and capacity/augmentation multipliers to the same work reduction.
- The exact consumer-side migration required for the checked-out AgenticAICompass adapter's legacy support-category attributes.

### Phase 4 resolution status

No production code, schemas, prompts, tests, or existing canonical documentation were changed. This phase adds evidence and interpretations to the historical audit only. The strongest confirmed gaps are the implicit parent output denominator, lack of typed baseline occurrence/per-occurrence operands, and the checked-out downstream adapter's legacy accounting-field references. No defect was found in the current deterministic allocation or W0/W1 formulas. Read-only validation should remain limited to inspection and the existing credential-free test suite; implementation work requires review of the findings above.

## Stage 1 — Effort Contract and Invariant Standardization

Stage 1 implemented the minimum contract-semantic clarification requested from the Phase 4 findings. Existing public contracts and formulas were preserved: baseline decomposition still produces provider-generated relative weights, `allocate_effort()` normalizes them once, transformation still consumes the frozen `TaskDecomposition`, and `domain/accounting.py` remains the sole W0/W1 authority.

Resolved findings and changes:

- F-01, F-02, and F-03: canonical documentation and provider guidance now consistently define one parent output per execution, expected occurrences (including conditional and repeated work), active effort per occurrence, internal workload counted once, and external output volume as downstream-owned.
- F-04 and F-07/F-08: rationale guidance distinguishes supplied facts from assumptions, rejects unsupported precision as measurement, and keeps relative weights dimensionless; no schema or absolute baseline-estimation field was added.
- F-05: documentation now states that added-work ranges are retained for traceability while canonical accounting uses typical values only.
- The rubric now flags parent-denominator inconsistencies, double-counting, passive waiting, normalized quantities presented as time/capacity, and unsupported precision without requiring absolute measurements.
- Focused known-answer tests cover conditional and repeated occurrences, relative-weight scale invariance, absolute calibration, normalized/absolute unit boundaries, and unchanged added-work/W0/W1 reconciliation.

Deferred findings:

- F-06 remains open: provider-selected decomposition-relative reference anchors can vary with decomposition granularity.
- F-09 remains open: provider-service helper duplication is unrelated to this focused semantic change.
- F-10 remains limited to the existing result details, stage-level provenance, and tracing; no new calculation-trace schema was introduced.
- The implicit parent output unit and baseline occurrence/per-occurrence operands remain documentation/provider responsibilities because adding public fields would change contracts and is outside this stage.

Stage 1 validation used deterministic, credential-free tests and did not change downstream integrations, capacity/resource semantics, reference-anchor selection, or accounting formulas.

## Phase 1 — Agentic Task Synthesis implementation record

The transformation pipeline now has an optional Agentic Task Synthesis stage between RETAIN/REMOVE classification and added-work proposal. It consumes the frozen baseline, validated classifications, and transformation request context, and exposes validated semantic `AgenticTask` definitions through `TransformationDecompositionResult.agentic_task_synthesis`.

The new contract contains a stable agentic task ID/name, responsibility description, replaced baseline subtask IDs, required inputs, and expected outputs. Deterministic validation enforces known source IDs, REMOVE-only scope, exactly-once coverage, nonempty responsibility/input/output fields, and the zero-REMOVE/zero-task case. Supported providers returning invalid synthesis output fail with the existing provider contract validation error; providers without the optional capability remain compatible and return `None`.

The stage does not alter baseline allocation, added-work formulas, reference selection, or W0/W1 accounting. Agentic tasks are semantic transformation artifacts rather than execution nodes, resource entries, or human-effort rows. The optional capability reuses the shared provider-stage infrastructure and prompt/schema handling; existing concrete adapters remain compatible without the capability. Deterministic tests cover grouping, exclusions, duplicate/unknown/missing mappings, zero removal, capability absence, pipeline ordering, and unchanged accounting.

## Phase 1B — Built-in provider enablement record

OpenAI, Gemini, and DeepSeek now implement the existing `AgenticTaskSynthesisProvider` capability. Each adapter uses its established structured-output path, shared synthesis prompt, model/token configuration, tracing, provenance, and parsing/error handling. The application still performs the authoritative deterministic mapping validation; no provider output is trusted as accounting.

Mocked provider tests cover synthesis invocation, schema parsing, provenance and stage ordering across all three adapters, while preserving identical added-work and W0/W1 results. External providers without the optional method remain compatible and continue to return `agentic_task_synthesis=None`.

## Phase 2 — Human–Agent Interaction Modeling implementation record

The pipeline now optionally models semantic human activities after agentic task synthesis and before added-work proposal. `HumanAgentActivity` records contain an activity identity/name, description, non-effort category, associated agentic task IDs, trigger, and expected human action. Deterministic validation enforces nonempty fields, unique activity IDs, known agentic-task references, and zero activities when synthesis contains no agentic tasks.

OpenAI, Gemini, and DeepSeek implement the optional modeling capability using their existing provider-stage infrastructure, shared prompt, structured parsing, token configuration, tracing, provenance, and error handling. External providers may omit the capability. Modeled activities are exposed in `TransformationDecompositionResult.human_agent_activity_modeling` but are not converted into added-work rows and do not affect W0/W1 or any effort estimate. Existing added-work proposals remain the sole quantitative source pending a later migration phase.

## Phase 3 — Activity-Based Human Effort Estimation implementation record

The optional activity-based path now follows human activities from semantic definitions to quantified per-parent-output effort. Built-in OpenAI, Gemini, and DeepSeek providers estimate expected occurrences and active effort per occurrence through a shared structured-output contract; application validation requires complete one-to-one activity coverage, compatible units, and the exact deterministic product. Conditional and repeated work is represented once through expected occurrences, and passive or autonomous processing is excluded.

For absolute accounting, supplied `baseline_human_effort` is the calibration basis. For normalized accounting, a provider-estimated positive baseline calibration with rationale is required; normalized weights are never interpreted as time. Activity estimates are converted to the existing support-work inputs, with exception handling mapped to interaction only at that accounting boundary. The activity path and legacy reference-based path are mutually exclusive, and selected-path validation failures are propagated. `domain/accounting.py` remains the sole W0/W1 authority; no formulas, classification, synthesis, or activity semantics were changed.

External providers without the complete optional capability remain on the legacy path. The remaining limitation is intentional: modeled activities are not yet a separate workflow or capacity model, and resource calendars, staffing, throughput, and demand remain downstream responsibilities.

## Phase 3 audit correction record

The observed claim-triage runs were traced through the activity-estimation response, normalized resolver, canonical accounting, and notebook projection. The repeated normalized W1 value is not caused by clipping, fallback, repeated normalization, or legacy/activity double counting: `domain/accounting.py` receives one retained baseline ratio and one resolved activity-support total and computes W1 once. The observations are consistent with provider outputs scaling both an estimated baseline calibration and activity effort by approximately the same factor. The checked-out code cannot establish whether that correlation is stochastic model behavior or prompt anchoring; it is not evidence of a deterministic accounting defect.

The scope defect was a semantic boundary gap in later-stage prompts. Although the original task description and baseline were supplied, synthesis, activity modeling, and effort estimation did not explicitly state that downstream roles and later decisions are context-only unless assigned to the parent task. Shared prompts and the existing semantic rubric now state that handoffs to downstream roles exclude later adjudication, final decisions, settlement, and later-process execution. No structural validator claims to prove semantic scope preservation.

The notebook previously read `support_work_resolution.estimated_support_work`, which is a legacy resolver diagnostic and is intentionally absent on activity-based results. It now displays activity-level estimates and category projections, explicit supplied-versus-estimated calibration rationale, and canonical W0/W1/reduction fields. The category projection is reporting-only; canonical accounting remains in the domain module.

## Phase 1 — Output-Based Baseline Effort Estimation implementation record

Baseline decomposition now optionally accepts an additive parent-output contract and
one bottom-up estimate per operational subtask. Each estimate uses expected
occurrences per parent output and active effort per occurrence; application code
converts compatible duration units, computes the product, totals the estimates, and
derives the existing relative weights. Provider-supplied products are validated
rather than treated as authoritative.

Built-in providers use the existing operational decomposition call and shared
structured-output infrastructure; no additional LLM call or transformation-stage
integration was introduced. Providers that return only relative weights remain
compatible, and callers are not required to provide the new parent-output metadata.
The task-decomposition result exposes the optional baseline estimate and parent
output contract, while W0/W1, transformation accounting, and workflow-capacity
semantics remain unchanged for the next phase.

## Phase 2 — Output-Based Baseline Effort Integration implementation record

Transformation calibration now uses explicit precedence: caller-supplied absolute
baseline effort, Phase 1 bottom-up baseline effort, then the existing provider
calibration fallback. The selected source is exposed as
`baseline_calibration_source`. Absolute transformations preserve bottom-up
subtask proportions and scale retained/removed effort to the authoritative
supplied baseline before the existing accounting handoff. Normalized activity
support uses the bottom-up total when available and converts compatible duration
units deterministically.

The activity estimator remains a single existing provider stage; it does not
receive a new call or a W1/W0 target, and any provider baseline returned when a
higher-precedence calibration exists is diagnostic only. `domain/accounting.py`
remains the sole W0/W1 authority. Legacy relative-only decompositions and
providers without optional capabilities retain their existing paths. Zero or
invalid calibration remains an explicit validation/error case rather than a
fabricated normalized result.
