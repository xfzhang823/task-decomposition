# Canonical Accounting Model

`src/task_decomposition/domain/accounting.py` is the sole deterministic
authority for canonical effort accounting. This document defines the meaning
of its inputs and outputs. Application orchestration prepares and validates the
inputs; providers propose semantic facts but do not calculate authoritative
metrics.

## Canonical quantities and provenance

The accounting quantities have distinct origins and meanings:

| Quantity | Meaning | Origin |
| --- | --- | --- |
| `baseline_human_effort` | Total human effort required before the AI transformation. This is the complete baseline `W0`, not an additional component to sum. | Host/application input, usually an `EffortQuantity`. |
| `retained_human_work` | Portion of baseline effort associated with subtasks classified `RETAIN`. | Validated task allocation plus validated transformation classification, or an equivalent host accounting input. |
| `gross_removed_work` | Portion of baseline effort associated with subtasks classified `REMOVE`, before newly introduced support work is considered. | Validated task allocation plus validated transformation classification, or an equivalent host accounting input. |
| `support_work` | Additional human effort introduced by AI-related activities. Canonical categories are `AI_INTERACTION` and `AI_VERIFICATION`. | Application resolution from host-provided support or validated added-work estimates. |
| `added_human_work` | Sum of resolved interaction and verification support work. | Deterministically computed by the accounting domain. |
| `W0` | Original human effort before transformation. | Deterministically computed from the baseline input. |
| `W1` | Human effort remaining after transformation, including retained work and new support work. | Deterministically computed by the accounting domain. |

Support work is post-transformation effort. It is not part of the original
baseline partition and must not be added to `gross_removed_work`.

## Baseline and post-transformation relationships

For compatible absolute effort quantities, the baseline partition is:

```text
W0 = retained_human_work + gross_removed_work
```

The post-transformation effort is:

```text
W1 = retained_human_work + resolved_support_work
```

The second equation uses the sum of the resolved `AI_INTERACTION` and
`AI_VERIFICATION` contributions. Gross removal and net reduction are therefore
different concepts: gross removal measures baseline work no longer performed,
while net reduction accounts for support work that is newly introduced.

The canonical derived ratios are:

```text
gross_removed_work_ratio = gross_removed_work / W0
added_human_work_ratio   = added_human_work / W0
net_remaining_work_ratio = W1 / W0
net_substitution_ratio   = 1 - net_remaining_work_ratio
net_augmentation_multiplier = 1 / net_remaining_work_ratio
```

For absolute accounting, the multiplier is calculated equivalently as `W0 / W1`.
Ratios are not clamped. If support work exceeds gross removal, `W1 > W0`, net
substitution is negative, and the effect is `DEGRADATION`.

Example: if `W0 = 100`, retained work is `60`, gross removed work is `40`, and
resolved support work is `10`, then:

```text
W0 = 60 + 40 = 100
W1 = 60 + 10 = 70
gross_removed_work_ratio = 0.40
net_substitution_ratio = 1 - 70/100 = 0.30
net_augmentation_multiplier = 100/70 ≈ 1.43
```

The gross removed ratio is `0.40`, but the net substitution ratio is `0.30`
because support work offsets part of the gross reduction.

## Absolute and normalized accounting

`AbsoluteEffortInput` expresses baseline, retained, and removed work as
`EffortQuantity` values. All absolute quantities used together must have the
same `EffortUnit` and `TimeBasis`, for example `HOURS` per operation. Absolute
support inputs must use the same unit and time basis as the baseline. Ratio
support inputs are converted using their explicit `RatioBasis`.

`NormalizedAccountingInput` fixes `W0 = 1.0`. Its retained and gross-removed
ratios must partition the baseline within the canonical tolerance. Normalized
support inputs use an explicit non-absolute ratio basis. `ABSOLUTE_EFFORT`
support is rejected in normalized accounting because it cannot be interpreted
without an absolute baseline unit and basis.

The supported support bases are:

- `RATIO_OF_BASELINE_WORK`: already relative to baseline work.
- `RATIO_OF_GROSS_REMOVED_WORK`: relative to gross removed work and converted
  using the gross-removed contribution.
- `NORMALIZED_CONTRIBUTION`: already a baseline-relative contribution; it must
  not be multiplied by gross removed work again.
- `ABSOLUTE_EFFORT`: a concrete effort amount, valid for absolute accounting
  when its unit and time basis match the baseline.

The representations are scale-equivalent when corresponding absolute values
and absolute support work are scaled by the same positive factor.

## Responsibility boundaries

The canonical flow preserves these ownership boundaries:

1. The host/application supplies the baseline effort and transformation
   accounting input.
2. Task decomposition validates operational subtasks and establishes baseline
   allocations by stable subtask ID.
3. Transformation decomposition consumes that existing task decomposition and
   validates `RETAIN`/`REMOVE` classifications and added-work proposals.
4. The application resolves added support work from host inputs or validated
   added-work estimates.
5. `domain/accounting.py` validates the accounting handoff and computes W0, W1,
   ratios, multiplier, and effect.

The baseline is never regenerated during transformation decomposition. Providers
do not own accounting formulas, and application layers must not duplicate them.

## Edge behavior and assumptions

- Retained plus gross removed work must reconcile to the baseline within
  `DEFAULT_TOLERANCE`.
- Effort values are finite and non-negative.
- Absolute units and time bases must be compatible before arithmetic.
- Full removal with zero support produces `W1 = 0`; the augmentation
  multiplier is undefined and raises `InvalidDenominatorError`.
- Absolute accounting rejects a non-positive baseline with `ZeroBaselineError`.
- Effect classification uses the canonical tolerance and returns `GAIN`,
  `NEUTRAL`, or `DEGRADATION` without clamping values.

The input contracts permit `support_work=None` so the application can resolve
host-versus-estimated support. Before direct domain accounting, support work is
expected to have been resolved; the staged application handoff supplies the
resolved support bundle.

## Verification

Known-answer, scale-equivalence, algebraic-invariant, boundary, invalid-input,
allocation-handoff, support-aggregation, staged-parity, and effect-tolerance
tests protect these semantics. They are credential-free and do not invoke
providers.
