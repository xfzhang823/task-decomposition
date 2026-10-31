# Contracts

Frozen, provider-neutral data schemas for every value that crosses the pipeline. This package defines *shape* — Pydantic models, enums, and one unit-conversion helper. It contains no orchestration, no provider transport, and no accounting formulas.

Dependency direction: `contracts/` is the leaf of the import graph. It imports only `pydantic` and `task_transmorph.errors`. `application/`, `validation/`, `evaluation/`, `interfaces/`, `domain/`, and `providers/` all import from it; it imports none of them.

Behavioral protocols do not live here. `interfaces/` owns the `Protocol` definitions (`TaskDecompositionProvider`, `TransformationDecompositionProvider`, `SemanticEvaluator`); this package owns only the data those protocols exchange.

## Module overview

The package answers one question — *what is a well-formed value at this boundary?* — and nothing else.

- **Baseline schemas** describe operational subtasks, their bottom-up effort estimates, and the frozen W0 allocation.
- **Stage schemas** describe the progressive transformation analysis: RETAIN/REMOVE classification → agentic task synthesis → human-agent activity modeling → activity-effort estimation.
- **Request envelopes** carry host input into provider stages without vendor SDK types.
- **Effort value objects** make units, time bases, and ratio denominators explicit, so incompatible quantities cannot be silently combined.
- **Accounting contracts** name the result vocabulary (`CanonicalTransformationImpact`) without computing it.
- **Provenance contracts** carry portable provider/model metadata; persistence stays host-owned.

Every model is immutable (`frozen=True`). Stage and request models also forbid unknown fields (`extra="forbid"`), so a misspelled or stale provider field fails loudly instead of being dropped.

## Directory structure

```text
contracts/
├── __init__.py       flat export surface (45 names, alphabetical __all__)
├── effort.py         units, time bases, ratio bases, effort quantities, accounting inputs
├── decomposition.py  RETAIN/REMOVE label and canonical baseline work row
├── provenance.py     provenance references, provider stages, provider metadata
├── stages.py         baseline and transformation stage results (largest module)
├── provider.py       host requests and the untrusted provider-stage envelope
└── accounting.py     accounting mode, effect labels, canonical impact result
```

There are no subpackages. Application code imports from `task_transmorph.contracts` (the flat surface); import a specific module only when a module-local dependency reads more clearly.

### `effort.py`

The numeric vocabulary shared by every other module.

- `EffortUnit` — `effort`, `minutes`, `hours`, `days`, `fte`. The domain does not assume hours.
- `TimeBasis` — the period an absolute quantity is measured over (`per_operation`, `per_day`, `per_week`, `per_month`, `per_year`).
- `RatioBasis` — `ratio_of_baseline_work`, `ratio_of_gross_removed_work`, `normalized_contribution`, `absolute_effort`. Every support value must state its denominator.
- `EffortQuantity` — a non-negative `Decimal` amount plus unit and time basis. Negative and non-finite values are rejected.
- `convert_effort_quantity()` — converts duration units only (minutes/hours/days) and preserves the time basis. `EFFORT` and `FTE` are not durations and raise `ContractValidationError`.
- `SupportWorkInput` / `SupportWorkInputs` — additional post-transformation work in exactly two canonical categories, `ai_interaction` and `ai_verification`. `unit`/`time_basis` are permitted only with `absolute_effort`; supplying them on a ratio basis is an error.
- `AbsoluteEffortInput` — the W0 partition (`baseline_human_effort = retained_human_work + gross_removed_work`) plus optional support work.
- `NormalizedAccountingInput` — baseline fixed at `W0 = 1.0`; the retained and gross-removed ratios must partition that baseline within the accounting tolerance.

### `decomposition.py`

- `TransformationClassification` — `RETAIN` / `REMOVE`.
- `TransformationRow` — one canonical baseline work row: `row_id`, classification, optional absolute effort or relative weight, rationale, provenance. Consumed by `domain.accounting.aggregate_baseline_rows`; the row carries no totals.

### `provenance.py`

- `ProvenanceRef` — a `kind` + `value` pair for host references.
- `ProviderStage` — the five provider-driven stages. Semantic evaluation is deliberately not a provider stage.
- `ProviderProvenance` — provider id, stage, optional model and request ids, references. Extra fields are forbidden.

### `stages.py`

Identity and scope:

- `TaskReference` — the operational task identity. It never selects a provider, model, scenario, or accounting mode.
- `ParentOutputContract` — `output_unit`, `completion_boundary`, `scope_exclusions`, and a `source` recording whether the boundary was `supplied`, `provider_inferred`, or `application_inferred`.

Baseline decomposition:

- `OperationalSubtask` / `OperationalDecomposition` — observable human work; `sequence_index`, `depends_on`, and effort rationale.
- `BaselineSubtaskEffortEstimate` / `BaselineEffortEstimation` — bottom-up estimates per parent output. Expected effort is defined as `expected_occurrences_per_parent_output × active_effort_per_occurrence`; the application computes and checks that product.
- `BaselineEffortAllocation` — one subtask's frozen share; must carry `effort` or `weight_ratio`, and records `allocation_source` (`estimated` / `host`).
- `TaskDecomposition` — the reusable baseline: decomposition plus estimates, allocations, provenance. Re-validates that allocations uniquely and completely cover the subtasks when any are present.

Transformation stages:

- `ClassifiedSubtask` / `RetainRemoveClassification` — identity-preserving labels. A row may carry absolute `effort` or `baseline_effort_ratio`, never both. Provider JSON may use upper- or lower-case labels.
- `AgenticTask` / `AgenticTaskSynthesis` — AI responsibilities assembled from removed subtasks: description, required inputs, expected outputs.
- `HumanAgentActivityCategory` / `HumanAgentActivity` / `HumanAgentActivityModel` — semantic human activities (`AI_INTERACTION` / `AI_VERIFICATION`) with trigger and expected action. No effort, occurrences, or durations on the activity itself.
- `ActivityEffortEstimate` / `ActivityEffortEstimation` — occurrences per parent output and active effort per occurrence, one estimate per modeled activity. Application validation requires `expected_effort_per_parent_output` to equal their product.

Results:

- `TransformationDecompositionResult` — frozen baseline, every stage output, and the authoritative `accounting` impact; also carries `estimation_assumptions` and `normalized_work_estimates` for exploratory runs.
- `NormalizedWorkEstimate` — an auditable 100-unit baseline row used by normalized estimation.

The `semantic_evaluation` field on `TransformationDecompositionResult` is typed `Any` on purpose: `evaluation/contracts.py` imports `contracts/`, so a typed reference would close an import cycle. The application stores a validated `SemanticEvaluation` there.

### `provider.py`

Host requests:

- `TaskDecompositionRequest` — task, optional context, optional parent-output contract, optional measured `baseline_effort`. No transformation intent.
- `TransformationDecompositionRequest` — a frozen `TaskDecomposition` plus explicit `accounting_input` (`AbsoluteEffortInput` or `NormalizedAccountingInput`).
- `TransformationProposalRequest` — the same frozen baseline without accounting input; used by exploratory normalized estimation, which constructs accounting after classification.

Stage requests nest progressively, so a stage cannot be invoked without the outputs it consumes:

- `OperationalDecompositionRequest` → `request`
- `RetainRemoveClassificationRequest` → `request` + `operational_decomposition`
- `AgenticTaskSynthesisRequest` → adds `retain_remove_classification`
- `HumanAgentActivityModelingRequest` → adds `agentic_task_synthesis`
- `ActivityEffortEstimationRequest` → adds `human_agent_activity_modeling`

`ProviderStageResponse` is the return envelope: `stage` + `payload: Any` + `provenance`. The payload is untrusted by design — only application validation promotes it to a typed stage model.

### `accounting.py`

- `AccountingMode` — `normalized` (W0 fixed at 1) or `absolute` (explicit units and time bases).
- `EffectClassification` — `gain` / `neutral` / `degradation`. Tolerance-aware and unclamped: support work may exceed gross removal.
- `CanonicalTransformationImpact` — the output contract of deterministic accounting. Absolute-mode `EffortQuantity` fields are `None` in normalized mode; ratio fields exist in both modes. `net_augmentation_multiplier` is `None` when `w1 == 0` because the multiplier is undefined.

## Conventions

- **Immutable by default.** Every model sets `frozen=True`.
- **Strict where input is untrusted.** Every stage, request, and envelope model uses `extra="forbid"`. `EffortQuantity`, `SupportWorkInput`/`SupportWorkInputs`, `AbsoluteEffortInput`, `NormalizedAccountingInput`, `TransformationRow`, `ProvenanceRef`, and `CanonicalTransformationImpact` are frozen but tolerate extra keys.
- **Exact arithmetic.** All numeric fields are `Decimal`, and `mode="before"` validators coerce `int`/`float`/`str` with `Decimal(str(value))`, so binary float error never reaches accounting.
- **Wire-case tolerance at the edges.** `ClassifiedSubtask.classification` accepts upper- or lower-case; `HumanAgentActivity.category` is case-insensitive. Everything else is strict.
- **Explicit bases.** Effort is never inferred from missing data. Units, time bases, and ratio denominators are mandatory wherever an absolute value is possible.
- **Per-parent-output anchoring.** Every effort field is normalized to one completed parent output.
- **No accounting arithmetic.** W0/W1, ratios, effect classification, and tolerance live only in `domain/accounting.py`. The sole computation here is the deterministic duration conversion in `convert_effort_quantity()`.
- **No provider leakage.** No SDK types, no network calls, no tracing, no persistence.

## Usage examples

### Build normalized accounting input

```python
from decimal import Decimal

from task_transmorph.contracts import (
    NormalizedAccountingInput,
    SupportWorkInput,
    SupportWorkInputs,
)

accounting = NormalizedAccountingInput(
    retained_work_ratio=Decimal("0.60"),
    gross_removed_work_ratio=Decimal("0.40"),
    support_work=SupportWorkInputs(
        ai_interaction=SupportWorkInput(value="0.08", basis="normalized_contribution"),
        ai_verification=SupportWorkInput(value="0.06", basis="ratio_of_baseline_work"),
    ),
)
```

### Build absolute accounting input

```python
from task_transmorph.contracts import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    TimeBasis,
)


def per_invoice(minutes: str) -> EffortQuantity:
    return EffortQuantity(
        value=minutes,
        unit=EffortUnit.MINUTES,
        time_basis=TimeBasis.PER_OPERATION,
    )


w0 = AbsoluteEffortInput(
    baseline_human_effort=per_invoice("14"),
    retained_human_work=per_invoice("8.4"),
    gross_removed_work=per_invoice("5.6"),
)
```

### Convert compatible durations

```python
from decimal import Decimal

from task_transmorph.contracts import (
    EffortQuantity,
    EffortUnit,
    TimeBasis,
    convert_effort_quantity,
)

quarter_hour = EffortQuantity(
    value="0.25",
    unit=EffortUnit.HOURS,
    time_basis=TimeBasis.PER_OPERATION,
)
assert convert_effort_quantity(quarter_hour, EffortUnit.MINUTES).value == Decimal("15")
```

### Read a transformation result

```python
impact = result.accounting

impact.w0                       # baseline effort, or 1 in normalized mode
impact.w1                       # retained work + resolved support work
impact.net_substitution_ratio   # 1 - w1 / w0
impact.gross_removed_work_ratio # gross removal before support work
impact.effect                   # gain | neutral | degradation
result.semantic_evaluation      # validated SemanticEvaluation, or None
```

### Fail fast on malformed values

```python
from task_transmorph.contracts import ClassifiedSubtask, EffortQuantity, EffortUnit, TimeBasis

EffortQuantity(value="-1", unit=EffortUnit.MINUTES, time_basis=TimeBasis.PER_OPERATION)
# pydantic ValidationError: effort quantities cannot be negative

ClassifiedSubtask(
    subtask_id="sub-1",
    classification="retain",
    effort=EffortQuantity(value=1, unit=EffortUnit.EFFORT, time_basis=TimeBasis.PER_OPERATION),
    baseline_effort_ratio="0.5",
)
# ValidationError: classification effort must use absolute effort or
# baseline_effort_ratio, not both
```

## Dependency relationships

```text
                        task_transmorph.errors
                                 ▲
                                 │
                            contracts/            ← leaf; pydantic + errors only
        ┌────────────┬───────────┼────────────┬──────────────┐
        │            │           │            │              │
   validation    interfaces  evaluation  domain/accounting  providers
        └────────────┴───────────┴────────────┴──────────────┘
                                 ▲
                            application
```

Inside the package the graph is acyclic and shallow:

- `effort.py` and `provenance.py` are the roots.
- `decomposition.py`, `accounting.py`, and `stages.py` build on those roots.
- `provider.py` builds on `effort`, `provenance`, and `stages`.
- `__init__.py` re-exports the whole surface; every name is also re-exported by `task_transmorph`.

Two escape hatches exist to keep the graph acyclic and are intentional: `ProviderStageResponse.payload` is `Any`, and `TransformationDecompositionResult.semantic_evaluation` is `Any`. Both are narrowed by application validation, not by the contract.

## Changing this module

1. Keep it a leaf. Do not import `application`, `providers`, `evaluation`, `interfaces`, `validation`, or `domain`.
2. Do not add accounting formulas, provider SDK types, tracing, or persistence concerns.
3. Add or change a model, then export it in the module's `__all__` and in `contracts/__init__.py`; check whether the top-level `task_transmorph` surface should change too.
4. Prefer adding a validator over documenting a rule the type system can enforce.
5. If the change touches effort, allocation, stage identities, or accounting semantics, identify the affected records in `docs/invariants/registry.yaml` and run the focused invariant tests.
6. Run the standard verification from the repository root: `pytest`, `ruff check src tests`, `ruff format --check src tests`, and `python -m compileall -q src`.
