# Canonicalization and Duplication Audit

## 1. Executive summary

The current runtime has one authoritative accounting implementation and one canonical public decomposition flow. The approved interfaces migration and Phases 1–3 added-work/public API consolidation are complete; remaining findings are unrelated provider/configuration and boundary-maintenance items:

```text
decompose_task()
  -> TaskDecomposition
  -> decompose_transformation()
  -> reference-class support resolution
  -> internal accounting handoff
  -> domain.accounting
```

Phase 1 has removed the duplicate added-work quantification path. `application/added_work_estimation.py` now resolves host or estimate support inputs, and `application/staged_pipeline.py` accepts only that concrete result before accounting.

The earlier `ports/` → `interfaces/` migration is resolved. Provider protocols are now under `interfaces/`, allocation schemas are under `contracts/allocation.py`, and `SemanticEvaluator` is under `interfaces/semantic_evaluator.py`. No old-path alias or re-export shim was introduced.

The added-work validation compatibility surface has been removed. Historical documentation may still contain obsolete API names as evidence, but those files are not executable behavior.

Phases 1–4 and the `ports/` → `interfaces/` migration are complete. Remaining items are packaging/input-boundary concerns and explicitly historical or external-consumer documentation matters; no canonicalization implementation phase remains open.

The audit’s Phase 1 recommendations were subsequently implemented; this document records the resulting ownership and remaining findings.

## 2. Scope and method

The audit inspected:

- all Python modules under `src/task_decomposition`;
- public exports and provider/application ports;
- all runtime and test references to legacy, compatibility, fallback, alias, and deprecated terms;
- direct callers of stage validation, staged orchestration, and accounting;
- active documentation, archived history, and the existing audit reports;
- the provider adapters and their shared helpers.

The distinction used here is important:

- **Runtime compatibility** is code that accepts an older contract, provides a fallback path, or maintains a parallel behavior. It is in scope for removal under the requested policy.
- **Provider transport adaptation** is not automatically duplication. OpenAI Responses, Gemini generation, and DeepSeek/OpenAI-compatible chat transport have different SDK response surfaces. Their transport-specific code should remain, while shared semantic contracts and common parsing responsibilities should have one owner.
- **Historical documentation** may mention removed APIs as evidence. It is not runtime compatibility, but active documentation must not present those names as current APIs.

## 3. Canonical execution and ownership map

### Actual public execution path

1. `application/task_decomposition.py:44-89` validates a `TaskDecompositionProvider`, calls the operational provider stage, invokes the semantic evaluator/repair policy, allocates baseline effort, and returns `TaskDecomposition`.
2. `application/transformation_decomposition.py:28-105` consumes that existing decomposition, calls RETAIN/REMOVE, applies the existing allocation to classification rows, calls added-work classification, validates the result, resolves support work, and invokes the staged handoff.
3. `application/added_work_estimation.py:27-115` is the deterministic reference-class estimator. It normalizes baseline references by reference frequency, validates external quantitative anchors, aggregates by `AI_INTERACTION` and `AI_VERIFICATION`, and selects host/estimate/auto support inputs.
4. Internal `application/staged_pipeline.py` validates the handoff and invokes `domain.accounting.account_absolute()` or `account_normalized()`; it is not a public application entry point.
5. `domain/accounting.py:85-214` is the sole W0/W1, ratio, multiplier, and effect authority.

### Ownership that should remain canonical

| Responsibility | Current authoritative owner | Assessment |
| --- | --- | --- |
| Operational decomposition orchestration | `application/task_decomposition.py` | Keep |
| Transformation orchestration | `application/transformation_decomposition.py` | Keep |
| Stage contracts | `contracts/stages.py`, `contracts/provider.py` | Keep |
| Cross-stage structural validation | `validation/stages.py` | Keep; one unconditional causal rule |
| Reference-class effort resolution | `application/added_work_estimation.py` | Keep as the only added-work estimator |
| W0/W1 and derived accounting | `domain/accounting.py` | Keep as the only mathematical authority |
| Baseline allocation | `domain/allocation.py` and task application handoff | Keep; not an added-work estimator |
| Provider capability boundary | `interfaces/provider.py` | Keep as canonical behavioral protocols; migration resolved |
| Semantic evaluation interface | `interfaces/semantic_evaluator.py` | Keep as the canonical evaluator protocol; migration resolved |
| Allocation data schemas | `contracts/allocation.py` | Keep as the canonical allocation contract; migration resolved |
| Provider transport adaptation | each provider adapter | Keep provider-specific transport; consolidate only common semantic helpers |
| Prompt definitions | `providers/prompts.py` | Keep |
| Safe tracing | `tracing.py` | Keep one tracing authority; possible later internal split |

## 4. Inventory of legacy and compatibility runtime code

### C-1 — Legacy added-work amount contract and row-derived accounting — Resolved

**Phase 1 complete.** `AddedWorkItem` no longer carries `amount`; `_support_inputs()`, `_sum_support_values()`, and `support_work_override` were deleted. `resolve_support_work()` is the sole support resolver, and `run_staged_pipeline()` requires its concrete result. Empty categories still resolve to explicit zero values and `domain/accounting.py` is unchanged.

Affected provider schemas, application callers, benchmark helpers, fixtures, and active documentation were migrated. The contract change is intentionally direct: callers must supply host support or computable estimates before the staged accounting handoff.

### C-2 — Legacy causal-attribution validation mode — Resolved

**Phase 2 complete.** `validate_added_work_classification()` has one signature and unconditionally requires each added-work row to contain at least one known source subtask classified `REMOVE`. The application no longer selects validation behavior from `SupportWorkMode`; `validate_added_response()` has no compatibility parameter. Missing, unknown, duplicate, and RETAIN causal sources are rejected by the single validator authority.

Provider fixtures and prompts now follow the same rule. Empty `added_work_rows` remains valid, so removing a baseline subtask does not itself force added work.

### C-3 — Composite provider “compatibility” port — Resolved

**Resolved.**

`interfaces/provider.py:45-51` defines `DecompositionProvider` as the composition of the task and transformation protocols. `application/provider_service.py:21-50` and its tests use it for the convenience `decompose()` flow; all three concrete providers satisfy it.

The composition itself is not duplicate provider logic: `decompose()` genuinely needs both capabilities. The migration retained it as the canonical combined capability, removed the compatibility wording, and moved it with the other behavioral protocols. No further deletion is recommended for this finding.

### C-4 — Historical/obsolete API references in documentation

**Confirmed documentation residue, not runtime behavior.**

Historical records under `docs/history/` and `docs/audits/`, plus explicitly historical sections of topic documentation, mention removed names such as `DecompositionRequest`, `transformation_intent`, `_CompatibilityProvider`, `BenchmarkPort`, and `build_standalone_request`. `docs/verification/FINAL_VERIFICATION.md` explicitly says these names are historical and absent from production.

Disposition: keep archived audit/history evidence, but ensure `docs/README.md` and current reference documents do not link to those names as current guidance. Do not delete historical evidence as part of a code canonicalization phase.

### C-5 — Configuration fallback lookup

**Confirmed fallback, but not necessarily legacy.**

`providers/_shared.py:46-52` resolves a stage-specific token budget from a mapping and falls back to a provider default. This is ordinary configuration precedence, not a parallel contract or obsolete API. It should remain unless the intended contract changes to require every stage explicitly.

Disposition: keep. It has one owner and deterministic precedence.

### C-6 — Interface/data-schema package ownership — Resolved

The former `ports/` package mixed protocols with allocation Pydantic models, and `evaluation/ports.py` held a protocol outside the interface package. The migration now places behavioral protocols in `interfaces/` and allocation request/result schemas in `contracts/allocation.py`. Root-level exports remain available, while obsolete module paths are absent. This finding is closed.

## 5. Duplication and ownership matrix

| Overlap | Current locations | Proposed canonical owner | Disposition |
| --- | --- | --- | --- |
| Added-work quantitative calculation | `application/added_work_estimation.py` | `application/added_work_estimation.py` | Keep; Phase 1 removed the duplicate row-amount path |
| Causal source enforcement | `validation/stages.py` | `validation/stages.py` | Keep; Phase 2 removed mode branching |
| Stage invocation/error normalization | `application/_provider_stage.py`; provider adapter try/except blocks | Application stage boundary for provider-neutral errors; adapters for SDK-specific mapping | Keep split; remove only redundant adapter wrapping after parity review |
| Structured payload parsing | `providers/_shared.py:parse_model_payload`; OpenAI `_parse_structured`; Gemini/DeepSeek local parsing | Shared semantic contract parser where response shape permits; provider transport parser where it does not | Merge common mapping; keep SDK-specific response extraction |
| Stage output-token configuration | `_shared.py:stage_output_tokens`; three provider `ProviderConfig.output_tokens_for()` methods | One provider-neutral configuration helper, if signatures can be made identical | Consolidate in a later provider-maintenance phase; no functional deletion yet |
| Operational/RETAIN/REMOVE/added-work validation | `validation/stages.py`; `_provider_stage.py` wrappers; `validate_stage_chain()` | `validation/stages.py` | Keep stage validators; wrappers should remain orchestration adapters, not second validators |
| Absolute and normalized accounting | `domain/accounting.py:account_absolute`, `account_normalized` | `domain/accounting.py` | Keep: units and ratio semantics are genuinely distinct |
| Baseline allocation and added-work estimation | `domain/allocation.py`; `application/added_work_estimation.py` | Separate owners | Keep separate: baseline allocation weights are not added-work estimates |
| Task/transformation composition | `provider_service.decompose`; `decompose_task`; `decompose_transformation` | `provider_service.decompose` as composition only | Keep; no duplicate decomposition logic found |
| Staged result vs transformation result | Internal accounting impact; `TransformationDecompositionResult` | `TransformationDecompositionResult` | Resolved: delete redundant staged result contract and keep handoff internal |
| Provider implementations | OpenAI, Gemini, DeepSeek adapters | Each adapter for transport; shared contracts/prompts/helpers | Keep provider-specific transport; do not merge into one vendor abstraction |

## 6. Unused code and unnecessary abstractions

No production module can be safely labeled dead from repository evidence alone:

- The staged handoff is used only by transformation orchestration and focused internal tests; it is no longer a public application or root export.
- `StagedDecompositionResult` was deleted; the internal handoff returns `CanonicalTransformationImpact` directly.
- `DecompositionProvider` is used by `decompose()` and provider/application tests.
- `AddedWorkItem.amount` was removed in Phase 1; benchmark and fixture consumers now use estimates or resolved accounting inputs.
- `domain.accounting.aggregate_baseline_rows()` is used by domain utility and mathematical-validation tests.

The added-work amount/estimate and causal-validation mode overlaps were consolidated in Phases 1 and 2.

## 7. Target package structure

No package-wide restructuring is justified. The existing ownership boundaries are already appropriate. The target should be a smaller version of the current structure:

```text
application/
  task_decomposition.py          # task orchestration
  transformation_decomposition.py # transformation orchestration
  added_work_estimation.py       # only added-work resolver
  staged_pipeline.py             # concrete handoff, no alternate support path
contracts/
  allocation.py                  # allocation request/result schemas
  ...                            # one current contract per boundary
interfaces/
  provider.py                    # provider protocols
  effort_allocator.py            # allocator protocol
  semantic_evaluator.py          # evaluator protocol
domain/
  accounting.py                  # only W0/W1 mathematics
providers/
  provider-specific transport    # shared prompt/contract helpers only
validation/
  stages.py                      # one strict structural authority
```

Do not create a new estimation pipeline, provider framework, scenario layer, or accounting abstraction. The needed change is deletion of parallel paths, not addition of another coordinator.

## 8. Dependency-aware deletion and consolidation plan

### Phase 1 — Canonical added-work accounting — Complete

1. `AddedWorkEstimate` plus `resolve_support_work()` is the only estimate-derived support path.
2. `AddedWorkItem.amount`, `_support_inputs()`, `_sum_support_values()`, and `support_work_override` are deleted.
3. The internal staged handoff receives the already-resolved concrete support input; `domain/accounting.py` is unchanged.
4. Empty added-work categories resolve through the single resolver to explicit zero values.

Completed caller/test/doc updates include `application/staged_pipeline.py`, `transformation_decomposition.py`, provider schema tests, staged/application/math/semantic fixtures, benchmark rendering, application README, automation-classification reports, and current reference docs.

Behavioral test requirements: estimate mode, host mode, auto precedence, missing estimates, external anchors, zero categories, unit compatibility, and canonical W0/W1 known answers. No accounting formula changes are allowed.

### Phase 2 — Remove legacy causal validation — Complete

1. Removed the `compatibility` argument and legacy default from `validate_added_work_classification()` and `validate_added_response()`.
2. Require nonempty causal source IDs and REMOVE classification for every runtime added-work row.
3. Removed the support-mode conditional in `transformation_decomposition.py`.
4. Updated provider fixtures and tests to provide causal IDs or assert rejection.

Affected callers/tests: `validation/stages.py`, `application/_provider_stage.py`, `application/transformation_decomposition.py`, added-work taxonomy tests, boundary tests, provider fixtures, and prompt/schema tests.

### Phase 3 — Resolve public staged/composite API duplication — Complete

1. Repository inspection found no independent production caller of staged execution; direct uses were limited to tests and documentation.
2. Staged execution is now private to transformation decomposition, returns `CanonicalTransformationImpact`, and is absent from application/root exports.
3. `DecompositionProvider` remains the canonical combined interface required by `decompose()`.

Affected callers/tests/docs for the completed migration: root exports, `application/__init__.py`, provider service, interfaces README, public README, provider application tests, and any external integration. No further changes are pending for this item.

### Phase 4 — Provider helper consolidation — Complete

1. `_shared.parse_model_payload()` is the single owner for JSON decoding and stage-contract mapping used by Gemini and DeepSeek. DeepSeek no longer duplicates JSON decoding for generation stages or semantic evaluation; its provider-specific response extraction remains local.
2. `_shared.raise_provider_failure()` is now also the OpenAI owner for transport exception classification. OpenAI-specific evaluation parse errors and Responses API status/refusal handling remain local because they have distinct semantics.
3. `_shared.stage_output_tokens()` and `validate_stage_output_tokens()` remain the shared owners of stage override lookup and validation. The three configuration `output_tokens_for()` methods remain as thin provider configuration accessors because their fallback fields and provider configuration contracts differ (`max_output_tokens` versus `max_tokens`).
4. OpenAI Responses extraction/schema canonicalization, Gemini `generate_content()` extraction, and DeepSeek chat-completions extraction remain provider-specific. No generic provider framework was introduced.

Focused provider, parity, tracing, and token-budget tests pass. No decomposition, validation, or accounting logic changed in this phase.

## 9. Public API and test impact matrix

| Change | Public impact | Required test updates |
| --- | --- | --- |
| Remove `AddedWorkItem.amount` | Breaking provider/stage contract; callers now use host support or estimates | Completed: contract, provider parsing, staged pipeline, benchmark fixtures |
| Remove `support_work_override` | Lower-level staged callers must resolve support before handoff | Completed: staged-pipeline and application handoff tests |
| Strict causal IDs always required | Rows without REMOVE sources become invalid | Completed: validator, provider fixtures, and rejection tests |
| Keep `SupportWorkMode` | No API removal; remains the single selection policy | Host/estimate/auto precedence tests |
| Keep absolute/normalized accounting functions | No accounting API change | Existing known-answer and invariant suite |
| Hide staged execution and remove `StagedDecompositionResult` | Direct utility callers must move to transformation application; result-contract imports break | Completed locally; external consumers remain unverifiable |
| Keep `DecompositionProvider` | Canonical combined capability remains required by `decompose()` | Provider protocol tests and examples |

## 10. Remaining uncertainty requiring inspection

1. **External consumers:** the accessible AgenticAICompass checkout has no removed staged/interface imports, but its deterministic demo still constructs the removed `AddedWorkItem.amount` contract; that consumer migration remains external to this repository. Other remote consumers remain unverifiable; no compatibility shim was added.
2. **Persistence:** no local persistence layer was found. External persisted rows using the removed amount field require an external migration; this library intentionally provides no compatibility path.
3. **Provider wire contracts:** local provider schemas and fixtures now match the amount-free contract; live integrations should still be smoke-tested by consumers.
4. **Historical docs policy:** archived audit records retain obsolete identifiers as evidence. They are not runtime shims; current README/reference guidance does not expose those identifiers.
5. **Direct accounting callers:** `domain/accounting.py` is correctly authoritative, but direct callers may rely on optional support input behavior. Confirm before tightening the domain input boundary.

## 11. Verification

At Phase 4 completion:

- `pytest -q`: 273 passed, 6 skipped.
- Focused provider suite: 87 passed (`openai`, `gemini`, `deepseek`, parity, token-budget, and tracing tests).
- AST-based internal import scan: no cycles found.
- Provider import/compile checks passed.
- `ruff format --check src tests`: passed.
- `git diff --check`: passed.
- Documentation links in `docs/README.md` and this audit: valid.
- Full Ruff still reports 64 pre-existing repository issues outside this focused provider change.
- Isolated `compileall` passed using `PYTHONPYCACHEPREFIX=/tmp/task-decomposition-pycache-phase4`.

## 12. Final canonicalization status

Phases 1–4 are complete: added-work resolution, causal validation, the public decomposition surface, and genuinely shared provider helper behavior each have one canonical owner. The `ports/` → `interfaces/` migration is also complete with no aliases or re-export shims. The public surface is `decompose_task()`, `decompose_transformation()`, `decompose()`, the contracts, validation functions, domain accounting functions, and behavioral interfaces. Remaining provider duplication is justified by SDK response and transport differences. No canonicalization blocker remains inside this repository; packaging, direct accounting-input tightening, documentation category wording, and external consumer migration are separate follow-up work.
