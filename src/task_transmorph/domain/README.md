# Domain

Pure deterministic mathematics. This package is the sole authority for effort allocation and canonical W0/W1 accounting; it contains no I/O, no environment access, no provider imports, and no logging side effects. Given the same typed inputs it always returns the same result.

Dependency direction: `domain/` → `contracts/` (typed inputs and the `CanonicalTransformationImpact` result) and `errors/`. It is imported by `application/` and by tests; `contracts/` never imports it.

The public surface is five functions and one constant. There are no domain classes: inputs and outputs are the frozen Pydantic models from `task_transmorph.contracts`.

## Module overview

The package covers the two deterministic steps between semantic proposals and a reported impact:

1. **Allocation** — turn relative effort weights into per-subtask shares of a parent effort quantity.
2. **Accounting** — turn a baseline partition plus resolved support work into W0, W1, ratios, multiplier, and effect.

The semantic premises (which subtasks exist, what they cost, what is retained or removed, how much support work a transformation introduces) come from providers and hosts. This package never invents them: it validates that the supplied numbers are internally consistent and computes the consequences.

```text
effort weights ──► allocate_effort ──► per-subtask EffortQuantity
                                            │
                         TransformationRow ─┤ aggregate_baseline_rows
                                            ▼
                              retained + gross_removed
                                            │
                    resolved support work ──┤ account_absolute / account_normalized
                                            ▼
                            CanonicalTransformationImpact (W0, W1, ratios, effect)
```

## Directory structure

```text
 domain/
 ├── __init__.py     re-exports the five functions plus DEFAULT_TOLERANCE
 ├── allocation.py   allocate_effort() and the canonical tolerance constant
 └── accounting.py   account_absolute(), account_normalized(),
                    classify_effect(), aggregate_baseline_rows()
```

There are no subpackages. `accounting.py` imports `DEFAULT_TOLERANCE` from `allocation.py`; nothing else crosses between the two modules.

### `allocation.py`

`allocate_effort(parent_effort, weights, *, tolerance=DEFAULT_TOLERANCE)` distributes one `EffortQuantity` across labelled weights.

- Keys are arbitrary labels — in practice stable subtask IDs.
- Weights accept `Decimal`, `int`, `float`, or `str` and are converted through `Decimal(str(value))`.
- Weights must be non-empty, non-negative, and have a positive total; otherwise `AccountingInvariantError`.
- Each share is `parent_effort.value × weight / total`, preserving the parent's unit and time basis.
- The shares are reconciled back to the parent within `tolerance` before returning.
- Only proportions matter: weights `{1, 3}` and `{20, 60}` produce the same shares for the same parent.

`DEFAULT_TOLERANCE` is `Decimal("0.000000001")` (1e-9). It is defined here, imported by `accounting.py`, and re-exported from `task_transmorph.domain`. It is intentionally not part of the top-level `task_transmorph` surface; callers import it from `task_transmorph.domain`.

### `accounting.py`

The canonical relationships:

```text
W0 = retained_human_work + gross_removed_work        (baseline partition)
W1 = retained_human_work + resolved_support_work     (post-transformation)
```

Gross removal is part of W0, not of W1. Support work is new post-transformation effort, so it offsets gross removal rather than adding to it.

Derived fields on `CanonicalTransformationImpact`, computed identically in both modes:

- `gross_removed_work_ratio = gross_removed_work / W0`
- `added_human_work_ratio = added_human_work / W0`
- `net_remaining_work_ratio = W1 / W0`
- `net_substitution_ratio = 1 - net_remaining_work_ratio`
- `net_augmentation_multiplier = 1 / net_remaining_work_ratio`, or `None` when `W1 = 0`

Ratios are never clamped. Support work above gross removal gives `W1 > W0`, a negative substitution ratio, and `DEGRADATION`.

## Core interfaces

```text
allocate_effort(
    parent_effort: EffortQuantity,
    weights: Mapping[str, Decimal | int | float | str],
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> dict[str, EffortQuantity]

account_absolute(
    accounting: AbsoluteEffortInput,
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> CanonicalTransformationImpact

account_normalized(
    accounting: NormalizedAccountingInput,
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> CanonicalTransformationImpact

classify_effect(
    w0: Decimal,
    w1: Decimal,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> EffectClassification

aggregate_baseline_rows(
    rows: Iterable[TransformationRow],
) -> tuple[Decimal, Decimal]
```

**`account_normalized`** fixes `W0 = 1`. The retained and gross-removed ratios must partition that baseline within tolerance. Support contributions are converted from their declared `RatioBasis`; `ABSOLUTE_EFFORT` support is rejected with `RatioBasisError` because it has no baseline unit to attach to.

**`account_absolute`** requires `baseline_human_effort`, `retained_human_work`, and `gross_removed_work` to share one unit and time basis, and requires `W0 > 0` (`ZeroBaselineError` otherwise). Absolute support must match the baseline unit and basis; ratio support is scaled by W0 or by gross-removed work as its basis declares. The result carries `EffortQuantity` fields alongside the same ratios as normalized mode.

**`classify_effect`** returns `GAIN` when `w1 < w0 - tolerance`, `DEGRADATION` when `w1 > w0 + tolerance`, and `NEUTRAL` inside the band. At exactly `w0 ± tolerance` the result is still neutral.

**`aggregate_baseline_rows`** sums `TransformationRow.effort` by classification and returns `(retained, removed)` as plain `Decimal` values. Every row must carry absolute effort; a row without it raises `AccountingInvariantError` naming the `row_id`. The helper has no support-work input by design — support is post-transformation work.

### Support-work basis conversion

| Basis | Normalized mode | Absolute mode |
| --- | --- | --- |
| `NORMALIZED_CONTRIBUTION` | used as-is | `value × W0` |
| `RATIO_OF_BASELINE_WORK` | used as-is (W0 = 1) | `value × W0` |
| `RATIO_OF_GROSS_REMOVED_WORK` | `value × gross_removed / W0` | `value × gross_removed` |
| `ABSOLUTE_EFFORT` | rejected (`RatioBasisError`) | used as-is, unit must match |

`RATIO_OF_GROSS_REMOVED_WORK` is applied exactly once. `NORMALIZED_CONTRIBUTION` is already baseline-relative and is never multiplied by gross removal a second time.

### Preconditions

The domain does not resolve inputs. In particular, `support_work` is nullable on the input contracts so the application can decide between host-supplied and estimated support; by the time `account_absolute` or `account_normalized` is called, the caller must pass a resolved `SupportWorkInputs` bundle. The staged handoff in `application/staged_pipeline.py` does exactly that.

## Usage examples

### Allocate a parent effort by weight

```python
from task_transmorph import EffortQuantity, EffortUnit, TimeBasis, allocate_effort

parent = EffortQuantity(value=100, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION)
shares = allocate_effort(parent, {"a": 1, "b": 3})

assert shares["a"].value == 25
assert shares["b"].value == 75
assert shares["b"].unit is EffortUnit.EFFORT
```

### Aggregate classified rows and account for them

```python
from decimal import Decimal

from task_transmorph import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    SupportWorkInput,
    SupportWorkInputs,
    TimeBasis,
    TransformationClassification,
    TransformationRow,
    account_absolute,
    aggregate_baseline_rows,
    allocate_effort,
)

unit, time_basis = EffortUnit.MINUTES, TimeBasis.PER_OPERATION
parent = EffortQuantity(value=100, unit=unit, time_basis=time_basis)
shares = allocate_effort(parent, {"a": "0.50", "b": "0.30", "c": "0.20"})

rows = [
    TransformationRow(row_id="a", classification=TransformationClassification.RETAIN, effort=shares["a"]),
    TransformationRow(row_id="b", classification=TransformationClassification.REMOVE, effort=shares["b"]),
    TransformationRow(row_id="c", classification=TransformationClassification.RETAIN, effort=shares["c"]),
]
retained, removed = aggregate_baseline_rows(rows)

impact = account_absolute(
    AbsoluteEffortInput(
        baseline_human_effort=parent,
        retained_human_work=EffortQuantity(value=retained, unit=unit, time_basis=time_basis),
        gross_removed_work=EffortQuantity(value=removed, unit=unit, time_basis=time_basis),
        support_work=SupportWorkInputs(
            ai_interaction=SupportWorkInput(
                value=0, basis="absolute_effort", unit=unit, time_basis=time_basis
            ),
            ai_verification=SupportWorkInput(
                value=0, basis="absolute_effort", unit=unit, time_basis=time_basis
            ),
        ),
    )
)

assert (retained, removed) == (Decimal("70"), Decimal("30"))
assert impact.w0 == 100 and impact.w1 == 70
assert impact.gross_removed_work_ratio == Decimal("0.3")
assert impact.effect.value == "gain"
```

Support work is required at this boundary. The example passes an explicit zero bundle, matching what the staged handoff always injects. A `None` bundle is a contract-level placeholder for the application, not a valid direct call to the accounting functions.

### Normalized accounting with support work

```python
from decimal import Decimal

from task_transmorph import (
    NormalizedAccountingInput,
    SupportWorkInput,
    SupportWorkInputs,
    account_normalized,
)

impact = account_normalized(
    NormalizedAccountingInput(
        retained_work_ratio=Decimal("0.60"),
        gross_removed_work_ratio=Decimal("0.40"),
        support_work=SupportWorkInputs(
            ai_interaction=SupportWorkInput(value="0.08", basis="normalized_contribution"),
            ai_verification=SupportWorkInput(value="0.06", basis="normalized_contribution"),
        ),
    )
)

assert impact.w0 == 1
assert impact.w1 == Decimal("0.74")
assert impact.net_substitution_ratio == Decimal("0.26")
assert impact.net_augmentation_multiplier == Decimal(1) / Decimal("0.74")
```

### Effect tolerance

```python
from decimal import Decimal

from task_transmorph import classify_effect

assert classify_effect(Decimal("100"), Decimal("99.999999999")).value == "neutral"
assert classify_effect(Decimal("100"), Decimal("99.999999998")).value == "gain"
assert classify_effect(Decimal("100"), Decimal("100.000000002")).value == "degradation"
```

## Dependency relationships

```text
                   contracts/                 errors
                       │                       │
                       └───────────┬───────────┘
                                   ▼
                                 domain/
                 ┌─────────────────┴──────────────────┐
                 │                                    │
          allocation.py  ── DEFAULT_TOLERANCE ──►  accounting.py
       (weights → shares)                    (W0/W1, ratios, effect)
                 ▲                                    ▲
                 │                                    │
   application.task_decomposition      application.staged_pipeline
                                       application.normalized_estimation
```

Callers today:

- `application/task_decomposition.py` calls `allocate_effort` to normalize derived weights against a synthetic `W0 = 1.0` parent and, when a measured baseline is supplied, to materialize absolute shares.
- `application/staged_pipeline.py` calls `account_absolute` or `account_normalized` after validating the stage chain and injecting resolved support work.
- `application/normalized_estimation.py` reads `DEFAULT_TOLERANCE` for its exploratory bridge.
- `examples/openai_decompose.py` reads `DEFAULT_TOLERANCE` for display tolerance.

The package imports no provider SDK, no application module, no tracing, and no persistence. That keeps it usable in credential-free tests and sidesteps import cycles.

## Edge behavior

- Retained plus gross-removed work must reconcile to `W0` within tolerance; a mismatch raises `AccountingInvariantError`.
- Absolute quantities must share one unit and time basis; otherwise `IncompatibleEffortUnitError`.
- Absolute `W0` must be positive; otherwise `ZeroBaselineError`.
- Absolute support work must match the baseline unit and basis; otherwise `IncompatibleEffortUnitError`.
- Absolute support work under normalized accounting raises `RatioBasisError`.
- Negative or non-finite effort is rejected earlier, by the `contracts` validators.
- Full removal with zero support gives `W1 = 0`, `net_substitution_ratio = 1`, and `net_augmentation_multiplier = None`; every other field stays valid.
- Very small positive `W1` yields a large but finite multiplier; values are not rounded or clamped.

The normative description of these relationships, inputs, and boundaries is [`docs/reference/ACCOUNTING_MODEL.md`](../../../docs/reference/ACCOUNTING_MODEL.md).

## Verification

Deterministic behavior is protected by credential-free tests. When changing this package, run them and extend them rather than trusting the prose:

- `tests/test_accounting.py` — known-answer absolute and normalized cases, basis conversion, invalid balance, unit mismatch, zero baseline.
- `tests/test_mathematical_validation.py` — known-answer matrix, scale equivalence, algebraic invariants, effect tolerance boundaries, allocation-to-accounting handoff, staged parity.
- `tests/test_domain_utilities.py` — allocation determinism, weight-scale invariance, row aggregation.
- `tests/test_effort_estimation.py` and `tests/test_staged_pipeline.py` — effort handoff and staged accounting integration.

Standard repository checks: `pytest`, `ruff check src tests`, `ruff format --check src tests`, `python -m compileall -q src`, `git diff --check`.

## Changing this module

1. Keep formulas here and only here. Application code, providers, and prompts must not restate W0/W1, ratio, or effect arithmetic.
2. Keep it pure: no environment reads, no network, no filesystem, no provider SDK imports.
3. Accounting changes require independent known-answer regression tests, a registry review in `docs/invariants/registry.yaml`, and an update to `docs/reference/ACCOUNTING_MODEL.md` if semantics move.
4. Allocation or effort changes require an allocation-to-accounting handoff test that proves totals survive the boundary.
5. Do not change support-ratio bases, units, tolerance, or zero-denominator behavior silently.
6. If a public name is added or removed, update `domain/__init__.py` and check whether the top-level `task_transmorph` surface should change too, along with any external consumer (especially AgenticAICompass).
