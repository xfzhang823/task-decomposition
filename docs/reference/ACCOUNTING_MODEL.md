# Accounting Model

`src/task_decomposition/domain/accounting.py` is the sole deterministic mathematical authority. Application orchestration prepares and validates inputs, but it does not duplicate these equations and providers do not calculate the resulting metrics.

## Quantities

`retained_human_work` is baseline work still performed by humans after the transformation. `gross_removed_work` is baseline work classified as removed. `added_human_work` is new human work introduced by the transformation and is the sum of governance, operational/review/support, and lifecycle/maintenance contributions.

The baseline and post-transformation work are:

```text
W0 = retained_human_work + gross_removed_work
W1 = retained_human_work + added_human_work
```

The derived ratios are:

```text
gross_removed_work_ratio = gross_removed_work / W0
net_remaining_work_ratio = W1 / W0
net_substitution_ratio = 1 - net_remaining_work_ratio
net_augmentation_multiplier = 1 / net_remaining_work_ratio
```

For absolute accounting, the multiplier is calculated equivalently as `W0 / W1`. The canonical impact also exposes `added_human_work_ratio = added_human_work / W0`.

## Gross versus net

Gross removal is not net substitution. If baseline human work is `100`, removed work is `40`, and added work is `10`, retained work is `60`, `W0 = 100`, and `W1 = 70`. The gross removed ratio is `0.40`, while net substitution is `0.30`, because the new support work consumes part of the gross reduction. The augmentation multiplier is `100 / 70`, approximately `1.43`.

## Effect classification

`classify_effect(W0, W1)` derives the effect from the two work totals using `DEFAULT_TOLERANCE = 0.000000001`. It returns `GAIN` when `W1` is below `W0` beyond tolerance, `DEGRADATION` when `W1` is above `W0` beyond tolerance, and `NEUTRAL` within tolerance.

Ratios are unclamped. If added work exceeds removed work, `W1 > W0`, net substitution is negative, the augmentation multiplier is below one, and the effect is `DEGRADATION`. This is valid canonical behavior, not an error.

## Accounting modes

Normalized accounting uses `NormalizedAccountingInput` with `W0 = 1.0`, retained and gross-removed baseline-relative contributions, and support values with explicit `RatioBasis`. Absolute accounting uses `AbsoluteEffortInput` with baseline, retained, and removed `EffortQuantity` values plus support inputs. Absolute quantities must use one unit and time basis, such as `EFFORT` per operation or `HOURS` per day.

The supported support bases are `RATIO_OF_BASELINE_WORK`, `RATIO_OF_GROSS_REMOVED_WORK`, `NORMALIZED_CONTRIBUTION`, and `ABSOLUTE_EFFORT`. A basis is never inferred from an unqualified ratio. Absolute support effort is converted to the baseline-relative contribution for derived ratios; normalized mode rejects absolute support effort.

For equivalent inputs, normalized and absolute modes are scale invariant: scaling baseline, retained, removed, and absolute support effort by the same positive factor preserves ratios, multiplier, and effect classification. S4A tests this at scales `1`, `10`, `100`, and `10,000`.

## Edge behavior and constraints

No transformation with retained work equal to baseline and no added work is `NEUTRAL`. Pure removal with no added work makes net substitution equal gross removal. Added work that exactly offsets removed work produces `W1 = W0`, zero net substitution, and a neutral effect. Full removal with positive added work is defined using the same equations.

Full removal with zero added work produces `W1 = 0`, so the augmentation multiplier is undefined and the implementation raises `InvalidDenominatorError`. Absolute accounting rejects non-positive baseline `W0` with `ZeroBaselineError`. Retained plus gross removed must reconcile to `W0` within tolerance. Effort and support values must be finite and non-negative, and incompatible absolute units or time bases are rejected.

## Accounting handoff

`TaskDecomposition` stores baseline effort allocations by stable subtask ID. Transformation decomposition applies the appropriate absolute effort or normalized weight to validated RETAIN/REMOVE rows, validates the result, and calls `run_staged_pipeline()`. Added-work rows are aggregated by canonical category before the domain accounting call. Added work is not baseline work and removed work is not counted again.

## Verification

S4A added known-answer, scale-equivalence, algebraic-invariant, boundary, invalid-input, allocation-handoff, support-aggregation, staged-parity, and effect-tolerance tests. Ordinary tests are credential-free and do not invoke providers.
