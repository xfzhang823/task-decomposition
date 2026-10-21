# Task Decomposition Architecture Audit

## 1. Executive summary

The repository has a coherent two-stage ownership model:

```text
decompose_task() -> TaskDecomposition -> decompose_transformation()
  -> TransformationDecompositionResult
```

Task decomposition owns operational subtasks and baseline effort allocation. Transformation decomposition consumes that existing decomposition, adds RETAIN/REMOVE and added-work facts, and hands concrete inputs to the deterministic accounting domain. Providers propose untrusted semantic facts; `domain/accounting.py` owns the W0/W1 mathematics.

The main architectural strengths are explicit Pydantic contracts, behavioral interfaces separated from data schemas, a provider-independent application layer, isolated optional SDK imports, and a single accounting authority. The current test suite passes (`273 passed, 6 skipped` after the interfaces migration), and an AST-based scan found no internal import cycles.

### Post-audit migration status

The approved `ports/` → `interfaces/` migration is complete. Provider protocols now live in `src/task_decomposition/interfaces/provider.py`, and `SemanticEvaluator` lives in `interfaces/semantic_evaluator.py`. The unused alternate effort-allocation protocol and request/result schemas were removed; deterministic allocation remains in `domain/allocation.py`. The obsolete `ports/` package and `evaluation/ports.py` are no longer part of the tracked source tree. Root-level public symbols are preserved; obsolete submodule paths are intentionally not.

The migration and Phases 1–4 added-work, public-API, provider-helper, and documentation canonicalization resolve the former interface/data-schema, validation-compatibility, shared-provider-logic, and category-drift findings. Remaining findings concern packaging dependency ownership, direct accounting input optionality, and provider/tracing module size.

The most important findings are:

1. **Medium — packaging contradicts provider optionality.** `pyproject.toml` puts `openai`, `black`, `pylance`, and `pylint` in core dependencies while also declaring provider extras. This makes the distribution heavier than the documented optional-provider boundary and duplicates/conflicts with the OpenAI extra.
2. **Resolved in Phase 2 — validation is independent of support-work mode.** Added-work validation now unconditionally requires valid REMOVE causal sources in `validation/stages.py`; host/estimate/auto only selects support quantities.
3. **Medium — accounting input optionality leaks across the boundary.** `support_work` is optional on the public accounting input contracts, while the domain functions require concrete support values. The application resolves it before calling the domain, but direct domain callers can receive a later, less-specific failure.
4. **Medium — provider/tracing module size remains maintainability debt.** Phase 4 consolidated shared JSON/contract mapping and transport-error classification. The OpenAI adapter is 650 lines and tracing is 509 lines; SDK-specific lifecycle code remains intentionally local because the provider response surfaces differ. This is maintainability debt, not evidence that the current flow is incorrect.
5. **Resolved — documentation category drift.** The root README and accounting reference now identify `AI_INTERACTION` and `AI_VERIFICATION` as the canonical support categories.
No evidence was found for circular imports, provider-side W0/W1 calculation, task regeneration during transformation decomposition, or an implemented scenario/simulation subsystem. No dead production module was removed or asserted without stronger usage evidence.

## 2. Current architecture and execution flow

### Public flow

`README.md` and `src/task_decomposition/application/README.md` describe the canonical flow. A caller first creates a `TaskDecompositionRequest` and invokes `decompose_task()`:

1. `application/task_decomposition.py` calls the provider's operational-decomposition capability through `_provider_stage.call_stage()`.
2. `validation/stages.py` validates the provider response against the operational contract.
3. The application invokes the semantic evaluator contract. A rejected or repairable result can trigger provider repair, followed by structural and semantic validation again.
4. Baseline effort is allocated by the host allocator or supplied allocation data, producing `TaskDecomposition`.

The resulting `TaskDecomposition` is then passed unchanged into `decompose_transformation()` in `application/transformation_decomposition.py`:

1. The provider classifies every baseline subtask as RETAIN or REMOVE.
2. The application applies the existing baseline allocation to classified rows and validates the classification.
3. The provider proposes added-work rows. Cross-stage validation checks source IDs, references, category rules, and retained-work overlap. Every runtime row follows the same causal rule.
4. `application/added_work_estimation.py` resolves reference-class estimates and host/estimate/auto support selection.
5. `application/staged_pipeline.py` validates the effort handoff and sends concrete inputs to `domain/accounting.py`.
6. The domain computes canonical W0/W1, ratios, multiplier, and effect classification. The application returns `TransformationDecompositionResult` with provenance and support-resolution diagnostics.

### Provider interaction

`interfaces/provider.py` defines capability protocols. `providers/openai.py`, `providers/gemini.py`, and `providers/deepseek.py` adapt vendor SDKs to `ProviderStageResponse`. Prompts live in `providers/prompts.py`; provider output is parsed and validated before it can cross the application boundary. Provider adapters do not own authoritative accounting metrics.

Tracing is opt-in through `tracing.py`. It records provider/stage lifecycle, safe request metadata, responses, validation, and failures in JSONL/console forms. Sensitive keys and values are redacted by the tracing layer.

## 3. Module ownership and dependency map

| Area | Primary modules | Responsibility |
| --- | --- | --- |
| Public composition | `src/task_decomposition/__init__.py`, `application/provider_service.py` | Public exports and convenience composition only |
| Task application | `application/task_decomposition.py`, `application/_provider_stage.py` | Task orchestration, validation, evaluator/repair policy, allocation handoff |
| Transformation application | `application/transformation_decomposition.py`, `application/added_work_estimation.py`, `application/staged_pipeline.py` | Transformation orchestration, added-work resolution, support selection, accounting handoff |
| Contracts | `contracts/*.py` | Pydantic request, stage, effort, accounting, and provenance schemas |
| Behavioral interfaces | `interfaces/provider.py`, `interfaces/semantic_evaluator.py` | Provider and evaluator protocols |
| Provider adapters | `providers/*.py` | SDK calls, prompts, structured parsing, provider provenance |
| Validation | `validation/stages.py` | Structural and cross-stage invariants; not accounting formulas |
| Evaluation | `evaluation/*.py` | Semantic evaluator request/result/rubric and evaluator port |
| Deterministic domain | `domain/accounting.py`, `domain/allocation.py` | W0/W1 mathematics, ratio bases, normalized allocation invariants and tolerances |
| Observability | `tracing.py` | Opt-in trace lifecycle, redaction, persistence, and console output |

The effective dependency direction is:

```text
public API
  -> application orchestration
      -> interfaces/contracts/validation/evaluation
      -> provider interfaces (injected adapters)
      -> domain accounting
providers -> contracts, prompts, provider utilities, tracing
domain -> contracts/errors/allocation only
```

An AST scan of internal imports found no cycles. Optional provider SDK imports are kept inside adapter construction/use rather than required by core package imports, but package metadata currently weakens that isolation (Finding F-1).

## 4. Findings

### F-1 — Core dependency metadata conflicts with the optional-provider boundary

**Severity: Medium. Confirmed.**

`pyproject.toml:7-28` places `black`, `openai`, `pylance`, and `pylint` in `[project].dependencies`, then declares separate provider extras. The OpenAI package is therefore both a core dependency and an optional dependency, with different lower bounds. This conflicts with the repository's documented optional SDK/provider isolation and makes a minimal core installation carry provider and tooling packages.

**Impact:** packaging behavior, install size, and dependency ownership are unclear; changes to provider SDK requirements can affect all consumers.

**Recommendation:** move development tools to the dev dependency group and keep provider SDKs only in provider extras, after checking published-consumer requirements. This is a packaging change, not a runtime redesign.

### F-2 — Added-work validation mode is indirectly selected by support-work mode

**Severity: Medium. Confirmed policy seam.**

Phase 2 removed the mode argument and branch. `validate_added_work_classification()` now rejects every row without at least one known REMOVE source, regardless of `SupportWorkMode`.

**Impact:** rows without causal attribution are now rejected consistently. Existing callers must provide valid source IDs or return no added-work rows.

**Disposition:** resolved. No legacy read or compatibility mode is retained in the runtime validator.

### F-3 — Optional support fields are accepted by domain input contracts

**Severity: Medium. Confirmed boundary weakness.**

`contracts/effort.py:106-124` allows `support_work=None` on both `AbsoluteEffortInput` and `NormalizedAccountingInput`. The application resolves support inputs before calling `account_absolute()`/`account_normalized()` (`application/staged_pipeline.py:50-63`), so the normal transformation path is concrete. However, the public domain functions receive those models directly and their helpers expect concrete support values.

**Impact:** a direct caller can construct a valid-looking input and receive a downstream attribute/type failure instead of a focused missing-support error. The optionality is useful at the transformation request boundary, but it is weaker as a domain accounting contract.

**Recommendation:** keep request-boundary optionality and add an explicit boundary check before domain math, or introduce a narrow concrete-input type for direct accounting calls. Do not change formulas or `domain/accounting.py` semantics without known-answer tests.

### F-4 — Provider adapters and tracing are oversized and repeat lifecycle logic

**Severity: Medium. Confirmed maintainability concern; no current functional failure established.**

`providers/openai.py` is 650 lines and `tracing.py` is 509 lines. Gemini and DeepSeek retain parallel SDK-specific configuration, stage dispatch, and response extraction; Phase 4 moved shared JSON/contract mapping and transport-error classification into `providers/_shared.py`.

**Impact:** provider-specific changes require navigating large modules and can produce parity drift across adapters; tracing changes have a broad blast radius.

**Disposition:** Phase 4 complete for the demonstrated shared parser and transport-error paths. Keep the remaining provider-specific lifecycle code; extract further seams only when a concrete parity problem is demonstrated. Avoid a generic provider framework.

### F-5 — Accounting documentation uses superseded added-work category names — Resolved

**Severity: Low. Resolved.**

`docs/reference/ACCOUNTING_MODEL.md` and the root README now describe added work as the `AI_INTERACTION` and `AI_VERIFICATION` support contributions, including explicit zero-category behavior.

No runtime or accounting change was required.

### F-6 — Legacy and reference-class added-work paths coexist — Resolved

**Resolved in Phases 1 and 2.**

`application/added_work_estimation.py` is now the sole resolver for reference-class, host, and estimate-derived support. `run_staged_pipeline()` accepts only the already-resolved concrete support input; row-level amount aggregation and override fallback were removed in Phase 1.

There is now one support resolver and one unconditional causal validator. No legacy staged-pipeline or validation mode remains.

### Positive boundary observations

- `domain/accounting.py` is the sole location for canonical W0/W1 calculations; application code prepares inputs rather than duplicating formulas.
- Transformation decomposition consumes `TaskDecomposition` and does not regenerate operational subtasks.
- `TaskDecompositionRequest` and transformation request contracts are separate; tests explicitly reject the retired `transformation_intent` shape.
- Provider responses are structurally validated and semantic evaluation is represented by a separate evaluator contract.
- The test suite includes accounting invariants, allocation handoff, provider parsing, boundary checks, and optional-provider behavior. The ordinary suite is credential-free.
- No scenario, simulation, Monte Carlo, grid-search, workforce-planning, or alternative-management orchestration was found in `src/task_decomposition`.

## 5. Recommended target architecture

The current architecture is close to the appropriate target. No broad redesign is justified. The target should retain the same flow and ownership:

```text
typed request boundary
  -> application orchestration and validation
      -> provider capability interfaces / optional adapters
      -> concrete accounting-input handoff
          -> domain/accounting.py
```

The incremental target changes are:

1. Keep host/estimate/auto support selection at the application boundary, independent of causal validation.
2. Make the domain accounting boundary reject unresolved support inputs with a focused contract error before entering mathematical helpers.
3. Keep `AddedWorkEstimate` as metadata plus a focused resolver; do not create a separate estimation pipeline. The resolver should remain the only place that converts reference-class facts to support inputs.
4. Reduce packaging dependencies so core imports and installs remain provider-neutral.
5. Accounting documentation now matches the current category contracts.
6. Extract provider/tracing internals only when a concrete change needs the seam; preserve the current ports and public exports.

## 6. Prioritized, incremental refactoring roadmap

### P0 — Correctness and contract clarity

1. Fix the duplicated semantic-evaluation error text.
2. Keep strict causal source validation centralized in `validation/stages.py`; no compatibility selector is required.
3. Add a focused unresolved-support contract check at the accounting handoff boundary, with known-answer and failure tests.

### P1 — Packaging and documentation

4. Move development-only packages out of core dependencies and reconcile provider extras after checking package consumers.
5. Update `README.md` and `docs/reference/ACCOUNTING_MODEL.md` to describe `AI_INTERACTION`/`AI_VERIFICATION` support as resolver-owned, with no row-level accounting amount.

### P2 — Maintainability, only when touched

6. Extract a small shared provider stage/configuration seam after measuring actual parity drift or repeated fixes across adapters.
7. Split tracing by stable responsibility (safe normalization, lifecycle/event emission, sinks) only if tracing changes continue to require broad edits.
8. Keep the Phase 1 canonical added-work accounting path covered by regression tests; no legacy amount path remains.

## Audit method and evidence boundary

This audit inspected the package tree, public exports, contracts, application orchestration, provider adapters/prompts, validation/evaluation layers, domain accounting, tests, documentation layout, and package metadata. Findings marked confirmed are directly visible in the cited files. Recommendations marked as maintainability work are not claims of current runtime failure. The current verification snapshot is `pytest -q`: `273 passed, 6 skipped`; a static AST import scan found no internal import cycles. The interface relocation is a resolved follow-up to this audit, not a new open finding.
