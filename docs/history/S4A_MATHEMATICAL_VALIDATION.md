# S4A Mathematical Validation

## Canonical equations as implemented

`domain/accounting.py` is the sole mathematical authority. For absolute inputs, `W0 = baseline_human_effort.value` and for normalized inputs `W0 = 1`. Both modes require retained baseline work plus gross removed baseline work to reconcile to `W0` within `DEFAULT_TOLERANCE = 0.000000001`.

`added_human_work = governance_work + operational_support_work + lifecycle_support_work` after each support value is converted to the active accounting basis.

`W1 = retained_human_work + added_human_work`.

`gross_removed_work_ratio = gross_removed_work / W0`.

`added_human_work_ratio = added_human_work / W0`.

`net_remaining_work_ratio = W1 / W0`.

`net_substitution_ratio = 1 - net_remaining_work_ratio`.

`net_augmentation_multiplier = W0 / W1`.

`classify_effect()` returns `GAIN` when `W1 < W0 - tolerance`, `DEGRADATION` when `W1 > W0 + tolerance`, and `NEUTRAL` otherwise. Ratios are unclamped, so degradation can produce negative net substitution and an augmentation multiplier below one.

## Assumptions and validation constraints

- Effort and support values must be non-negative and finite.
- Absolute effort quantities must share unit and time basis.
- Absolute support values must provide matching unit and time basis.
- Normalized support values must use an explicit ratio basis.
- Retained plus gross removed work must reconcile to `W0` within the configured tolerance.
- A positive baseline is required for absolute accounting.
- `W1 = 0` raises `InvalidDenominatorError` because the augmentation multiplier is undefined.
- Support bases are explicit: baseline ratio, gross-removed ratio, normalized contribution, or absolute effort.
- `run_staged_pipeline()` validates stage identity and effort handoff, aggregates added-work rows by category, then delegates to `account_absolute()` or `account_normalized()`.

## Known-answer matrix

| Retained | Removed | Added | W0 | W1 | Gross removed ratio | Net remaining ratio | Net substitution | Multiplier | Effect |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 100 | 0 | 0 | 100 | 100 | 0 | 1 | 0 | 1 | NEUTRAL |
| 60 | 40 | 0 | 100 | 60 | 0.40 | 0.60 | 0.40 | 1/0.60 | GAIN |
| 60 | 40 | 10 | 100 | 70 | 0.40 | 0.70 | 0.30 | 1/0.70 | GAIN |
| 60 | 40 | 40 | 100 | 100 | 0.40 | 1 | 0 | 1 | NEUTRAL |
| 60 | 40 | 60 | 100 | 120 | 0.40 | 1.20 | -0.20 | 1/1.20 | DEGRADATION |

Full removal with zero added work correctly raises `InvalidDenominatorError` because `W1 = 0`. Full removal with positive added work produces defined gain metrics.

The new table-driven tests also cover fractional and non-round inputs, large scales, zero support, and net-negative substitution.

## Absolute and normalized equivalence

Equivalent transformations were tested at baseline scales `1`, `10`, `100`, and `10,000`. Absolute inputs and normalized inputs produced identical derived ratios, augmentation multipliers, and effect classifications. Existing reference coverage also proves the `100 -> 74` case is equivalent in both modes.

Support conversion tests cover normalized contributions, baseline-relative ratios, gross-removed-work-relative ratios, and absolute support effort. Gross-removed support is converted once and is not double-counted.

## Algebraic invariants

The tests independently verify `W0 = retained + removed`, `W1 = retained + added`, gross removal and remaining-work ratios, the net substitution identity, and the reciprocal augmentation identity for positive `W1`.

For fixed baseline work, tests verify that zero added work makes net substitution equal gross removal and that increasing added work cannot decrease `W1` or net remaining work, increase net substitution, or increase the augmentation multiplier.

## Boundary and numerical results

The suite covers very small positive `W1`, fractional values, scales through `10,000`, exact neutral values, and values immediately inside and outside the `1e-9` effect tolerance band. The near-zero positive case remains finite with a large positive multiplier. Degradation remains unclamped.

## Invalid-input coverage

Tests cover negative effort, negative normalized contributions, inconsistent retained/removed totals, zero baseline, zero `W1`, mismatched absolute units, missing absolute support metadata, invalid support basis usage, NaN, and infinity. Non-finite values now fail as Pydantic validation errors with the explicit finite-value contract message rather than leaking `decimal.InvalidOperation`.

## Added/support-work accounting

Tests verify that support work enters only through `added_human_work`, does not alter `W0`, does not double-count removed work, and changes `W1` monotonically. Staged-pipeline coverage verifies multiple added rows in one category aggregate correctly and that zero categories contribute zero support.

## Allocation-to-accounting consistency

Deterministic weights `A=0.50`, `B=0.30`, and `C=0.20` were allocated from a baseline of `100`. Tests verify retained/removed totals for no removals, one removal, multiple removals, and all removals. The resulting known classification totals feed absolute accounting without an LLM.

## Staged-pipeline parity

For both absolute and normalized reference inputs, `run_staged_pipeline()` produced the same `W0`, `W1`, net substitution, augmentation multiplier, and effect as direct calls to the accounting authority with independently constructed equivalent inputs. The staged path therefore prepares and validates inputs without redefining the mathematics.

## Effect classification

The focused tolerance tests verify exact and adjacent values around `W1 = W0`: differences at or below `1e-9` are neutral, while differences beyond the tolerance classify as gain or degradation. Zero, positive substitution, and increased human work are covered through the known-answer and boundary cases.

## Defect found and fix

The audit found that `EffortQuantity(value="NaN", ...)` could raise a raw `decimal.InvalidOperation` while checking non-negativity. `contracts/effort.py` now rejects all non-finite decimal values before model validation continues. This is an unambiguous invalid-input correction and does not change valid accounting semantics.

## Tests added

`tests/test_mathematical_validation.py` adds 28 mathematical/accounting tests covering the matrix, equivalence, invariants, numerical boundaries, allocation handoff, staged parity, support aggregation, and invalid inputs. The repository now has 96 total tests, with 3 optional live-provider tests skipped.

## Verification

- `pytest -q`: `96 passed, 3 skipped`.
- `ruff check src tests`: passed.
- `ruff format --check src tests`: passed.
- `python -m compileall -q src`: passed using a temporary bytecode cache.
- `git diff --check`: passed.
- No live provider credentials or network calls were required.

## Remaining mathematical uncertainty

No defect or unresolved mathematical decision remains for the implemented canonical model. The explicit `W1 = 0` error behavior, tolerance, support-basis conversions, and unclamped degradation semantics are now documented and tested.

MATHEMATICS VALIDATED — PROCEED TO S4B
