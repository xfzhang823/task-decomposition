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
