# Behavioral Coverage Audit: CMP-001, CMP-005, and CMP-010

## Scope and method

This is a read-only behavioral audit of the three computational invariants identified in `docs/invariants/registry.yaml`:

- `CMP-001` — Baseline effort product
- `CMP-005` — Baseline accounting partition (W0)
- `CMP-010` — Bottom-up allocation precedence

The audit compared the registry with the implementation, contracts, reference documentation, and existing pytest assertions. It follows the canonical application path and also checks lower-level public utilities for bypasses. No production code, contracts, tests, registry records, or registry statuses were changed.

The full credential-free suite was run with `.venv/bin/python -m pytest`. It completed with **202 passed, 3 skipped**. The skipped tests are opt-in live semantic benchmarks and were not run because they may require external provider credentials.

## Architecture and ownership boundaries

The relevant ownership chain is:

1. `decompose_task()` obtains provider output, validates the operational decomposition, canonicalizes bottom-up effort products, derives relative weights, and calls deterministic allocation.
2. `decompose_transformation()` consumes the frozen `TaskDecomposition`; it does not regenerate the baseline.
3. `estimate_transformation()` classifies the frozen baseline, builds normalized accounting with `W0 = 1.0`, estimates added human support work, and delegates formulas to deterministic accounting.
4. `decompose()` is convenience composition through the provider service, not a separate accounting implementation.
5. `src/task_transmorph/domain/allocation.py` owns proportional allocation and reconciliation.
6. `src/task_transmorph/domain/accounting.py` owns W0/W1 partition checks and derived accounting.

Provider values are untrusted semantic inputs. In particular, provider `relative_effort_weight` values are compatibility fields; the canonical baseline path derives allocation weights from validated bottom-up expected-effort products.

## Summary

| Invariant | Current behavioral assessment | Highest finding | Conclusion |
| --- | --- | --- | --- |
| `CMP-001` | Strong canonical-path enforcement; some edge cases are covered indirectly | Medium coverage gap for fractional/conditional baseline occurrences and explicit conversion assertions | No confirmed defect |
| `CMP-005` | Strong direct and staged accounting enforcement | Medium gap in an end-to-end test tying classified frozen baseline allocations to an absolute W0 partition | No confirmed defect |
| `CMP-010` | Strong canonical-path enforcement and direct conflicting-weight regression test | Medium gap for a calibrated public `decompose_task()` allocation assertion and explicit zero/unit edge coverage at that boundary | No confirmed defect |

The registry's `verified` status is supported for the canonical paths. The gaps below concern regression sensitivity and test precision, not a demonstrated violation of the current contracts.

## CMP-001 — Baseline effort product

### Contract and formula

For each operational subtask, expected effort per completed parent output is:

```text
expected_effort_per_parent_output
    = expected_occurrences_per_parent_output
      × active_effort_per_occurrence
```

The product is computed after compatible effort-unit normalization. The effort quantity must use the `PER_OPERATION` time basis. A supplied expected product is optional at the provider contract boundary, but if supplied it must agree with the deterministic product; validation then stores the canonical product. Canonical operational decomposition requires a complete estimate for every operational subtask.

### Implementation ownership and enforcement paths

- `src/task_transmorph/validation/stages.py::validate_operational_decomposition()` requires a non-empty estimate collection and delegates to `validate_baseline_effort_estimates()`.
- `src/task_transmorph/validation/stages.py::validate_baseline_effort_estimates()` checks uniqueness, unknown and missing subtask IDs, `PER_OPERATION`, compatible units, the occurrence-by-effort product, and canonicalizes each estimate.
- `src/task_transmorph/application/task_decomposition.py::decompose_task()` is the public baseline path. It validates provider output before `_prepare_operational()` and `_allocate_baseline()` run.
- `src/task_transmorph/application/task_decomposition.py::_prepare_operational()` sums canonical expected products and derives each subtask weight from its product divided by the total.
- `src/task_transmorph/application/activity_effort_estimation.py::validate_activity_effort_estimation()` applies the same occurrence-product rule to AI interaction and verification activities before support work is resolved.

### Existing test evidence

Direct and integration evidence includes:

- `tests/test_effort_estimation.py::test_bottom_up_estimates_calculate_total_and_derive_relative_weights` asserts mixed hour/minute estimates produce a total of `2` and weights `0.5`, `0.25`, and `0.25`.
- `tests/test_effort_estimation.py::test_baseline_occurrences_are_multiplied_once_per_parent_output` asserts baseline products of `10`, `5`, and `15` for occurrence counts `1`, `0.25`, and `3`, plus a total of `30` and weights `1/3`, `1/6`, and `1/2`.
- `tests/test_effort_estimation.py::test_inconsistent_provider_product_is_rejected` asserts an inconsistent supplied baseline product raises `StageValidationError`.
- `tests/test_effort_estimation.py::test_invalid_baseline_coverage_is_rejected` asserts an incomplete bottom-up estimate collection is rejected.
- `tests/test_effort_estimation.py::test_missing_bottom_up_estimates_are_rejected` asserts the canonical validator rejects an empty collection.
- `tests/test_activity_effort_estimation.py::test_expected_occurrences_are_multiplied_once_per_parent_output` asserts `0.2 × 5 = 1` for conditional AI interaction work.
- `tests/test_activity_effort_estimation.py::test_repeated_activity_is_not_multiplied_by_external_volume` asserts `3 × 2 = 6` without an additional external-volume multiplication.
- `tests/test_activity_effort_estimation.py::test_expected_effort_is_optional_and_canonicalized_by_validation` asserts an omitted activity product is filled deterministically.
- `tests/test_activity_effort_estimation.py::test_product_and_units_are_validated_deterministically` covers an invalid product and incompatible units.

### Coverage assessment

| Dimension | Assessment |
| --- | --- |
| Positive cases | Directly asserted for baseline totals, mixed compatible units, activity products, and canonicalization. |
| Negative cases | Missing, incomplete, inconsistent, incompatible-unit, and wrong-product cases are covered. |
| Boundary cases | Zero bottom-up total is covered through `test_zero_bottom_up_effort_does_not_fabricate_weights`; `test_baseline_occurrences_are_multiplied_once_per_parent_output` covers fractional and repeated baseline occurrences. Tolerance behavior is not a CMP-001 product rule; product comparison is exact after conversion. |
| Integration | `decompose_task()` is exercised through provider-shaped output and its canonical validation/allocation path. Activity validation is integrated into support-work resolution tests. |
| Bypass resistance | The canonical public baseline path cannot omit estimates. Low-level `validate_baseline_effort_estimates()` intentionally returns an empty model when called directly, so it is a helper rather than the standalone canonical-entry enforcement point. Lower-level activity/application utilities can be called independently with explicit contracts. |
| Regression sensitivity | A change to the product, unit conversion, estimate coverage, or activity multiplication is likely to fail existing tests, including a regression limited to fractional or repeated baseline occurrences. |

### Gaps and regression scenarios

- **Medium:** The mixed-unit baseline assertion verifies the final total and weights, but does not assert each canonicalized estimate's converted unit/value. A conversion bug that preserves the tested total in a specially chosen fixture could be less visible.
- **Low:** The optional provider product and mandatory canonical baseline collection are documented and tested, but the distinction relies on the stage entry point rather than a single contract-level type.

No confirmed CMP-001 defect was found.

## CMP-005 — Baseline accounting partition (W0)

### Contract and formula

The baseline partition is:

```text
W0 = retained_human_work + gross_removed_work
```

Retained and gross-removed work are both portions of the original baseline. Added AI interaction and verification work is not part of gross removal. In absolute mode, quantities must have compatible unit and time-basis metadata and reconcile to the baseline within the accounting tolerance. In normalized mode, `W0 = 1`, and retained and gross-removed ratios must sum to one within the same tolerance.

The post-transformation relationship is separate:

```text
W1 = retained_human_work + resolved_support_work
```

Gross removal is not added to W1, and baseline effort is not counted as an additional component.

### Implementation ownership and enforcement paths

- `src/task_transmorph/domain/accounting.py::account_absolute()` validates common units/time basis, positive W0, and `retained + removed ≈ W0`; it then computes W1 from retained work plus resolved support.
- `src/task_transmorph/domain/accounting.py::account_normalized()` fixes W0 to `1`, validates the normalized partition, converts supported ratio bases, and computes W1 without adding gross removal.
- `src/task_transmorph/domain/accounting.py::aggregate_baseline_rows()` aggregates only RETAIN and REMOVE baseline rows and rejects rows without effort. It does not include support work.
- `src/task_transmorph/application/staged_pipeline.py::_validate_effort_handoff()` checks that classified absolute row totals match explicit retained and removed accounting inputs before `account_absolute()` runs.
- `src/task_transmorph/application/normalized_estimation.py::normalized_accounting_from_classification()` derives retained and removed ratios from frozen baseline allocation weights and verifies that they sum to one.
- `src/task_transmorph/application/estimate_transformation()` uses the normalized path with W0 fixed to `1.0` and delegates W1 and ratios to deterministic accounting.

### Existing test evidence

- `tests/test_accounting.py::test_reference_absolute_case_has_distinct_gross_and_net_metrics` asserts W0 `100`, W1 `74`, gross removal `0.40`, added work `0.14`, substitution `0.26`, and the distinct gross/net values.
- `tests/test_accounting.py::test_normalized_reference_is_semantically_equivalent_to_absolute` asserts normalized and absolute paths produce the same ratios and effect classification.
- `tests/test_accounting.py::test_invalid_balance_is_rejected` asserts invalid absolute and normalized partitions are rejected.
- `tests/test_domain_utilities.py::test_rows_aggregate_retain_and_gross_remove_only` asserts row aggregation returns only retained and removed baseline portions.
- `tests/test_domain_utilities.py::test_effort_bearing_rows_are_required_for_aggregation` rejects an effort-less row.
- `tests/test_mathematical_validation.py::test_algebraic_invariants` asserts W0, W1, remaining-work, substitution, and augmentation relationships across several normalized cases.
- `tests/test_mathematical_validation.py::test_allocation_to_accounting_consistency` allocates W0 into classified rows, aggregates them, and asserts retained `70`, removed `30`, W0 `100`, and W1 `70` with zero added work.
- `tests/test_staged_pipeline.py::test_staged_pipeline_preserves_canonical_absolute_accounting` asserts staged absolute W0/W1 values of `100`/`74`.
- `tests/test_staged_pipeline.py::test_staged_pipeline_preserves_canonical_normalized_accounting` asserts staged normalized W0/W1 values of `1`/`0.74`.
- `tests/test_staged_pipeline.py::test_staged_pipeline_preserves_frozen_baseline_partition_with_support_work` asserts a `40`/`20`/`60` frozen baseline classification, retained `40`, gross removed `80`, W0 `120`, added support `15`, and W1 `55`.

### Coverage assessment

| Dimension | Assessment |
| --- | --- |
| Positive cases | Strong direct assertions cover absolute and normalized formulas, support addition, gross/net distinction, row aggregation, and staged handoff. |
| Negative cases | Invalid partitions, zero absolute baseline, missing row effort, incompatible support representations, and mismatched absolute handoff values are covered. |
| Boundary cases | Full removal, zero added work, zero W1, very small positive W1, tolerance boundaries, degradation, and ratio-basis conversion are covered across accounting tests. |
| Integration | Direct accounting, row aggregation, staged pipeline, normalized classification, and allocation-to-accounting integration are exercised. |
| Bypass resistance | The deterministic accounting functions enforce the partition when called. A caller can intentionally use low-level explicit accounting APIs without subtask rows; that is the supported explicit accounting contract, not a bypass within the row-based staged handoff. |
| Regression sensitivity | A change that double-counts baseline, includes support in gross removal, or adds gross removal to W1 should fail the current known-answer, algebraic, and frozen-partition assertions. |

### Gaps and regression scenarios

- **Medium:** The strongest new partition assertion remains at the staged-pipeline level. There is still less direct evidence that a complete `TaskDecomposition` produced by `decompose_task()` and then classified through the transformation application path preserves an absolute W0 partition tied to its allocated rows. The explicit handoff test covers the accounting boundary without requiring additional provider-stage infrastructure.
- **Low:** `aggregate_baseline_rows()` intentionally aggregates rows without knowing the declared W0; reconciliation belongs to `account_absolute()`. This ownership split is correct, but a future caller could misunderstand the helper as a complete accounting validator.

No confirmed CMP-005 defect was found.

## CMP-010 — Bottom-up allocation precedence

### Contract and formula

For canonical baseline decomposition, bottom-up expected-effort products are the authoritative relative weights:

```text
weight_i = expected_effort_i / Σ expected_effort_j
allocated_effort_i = parent_effort × weight_i
```

Provider-supplied `relative_effort_weight` values cannot override these derived weights. The normalized allocation is made against W0 `= 1.0`; when a host supplies a baseline effort, the same weights materialize absolute quantities. `allocate_effort()` must reconcile the allocated quantities to the parent effort within its established tolerance. A zero total does not fabricate allocation weights.

### Implementation ownership and enforcement paths

- `src/task_transmorph/validation/stages.py::validate_operational_decomposition()` requires canonical bottom-up estimates and `validate_baseline_effort_estimates()` supplies canonical products.
- `src/task_transmorph/application/task_decomposition.py::_prepare_operational()` overwrites the compatibility weights with product-derived ratios. This is the precedence decision point.
- `src/task_transmorph/application/task_decomposition.py::_allocate_baseline()` sends only those derived weights to `allocate_effort()` for normalized W0 and optional absolute allocation.
- `src/task_transmorph/domain/allocation.py::allocate_effort()` rejects empty, negative, and non-positive-total weights; preserves the parent unit/time basis; and checks reconciliation within `DEFAULT_TOLERANCE`.
- `src/task_transmorph/application/normalized_estimation.py::normalized_accounting_from_classification()` consumes the frozen allocation rather than regenerating it.

### Existing test evidence

- `tests/test_effort_estimation.py::test_bottom_up_products_override_provider_relative_weights` supplies deliberately conflicting provider weights (`0.90`, `0.05`, `0.05`) and asserts the bottom-up result (`0.5`, `0.25`, `0.25`).
- `tests/test_effort_estimation.py::test_bottom_up_estimates_calculate_total_and_derive_relative_weights` asserts the expected product proportions on the public `decompose_task()` path.
- `tests/test_effort_estimation.py::test_public_absolute_allocation_uses_bottom_up_products` supplies a `120`-minute parent baseline and conflicting provider weights, then asserts absolute allocations of `40`, `20`, and `60`, normalized proportions of `1/3`, `1/6`, and `1/2`, reconciliation to `120`, and preservation of minutes/per-operation metadata.
- `tests/test_effort_estimation.py::test_zero_bottom_up_effort_does_not_fabricate_weights` asserts a zero product total yields no baseline allocations.
- `tests/test_domain_utilities.py::test_effort_allocation_is_deterministic_and_balanced` asserts `100` is allocated as `25`/`75` from weights `1`/`3`.
- `tests/test_domain_utilities.py::test_relative_weight_scale_does_not_change_allocation_proportions` asserts scale invariance.
- `tests/test_mathematical_validation.py::test_allocation_to_accounting_consistency` asserts allocated rows reconcile into the expected retained and removed totals and W0.
- `tests/test_mathematical_validation.py::test_absolute_calibration_preserves_relative_proportions` asserts normalized and calibrated allocations preserve proportions.

### Coverage assessment

| Dimension | Assessment |
| --- | --- |
| Positive cases | Direct public-path and utility assertions cover derived proportions, deterministic allocation, scale invariance, and accounting handoff. |
| Negative cases | Canonical missing/incomplete estimate rejection, non-positive zero-total behavior, and conflicting provider weights are covered. The allocation utility also rejects negative and non-positive totals, with its existing tests covering the relevant failure behavior where applicable. |
| Boundary cases | Zero bottom-up total, fractional Decimal arithmetic through allocation/accounting, unit preservation, scale invariance, absolute parent calibration, and reconciliation are covered. |
| Integration | `decompose_task()` derives and freezes allocations; normalized transformation estimation consumes them; allocation-to-accounting and staged tests verify downstream reconciliation. |
| Bypass resistance | The canonical baseline path prevents provider weights from winning. `allocate_effort()` itself intentionally accepts caller-supplied weights because it is a generic deterministic utility; it cannot enforce provenance. Low-level explicit accounting and transformation requests can also operate on host-supplied aggregate accounting without reconstructing a baseline allocation, as permitted by those contracts. |
| Regression sensitivity | Provider-weight precedence, absolute materialization, unit propagation, and parent reconciliation are directly asserted on the public baseline path. The exact public composition between baseline and transformation remains covered separately by staged tests. |

### Gaps and regression scenarios

- **Medium:** The canonical zero-total behavior is tested as an empty allocation result, while direct `allocate_effort()` rejection for a non-positive weight total is a separate utility concern. A future change could accidentally turn zero bottom-up estimates into equal allocations unless the current public-path assertion remains protected.
- **Low:** The generic allocation utility cannot distinguish bottom-up weights from another caller's weights. This is an ownership boundary, not a defect: precedence must remain enforced by `_prepare_operational()` before the utility is called.

No confirmed CMP-010 defect was found.

## Confirmed defects versus hypothetical risks

### Confirmed defects

None identified for the three audited invariants. The implementation and existing tests support the registry's current `verified` status on the canonical paths.

### Hypothetical regression risks

1. A baseline-specific conditional or repeated occurrence could be multiplied incorrectly while activity tests continue to pass.
2. Public baseline absolute materialization could drift from normalized allocation proportions without failing the current utility-only calibration test.
3. A complete public baseline-to-transformation absolute flow could stop reconciling classified rows to its frozen W0 while lower-level accounting and staged fixtures remain green.
4. A caller could use lower-level generic allocation or explicit accounting contracts outside the canonical provider-assisted baseline path. These are supported alternative entry points, not evidence that the canonical path is currently bypassable.

## Prioritized follow-up recommendations

1. **Medium — strengthen CMP-005 public integration coverage.** Add a complete public `TaskDecomposition`-to-transformation absolute-flow test if existing provider fixtures can support it without new infrastructure.
2. **Medium — preserve CMP-001 conversion assertions.** Add explicit assertions for each canonicalized mixed-unit estimate if unit conversion behavior changes or becomes more heavily used.
3. **Medium — preserve CMP-010 zero-total coverage.** Keep the public zero-total assertion alongside the new calibrated allocation test so zero estimates cannot silently become equal allocations.
4. **Low — preserve current boundary tests.** Keep the direct domain known-answer tests and conflicting-provider-weight regression test as first indicators for allocation or accounting changes.

Recommendations should reuse `tests/test_effort_estimation.py`, `tests/test_accounting.py`, `tests/test_mathematical_validation.py`, and the existing staged/transformation fixtures. No new registry loader or testing framework is needed.

## Verification result

Command run:

```bash
.venv/bin/python -m pytest
```

Result:

```text
202 passed, 3 skipped in 1.53s
```

The three skips are the existing opt-in live semantic benchmark tests. No paid or live LLM calls were made. The audit did not modify implementation code, contracts, tests, registry statuses, or `AGENTS.md`.
