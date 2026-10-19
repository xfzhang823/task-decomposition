# Host Accounting Input Origin Audit

## Scope and conclusion

This is an audit-only trace of `request.accounting_input` and `support_work` backward from `decompose_transformation()`. No production code, tests, prompts, schemas, validators, or accounting formulas were changed.

**Conclusion: the library does not originate host accounting quantities. Callers do.** The canonical request requires an explicit `AbsoluteEffortInput` or `NormalizedAccountingInput`; providers do not supply authoritative W0, retained work, removed work, or support quantities. In this checkout, the concrete callers are the example and credential-free tests. No frontend, workflow model, persistence adapter, or production service caller is present. The main confirmed risk is that explicit host accounting values can disagree with LLM-added-work rows without detection because the canonical transformation path intentionally gives host `support_work` precedence.

## Data-flow diagram

```text
Caller constructs AbsoluteEffortInput or NormalizedAccountingInput
  ├─ baseline W0
  ├─ retained and gross-removed work/ratios
  └─ SupportWorkInputs
       ├─ ai_interaction
       └─ ai_verification
            ↓
TransformationDecompositionRequest.accounting_input
            ↓
decompose_transformation()
  ├─ provider RETAIN/REMOVE proposal
  ├─ apply frozen baseline allocations when available
  ├─ provider added-work rows
  └─ run_staged_pipeline(
       accounting_input,
       support_work_override=accounting_input.support_work,
     )
            ↓
  host support override wins over provider row amounts
            ↓
domain.accounting.account_absolute() or account_normalized()
            ↓
  deterministic W0, W1, removed/support ratios, and effect
```

The provider receives transformation context, the operational decomposition, and the prior classification, but not `accounting_input` (`src/task_decomposition/providers/_shared.py:55-84`). This keeps accounting authoritative outside the provider, but means the provider cannot derive or validate the host's quantities.

## Contract and orchestration evidence

`TransformationDecompositionRequest.accounting_input` is required and accepts only `AbsoluteEffortInput | NormalizedAccountingInput` (`src/task_decomposition/contracts/provider.py:35-48`). There is no default accounting input. The convenience `decompose()` rejects `None` before any provider call (`src/task_decomposition/application/provider_service.py:19-44`). The staged pipeline likewise rejects unsupported or missing accounting input (`src/task_decomposition/application/staged_pipeline.py:32-67`).

`decompose_transformation()` receives the already-built request and passes `request.accounting_input` into `run_staged_pipeline()` at `src/task_decomposition/application/transformation_decomposition.py:43-72`. It also passes `request.accounting_input.support_work` as `support_work_override`. Therefore, for the canonical application path, host support values are selected before deterministic accounting and provider row amounts are not used to replace them.

The request's accounting values are not included in the added-work provider payload. The added-work payload contains task, transformation context, operational decomposition, and prior RETAIN/REMOVE classification (`src/task_decomposition/providers/_shared.py:65-83`). This is an intentional ownership boundary: providers propose semantic rows, while callers provide accounting facts.

## Origin of each quantity

### W0 / baseline human effort

In absolute mode, W0 originates in `AbsoluteEffortInput.baseline_human_effort`, which is a required `EffortQuantity` alongside retained and removed quantities (`src/task_decomposition/contracts/effort.py:106-115`). In normalized mode, W0 is fixed deterministically to `Decimal("1")` in `account_normalized()` (`src/task_decomposition/domain/accounting.py:96-105`); callers provide retained and gross-removed ratios that must sum to one.

The library does not calculate W0 from the LLM decomposition. Baseline allocations can be created during task decomposition from supplied baseline effort or effort weights (`src/task_decomposition/application/task_decomposition.py:80-88`), but the transformation request still requires the caller to provide an accounting input (`src/task_decomposition/contracts/provider.py:35-48`). The example uses a hardcoded `EffortQuantity(value=100, ...)` at `examples/openai_decompose.py:178-182` and passes it to `_derive_accounting_input()` at lines 279-287.

### Removed-work effort

In absolute mode, removed work originates in `AbsoluteEffortInput.gross_removed_work`. In normalized mode, it originates in `NormalizedAccountingInput.gross_removed_work_ratio` (`src/task_decomposition/contracts/effort.py:106-124`). The accounting domain validates that retained plus removed equals W0 or one, then calculates ratios; it does not infer removed work from labels (`src/task_decomposition/domain/accounting.py:96-123,148-166`).

The example derives retained and removed quantities from the classification and allocated relative weights before constructing `AbsoluteEffortInput` (`examples/openai_decompose.py:126-175`). The tests instead construct fixed fixtures: `make_absolute_accounting()` supplies 100 baseline, 60 retained, and 40 removed (`tests/test_staged_pipeline.py:147-160`), while normalized fixtures supply 0.60 and 0.40 (`tests/test_staged_pipeline.py:163-171`).

The application can reconcile caller quantities with classified rows when complete row effort or ratio allocations are present (`src/task_decomposition/application/staged_pipeline.py:88-184`). If classification rows have no effort/ratio fields, the handoff returns without row-level reconciliation (`src/task_decomposition/application/staged_pipeline.py:96-97,160-161`).

### AI_INTERACTION and AI_VERIFICATION quantities

Support quantities originate in `SupportWorkInputs.ai_interaction` and `.ai_verification`, both required fields (`src/task_decomposition/contracts/effort.py:99-104`). Each `SupportWorkInput` requires an explicit basis and, for absolute effort, unit and time basis (`src/task_decomposition/contracts/effort.py:62-96`). The values may represent absolute effort, normalized contribution, a ratio of baseline work, or a ratio of gross removed work; the accounting domain converts them according to the declared basis (`src/task_decomposition/domain/accounting.py:47-82`).

The canonical transformation caller passes those two host values as `support_work_override` (`src/task_decomposition/application/transformation_decomposition.py:67-72`). The final accounting uses the override and computes added human work as interaction plus verification (`src/task_decomposition/application/staged_pipeline.py:46-63`; `src/task_decomposition/domain/accounting.py:109-144,180-212`).

The example explicitly constructs both categories as zero-valued absolute support with `EffortUnit.EFFORT` per operation (`examples/openai_decompose.py:178-195`) and later passes the same zero support into the final input (`examples/openai_decompose.py:279-287`). Test fixtures use hardcoded values, commonly 8 interaction and 6 verification (`tests/test_provider_application.py:102-111`), or zero values in direct accounting fixtures (`tests/test_staged_pipeline.py:157-160,165-171`).

## Defaults versus explicit zero

There are three distinct cases:

1. **Missing accounting input:** not defaulted. The request model requires it, and `decompose()` raises `MissingAccountingInputError` when it is `None` (`src/task_decomposition/contracts/provider.py:35-48`; `src/task_decomposition/application/provider_service.py:19-27`).
2. **Explicit host zero:** represented by a `SupportWorkInput(value=0, ...)` with a declared basis and compatible metadata. The example and tests use this form (`examples/openai_decompose.py:183-195`; `tests/test_staged_pipeline.py:157-160`).
3. **Empty provider added-work category in the derived path:** if no support override is supplied, `_sum_support_values()` creates an explicit zero. Absolute zeros inherit the baseline unit/time basis; normalized zeros use `NORMALIZED_CONTRIBUTION` (`src/task_decomposition/application/staged_pipeline.py:222-234`).

An added-work row with `amount=None` is not an explicit zero. Direct row-derived conversion raises `MissingAccountingInputError` (`src/task_decomposition/application/staged_pipeline.py:189-198`). In the canonical transformation path, however, the explicit host support override bypasses row amount aggregation, so a row can be semantically present but quantitatively ignored in favor of host values. That is precedence, not an implicit zero default.

## Can host values contradict LLM-added-work rows?

Yes. The contradiction is representable and is not rejected by the current canonical path. The provider can return nonempty `AI_INTERACTION` or `AI_VERIFICATION` rows with amounts, while the host supplies different support values—or explicit zeros—and `decompose_transformation()` uses the host override (`src/task_decomposition/application/transformation_decomposition.py:56-72`; `src/task_decomposition/application/staged_pipeline.py:46-63`). Existing tests explicitly establish this precedence by removing provider row amounts while retaining successful explicit accounting (`tests/test_provider_application.py:265-277`).

This is not an accounting formula defect: providers are non-authoritative for metrics, and explicit host accounting is the selected source. It is a traceability/reconciliation risk because the returned result retains the provider rows but does not mark whether their amounts were overridden or compare their category totals to host support values. The current tests verify precedence, not contradiction diagnostics.

The reverse contradiction is also possible at the semantic level: the provider may return an empty added-work array while the host supplies nonzero interaction or verification support. The accounting result will include the host support, but no added-work row explains it. The library permits this because host accounting is explicit and provider rows are semantic proposals, not authoritative accounting inputs.

## Actual callers in this checkout

### Example caller

`examples/openai_decompose.py` is the only non-test executable caller found. It first probes classification, allocates a hardcoded 100-unit baseline by LLM relative weights, derives retained and removed effort from the labels, hardcodes zero interaction and verification support, and then constructs the final `TransformationDecompositionRequest` (`examples/openai_decompose.py:178-215,257-297`). This is an illustrative provider-driven workflow, not a frontend or persisted workflow model.

### Test callers

Tests construct accounting fixtures directly. `tests/test_provider_application.py:102-111` uses 100/60/40 with 8/6 support; `tests/test_staged_pipeline.py:147-171` covers absolute and normalized fixtures; `tests/test_mathematical_validation.py:42-73` builds support values for known-answer accounting; and `tests/test_provider_parity.py:117-138` reuses explicit accounting across OpenAI, Gemini, and DeepSeek fakes.

Tests also intentionally exercise missing and conflicting conditions: missing row amounts fail in direct staged conversion (`tests/test_staged_pipeline.py:340-355`), mixed support bases fail (`tests/test_staged_pipeline.py:357-389`), explicit support overrides provider amounts (`tests/test_provider_application.py:265-277`), and accounting/classification effort mismatches fail when row allocations are present (`tests/test_staged_pipeline.py:392-405`).

### Production callers

No application frontend, workflow model, database adapter, or production service caller that constructs `TransformationDecompositionRequest` was found in this checkout. Repository documentation references an external `AgenticAICompass` integration, but that consumer is not present as writable source here; the local package exposes only the library contracts and example/test callers. Therefore the origin of host values in the actual deployment cannot be inferred from this repository. The examples and tests are not evidence that production values are frontend-derived, workflow-derived, calculated, or defaulted.

## Risks

### High — host and provider support quantities can diverge silently

Explicit support inputs override provider row amounts without a reconciliation event or result flag. A nonzero provider row with host zero, or an empty provider result with host nonzero support, can produce a numerically valid result whose semantic and accounting representations disagree.

### Medium — production input origin is outside this repository

The library requires host values but contains no production caller or source-of-truth model for them. It cannot establish whether deployed values originate from frontend input, workflow state, a calculation, a default, or hardcoded configuration.

### Medium — no-row allocation path weakens removed-work reconciliation

When classified rows lack effort/ratio allocations, `_validate_effort_handoff()` accepts explicit retained and removed totals without comparing them to labels (`src/task_decomposition/application/staged_pipeline.py:88-184`). This is documented repository behavior, not a newly introduced formula error, but it allows host removed-work values to be independent of the LLM classification.

### Low — zero support is semantically opaque without caller provenance

The numeric value zero is valid and explicit when represented by `SupportWorkInput`; it is not possible from the final accounting object alone to tell whether zero came from an intentional host estimate, an empty derived category, or a host override that ignored provider rows. The current trace does not record that provenance.

## Final recommendation

**Audit only; no code changes recommended in this task.** The verified architecture intentionally makes host accounting inputs authoritative and keeps providers from inventing metrics. Any future correction should be an explicitly approved observability/reconciliation change that records input origin, override use, and final accounting provenance; it should not silently alter precedence, accounting formulas, or added-work taxonomy.
