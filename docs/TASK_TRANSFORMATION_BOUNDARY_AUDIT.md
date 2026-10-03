# Task / Transformation Boundary Audit

**Scope:** S2A-1, audit only **Repository:** `/home/xzhang/dev/task_decomposition` **Reference:** `/home/xzhang/dev/AgenticAICompass` (read-only) **Date:** 2026-10-02

This report compares the intended task-decomposition boundary with the current standalone implementation and its history. No production code or Bot0 file was changed for this audit.

## 1. Intended conceptual architecture

The design evidence supports three composable capabilities:

1. Task decomposition turns a task/process into an operational decomposition with stable subtasks, dependencies, and a reusable baseline effort allocation.
2. Transformation decomposition consumes that frozen decomposition plus a transformation context. It classifies subtasks as `RETAIN` or `REMOVE` and identifies new governance, operational/support, and lifecycle work.
3. Transformation accounting consumes those facts and explicit quantities. It deterministically derives W0, W1, gross removal, net remaining work, net substitution, net augmentation, and effect.

The resulting dependency direction is:

```text
task decomposition
        ↓
transformation decomposition
        ↓
transformation accounting
```

This is stated most directly by the staged Path B description in `AgenticAICompass/docs_local/task_decomposition/PATH_A_PATH_B_EQUIVALENCE_AUDIT.md` and by the target flow in `TARGET_EXTRACTION_ARCHITECTURE.md`. The migration plan also separates the operational decomposition and classification stages from deterministic accounting. The documents are design evidence, not proof that the current standalone API implements the separation.

The important reuse property is that one reviewed operational decomposition can be supplied to many transformation alternatives. Regenerating the baseline for every alternative would confound transformation comparisons and would make effort baselines unstable.

## 2. Current call graph

The current public provider-driven path is:

```text
task_decomposition.decompose(request, provider)
  ├─ provider.generate_operational_decomposition(
  │    OperationalDecompositionRequest(request))
  ├─ _call_stage(...)
  ├─ validate_operational_decomposition()
  ├─ provider.classify_retain_remove(
  │    RetainRemoveClassificationRequest(request, operational))
  ├─ _call_stage(...)
  ├─ validate_retain_remove_classification()
  ├─ provider.classify_added_work(
  │    AddedWorkClassificationRequest(request, operational, classification))
  ├─ _call_stage(...)
  ├─ validate_added_work_classification()
  └─ run_staged_pipeline(
       operational, classification, added_work, request.accounting_input,
       support_work_override=request.accounting_input.support_work)
       ├─ validate_stage_chain()
       ├─ validate effort handoff
       ├─ derive support inputs from added rows or explicit override
       └─ account_absolute() or account_normalized()
```

Concrete locations are:

- `application/provider_service.py:32-100` implements the combined public orchestration.
- `application/provider_service.py:110-170` checks stage response type, stage identity, provenance, and stage validators.
- `application/staged_pipeline.py:32-85` performs the provider-independent handoff to Wave 1 accounting.
- `application/staged_pipeline.py:88-187` checks row effort/ratio handoff.
- `application/staged_pipeline.py:189-263` derives support inputs from added work rows.
- `domain/accounting.py:97-218` contains the deterministic formulas.

The three generation/classification stages are therefore not merely exposed as a sequence of independently callable application capabilities. They are always driven by `decompose()` when invoked through the application service, and the path cannot finish without accounting input.

## 3. Current contract ownership

### Naturally task-decomposition oriented

- `contracts/stages.py:14-22`, `TaskReference`, identifies the source task.
- `contracts/stages.py:24-35`, `OperationalSubtask`, represents a stable operational unit, sequence, description, dependencies, and provenance.
- `contracts/stages.py:37-45`, `OperationalDecomposition`, is already a useful standalone baseline artifact.
- `contracts/provider.py:37-40`, `OperationalDecompositionRequest`, is the current request wrapper for generating that artifact.
- `domain/allocation.py:20-61`, `allocate_effort`, is a deterministic utility that can support freezing baseline effort, although the current application does not call it as a task-only service.

### Naturally transformation-decomposition oriented

- `contracts/stages.py:47-88`, `ClassifiedSubtask` and `RetainRemoveClassification`, classify an existing operational baseline.
- `contracts/stages.py:91-127`, `AddedWorkCategory`, `AddedWorkItem`, and `AddedWorkClassification`, represent new human work.
- `contracts/provider.py:42-60`, the classification request wrappers, carry the existing decomposition into transformation stages.
- `validation/stages.py:69-133` validates classification identity, cardinality, order, added-work IDs, and dependencies.

There is no explicit aggregate named `TransformationDecomposition`; the two classification outputs are carried separately and later joined only in `StagedDecompositionResult`.

### Naturally transformation-accounting oriented

- `contracts/effort.py:59-132` defines explicit absolute and normalized quantities, support-work bases, units, and time basis.
- `contracts/accounting.py:23-45`, `CanonicalTransformationImpact`, is the deterministic result.
- `domain/accounting.py:97-218` implements normalized and absolute accounting.

### Mixed contracts

- `contracts/provider.py:23-34`, `DecompositionRequest`, combines a task, transformation intent, free-form context, accounting input, request ID, and provenance. It is the main boundary violation.
- `contracts/provider.py:37-60` wraps that mixed request in all three stage request types. The operational stage therefore receives a request that includes transformation and accounting concerns even though provider implementations omit accounting from their payload.
- `contracts/stages.py:129-139`, `StagedDecompositionResult`, combines all three stage artifacts with the canonical accounting result. It is a useful compatibility/integration result, but not a single capability contract.

## 4. Provider-protocol findings

`ports/provider.py:14-34` defines one `DecompositionProvider` protocol with three methods:

- `generate_operational_decomposition`;
- `classify_retain_remove`;
- `classify_added_work`.

These methods are logically two capabilities: task decomposition and transformation decomposition. They are currently grouped because they share provider configuration, transport, model selection, and provenance handling. The concrete OpenAI, Gemini, and DeepSeek providers implement the same three methods; their provider IDs are not domain semantics.

The smallest restoration is not to duplicate provider objects. Keep the existing composite protocol for compatibility, and define conceptual or structural sub-protocols later so one concrete provider can satisfy both:

```text
TaskDecompositionProvider
  generate_operational_decomposition(...)

TransformationDecompositionProvider
  classify_retain_remove(...)
  classify_added_work(...)
```

The existing `DecompositionProvider` can remain a compatibility composition of those capabilities. This avoids a transport/configuration split and keeps Bot0's current provider factory working.

## 5. Effort-allocation findings

Effort can enter through several paths:

1. `ClassifiedSubtask` may carry absolute `effort` or a W0-based `baseline_effort_ratio` (`contracts/stages.py:56-78`).
2. `AbsoluteEffortInput` or `NormalizedAccountingInput` is required by `decompose()` and `run_staged_pipeline()`.
3. `staged_pipeline.py:88-187` checks that row-level effort, when present, agrees with the aggregate accounting input.
4. Bot0's `_EffortAllocatingProvider` in `app/services/assumption_trail/task_decomposition_adapter.py` supplies row effort after the classification provider returns. It calls standalone `allocate_effort` and is needed because Bot0 persistence and candidate projection expect effort-bearing classified rows.

Conceptually, baseline effort allocation belongs with task decomposition:

```text
operational decomposition
  + baseline allocation
  = frozen reusable baseline
```

The current runtime does not establish that boundary. A provider can emit row effort during classification, or Bot0 can inject it in its wrapper, while the application also requires aggregate accounting input. This is sufficient for the current combined path but not an independently finalized baseline.

`ports/effort_allocator.py:12-40` defines an `EffortAllocator` port, but the standalone application does not call it. The port is therefore a possible future boundary aid, not current evidence of task-only effort allocation. No change to effort semantics is recommended in this audit.

## 6. Transformation-context findings

The proposed transformation enters through `DecompositionRequest`:

- `task` is baseline task identity and description;
- `transformation_intent` is explicitly transformation-specific;
- `context` is an untyped string map that can contain either baseline or transformation information;
- `accounting_input` is accounting-specific and not reasoning context.

The operational request is built from the full `DecompositionRequest` in `provider_service.py:50-56`. The concrete providers serialize task, `transformation_intent`, and `context` for operational generation. For example, `providers/openai.py:62-66` includes all three. Gemini and DeepSeek use the shared stage payload with the same semantic fields.

Thus task decomposition currently receives transformation intent. The classification stages correctly need that intent, but the baseline stage should not need to know which proposed transformation will later be tested. The current request is consequently a mixed task/transformation/accounting boundary rather than a clean task request followed by a transformation request.

## 7. Accounting-boundary findings

The accounting boundary is substantially correct and independently testable.

- `domain/accounting.py:97-148`, `account_normalized`, uses W0 = 1.0.
- `domain/accounting.py:151-218`, `account_absolute`, validates units and balance, then computes W0/W1 and all canonical ratios.
- The domain imports contracts and standalone errors, not providers, Bot0, or application services.
- `tests/test_accounting.py` exercises accounting without an LLM.

The coupling is in `run_staged_pipeline`, not in the formulas. It consumes the three stage outputs and builds support inputs before calling Wave 1. A caller can call `account_absolute()` or `account_normalized()` directly, but there is no named transformation-decomposition aggregate that an accounting service consumes. The combined pipeline also allows an explicit support-work override, added in commit `3c4259d`, which means application-level accounting input can supersede row-derived support amounts.

No mathematical redesign is indicated. S2A-2 should add a narrow handoff or accounting-input adapter if needed, while retaining `account_absolute()` and `account_normalized()` as the mathematical authority.

## 8. Current public API capability matrix

### A. Task decomposition only: NO

There is no public application operation that accepts only a task/process and returns an `OperationalDecomposition`. `decompose()` requires a provider that implements all three stages and an explicit accounting input. The provider method can be called directly, but that bypasses application orchestration and does not provide a task-only service contract.

`validate_operational_decomposition()` is public validation, not task decomposition generation.

### B. Transformation decomposition only: PARTIALLY

The contracts and validators can classify a supplied operational decomposition without regenerating it. `validate_retain_remove_classification()` and `validate_added_work_classification()` are independently usable. However, there is no public application operation that runs both transformation stages against a frozen decomposition and stops before accounting. The available `run_staged_pipeline()` requires accounting input and returns a combined result.

### C. Accounting only: YES

`account_absolute()` and `account_normalized()` are root-exported and can be called with explicit Wave 1 inputs. This is deterministic accounting only, but the input is a quantity contract rather than a named aggregate of transformation-decomposition facts.

Minimum future public capabilities are therefore:

- `decompose_task(...) -> OperationalDecomposition` plus frozen effort data;
- `decompose_transformation(existing_decomposition, context, provider) ->` classification and added-work facts;
- `account_transformation(explicit_accounting_input) ->` `CanonicalTransformationImpact`;
- existing `decompose(...)` retained as a composed compatibility façade.

## 9. Exact Bot0 compatibility requirements

Bot0 currently depends on the combined path, not independent task and transformation services.

- `app/services/assumption_trail/task_decomposition_adapter.py:359` imports `task_decomposition.decompose` dynamically.
- `run_standalone_decomposition()` constructs a standalone `DecompositionRequest` and calls `decompose()` with `_EffortAllocatingProvider`.
- `_EffortAllocatingProvider.classify_retain_remove()` fills row effort using `allocate_effort` when the provider does not return it.
- The adapter projects `StagedDecompositionResult` into Bot0 candidate, review, export, and serialization contracts.
- `standalone_provider_factory.py:7-19` imports the root protocol and all three concrete provider/config pairs.
- Bot0 tests `tests/app/services/assumption_trail/test_task_decomposition_adapter.py` and `test_wave5a_generation_cutover.py` import standalone stage, effort, provenance, and provider symbols.

The compatibility requirements are therefore to preserve the current root `decompose` signature/behavior, `DecompositionProvider`, stage request and response shapes, `StagedDecompositionResult`, and `allocate_effort` while the new explicit APIs are introduced. No Bot0 change is required for the first boundary refactor if the façade remains compositional.

## 10. Original-design evidence

The intended separation is supported by the reference architecture:

- `PATH_A_PATH_B_EQUIVALENCE_AUDIT.md` describes Path B as operational decomposition, RETAIN/REMOVE, added workload, then workload accounting.
- `TARGET_EXTRACTION_ARCHITECTURE.md` separates staged generation and deterministic accounting/finalization in the standalone core.
- `EXTRACTION_MIGRATION_PLAN.md` maps staged generation to application orchestration and Path A accounting to the domain.
- `STANDALONE_PUBLIC_CONTRACT.md` distinguishes provider proposals from canonical deterministic outputs.

These documents establish the original conceptual architecture, but they do not prove that a task-only public service was ever implemented in this standalone repository.

## 11. Git-history evidence

The standalone history is short and shows the collapse happened at initial provider orchestration rather than through a later accidental merge:

- `ffe1d43` created the repository scaffold.
- `81fb138`, titled `feat(accounting): implement canonical task transformation semantics`, introduced the canonical contracts, accounting, and allocation. It did not introduce a task-only application API.
- `98cd8a8` (`feat(decomposition): add staged decomposition and validation pipeline`) added operational, classification, added-work contracts, validation, and `run_staged_pipeline`.
- `14af572` (`feat(providers): add provider ports and decomposition orchestration`) introduced the three-method provider protocol and the combined `application/provider_service.py:decompose()` method. Git blame attributes the current `decompose()` body to this commit.
- `3c4259d` added the concrete providers and later added the support-work override to the combined handoff.

`git show 98cd8a8` shows `staged_pipeline.py` was created as a complete stage-to-accounting pipeline. `git blame` shows no prior standalone task-only service or subsequent refactor that collapsed two existing services. Commit messages do not explain why the combined façade became the only application entry point. The evidence supports: the conceptual separation was planned in the migration/audit documents, while the implementation initially optimized for one provider-driven end-to-end operation.

## 12. When/how the concepts became combined

The combination occurred when `14af572` added provider orchestration. The provider protocol exposed operational generation and both transformation classifications together, and `decompose()` immediately invoked all three before accounting. This was not a later change to an already separate public API. It is best characterized as an end-to-end convenience implementation that was never decomposed into independent application services.

The current implementation still retains useful internal boundaries: the operational output is validated before classification, classification is validated before added work, and accounting is delegated to Wave 1. The missing boundary is at the public application capability level and in the mixed request contract, not in the deterministic formulas.

## 13. Test-impact analysis

Current tests map as follows:

- `tests/test_accounting.py`: transformation accounting, including canonical ratios and effect behavior.
- `tests/test_domain_utilities.py`: effort allocation and baseline-row aggregation.
- `tests/test_staged_pipeline.py`: stage validation, effort handoff, support derivation, and accounting composition.
- `tests/test_provider_application.py`: combined provider orchestration, stage sequencing, provenance, and validation gates.
- `tests/test_openai_provider.py`, `test_gemini_provider.py`, and `test_deepseek_provider.py`: concrete adapter behavior.
- `tests/test_provider_parity.py`: equivalent provider outputs through the current combined path.
- `tests/test_import_boundary.py` and `tests/test_smoke.py`: package/import boundary checks.

Missing independent coverage:

- task decomposition generation and validation without transformation intent or accounting;
- transformation classification against a fixed decomposition without a provider operational-generation call;
- two transformation alternatives sharing the same frozen decomposition and effort allocation;
- an explicit three-service integration test rather than only the combined `decompose()` test.

## 14. Semantic-benchmark impact

S4B should persist or otherwise identify a reviewed baseline artifact before evaluating transformations. The minimum benchmark identity should include:

- canonical process/task reference;
- operational decomposition version or content hash;
- stable subtask IDs, sequence, and dependency graph;
- frozen baseline effort allocation and units/time basis;
- review/provenance metadata appropriate to the benchmark host;
- transformation alternative identity and transformation context;
- transformation classifications, added-work rows, and canonical accounting.

Every alternative must reference the same baseline decomposition hash. For example, a reviewed insurance-claim process should be evaluated once, then used by copilot, agent, and workflow alternatives. S4B must not regenerate the baseline as part of each alternative run, and should compare outcomes only after confirming baseline identity.

This is a benchmark contract recommendation, not a request to create the corpus in S2A-1.

## 15. Proposed restored call graph

The approved target has two primary application capabilities. Accounting is embedded in transformation decomposition; it is not a third sibling application service.

```text
decompose_task(task_request, task_provider)
  ├─ generate operational subtasks
  ├─ validate operational decomposition
  ├─ allocate or accept baseline effort/weights
  └─ return reusable task decomposition

decompose_transformation(transformation_request, transformation_provider)
  ├─ receive an existing reusable task decomposition
  ├─ receive transformation context/data, not transformation_intent
  ├─ classify RETAIN/REMOVE
  ├─ validate classification
  ├─ classify added/support work
  ├─ validate added work
  ├─ invoke domain/accounting.py with explicit quantities
  └─ return transformation result with canonical transformation impact

decompose(request, provider)
  └─ compatibility composition of decompose_task and
     decompose_transformation
```

The provider-generated operational output remains untrusted. Transformation decomposition must not regenerate a supplied baseline. The transformation application owns when accounting is invoked, while `domain/accounting.py` remains the sole mathematical authority.

## 16. Proposed module ownership

Reuse the existing package layout rather than add packages:

- `application/task_decomposition.py`: task-only generation, validation, and baseline effort/weight handoff.
- `application/transformation_decomposition.py`: classification and added work against an existing decomposition, followed by the accounting handoff.
- `application/provider_service.py`: compatibility façade composed from the two primary application capabilities.
- `application/staged_pipeline.py`: retain as a lower-level deterministic stage-to-accounting primitive and compose it from transformation decomposition; it is not a third public capability.
- `domain/accounting.py`: retain as the sole mathematical authority.
- `contracts/stages.py`: retain stage artifacts; introduce a transformation result aggregate only if needed to make the approved boundary explicit.
- `contracts/provider.py`: establish separate task and transformation request/context semantics without carrying `transformation_intent` into the new APIs.
- `ports/provider.py`: represent task and transformation capabilities with the smallest clean protocol/interface change; concrete providers may implement both without duplicated clients or configuration.

These are proposed ownership locations, not changes made in this wave.

## 17. Proposed public API

The approved primary application surface is:

- `decompose_task(...)` for operational decomposition plus reusable baseline effort allocation/weights;
- `decompose_transformation(...)` for RETAIN/REMOVE, added/support work, deterministic accounting, and the transformation result;
- existing low-level `account_absolute()` and `account_normalized()` remain independently callable/testable domain functions;
- `decompose(...)` remains a compatibility/convenience composition.

There is intentionally no new peer application operation named `account_transformation(...)`. The task API must be usable without transformation context or data. The transformation API must accept an existing `OperationalDecomposition` and transformation context/data. Neither new API may use `transformation_intent` as canonical input.

## 18. Contracts reusable unchanged

The following are strong reuse candidates:

- `TaskReference`;
- `OperationalSubtask`;
- `OperationalDecomposition`;
- `ClassifiedSubtask`;
- `RetainRemoveClassification`;
- `AddedWorkCategory`;
- `AddedWorkItem`;
- `AddedWorkClassification`;
- `EffortQuantity`, `EffortUnit`, `TimeBasis`, and explicit `RatioBasis`;
- `AbsoluteEffortInput`, `NormalizedAccountingInput`, and support inputs;
- `CanonicalTransformationImpact`;
- `ProviderStageResponse` and `ProviderProvenance`.

They already preserve stable IDs, explicit support bases, and canonical metric names. The main issue is how they are grouped and requested, not their core field semantics.

## 19. Contracts requiring change, if any

S2A-2 should make the task/transformation boundary explicit with the smallest request changes:

- add or split task-only request semantics so task generation does not require transformation context or accounting input;
- add transformation request semantics that contain an existing task decomposition and actual transformation context/data;
- remove `transformation_intent` from the proposed canonical APIs rather than moving it to another new request;
- introduce a transformation result aggregate only if the existing classification outputs and `CanonicalTransformationImpact` cannot be clearly associated without one;
- make baseline effort allocation/weights part of the reusable task-decomposition result or its explicit associated artifact.

The production `DecompositionRequest` field is not removed in this documentation-only wave. It may remain at the historical compatibility façade while it is excluded from the new canonical architecture. Do not alter canonical metric formulas or reinterpret historical Path B ratio bases.

## 20. Compatibility façade recommendation

Retain `decompose()` temporarily. It should become an implementation of the approved composition, not the architectural authority. Conceptually it should call `decompose_task(...)` once and pass that result to `decompose_transformation(...)`. This preserves the Bot0 call at `task_decomposition_adapter.py:359` and avoids a simultaneous cross-repository migration.

The façade may continue accepting the historical `transformation_intent` field for compatibility only. That field must not reach or define the new task-decomposition API, and transformation decomposition should use actual transformation context/data. The façade should preserve current provider response/provenance behavior and the final `StagedDecompositionResult` shape while independent capabilities become available.

## 21. Exact files expected to change during S2A-2

Standalone files likely to change:

- `src/task_decomposition/application/task_decomposition.py` (new);
- `src/task_decomposition/application/transformation_decomposition.py` (new);
- `src/task_decomposition/application/provider_service.py` (compose the façade);
- `src/task_decomposition/application/staged_pipeline.py` only as needed to remain the lower-level accounting handoff;
- `src/task_decomposition/application/__init__.py`;
- `src/task_decomposition/contracts/provider.py` (task/transformation request and context boundary);
- `src/task_decomposition/contracts/stages.py` only if a transformation result aggregate is required;
- `src/task_decomposition/ports/provider.py` only for the smallest capability distinction;
- `src/task_decomposition/__init__.py` for intentional exports.

`domain/accounting.py`, provider implementations, and prompts should not need changes for the boundary itself. Bot0 should not be changed in S2A-2 unless a separate migration is explicitly approved.

## 22. Exact tests expected to change or be added during S2A-2

Expected additions:

- `tests/test_task_decomposition_application.py`: process/task input, operational subtasks, baseline effort allocation/weights, and no transformation requirement;
- `tests/test_transformation_decomposition_application.py`: fixed reusable baseline, transformation context/data, RETAIN/REMOVE, added work, stage sequencing, accounting invocation, and no baseline regeneration;
- a test proving two transformations consume the same decomposition identity and frozen baseline effort allocation;
- domain-level accounting tests in `tests/test_accounting.py` for known numerical inputs and exact canonical outputs;
- a two-capability end-to-end test that composes `decompose_task(...)` and `decompose_transformation(...)`.

Expected updates:

- `tests/test_provider_application.py`: retain combined façade coverage while adding delegation and compatibility assertions;
- `tests/test_staged_pipeline.py`: keep lower-level accounting handoff tests;
- `tests/test_import_boundary.py`: cover any new public modules/exports.

Accounting tests are domain tests, not evidence for a third application capability. Existing provider parity and concrete-provider tests should remain unchanged unless signatures require compatibility fixtures.

## 23. Risks

- A request split could accidentally break Bot0's serialized request/result assumptions.
- Moving effort allocation before classification could change Bot0 row-effort behavior unless the current wrapper remains compatible.
- A new aggregate could duplicate `StagedDecompositionResult` without adding semantic value.
- An ambiguous generic context object could silently re-collapse task and transformation semantics.
- Separate provider protocols could create needless adapter/configuration duplication if implemented as separate concrete classes.
- Existing direct consumers of root exports may make an apparently internal contract public in practice.
- Benchmark comparisons remain invalid if baseline decomposition identity is not persisted or verified.

## 24. Resolved and remaining decisions

The six architecture decisions left open by the factual audit are resolved by the approved architecture below:

1. Baseline effort allocation/weights belong to task decomposition and must be reusable with the baseline.
2. Transformation decomposition consumes an existing baseline; it does not inherently regenerate it.
3. Accounting remains physically in `domain/accounting.py` and is invoked inside transformation decomposition; there is no third sibling application operation.
4. Transformation decomposition has a clear result association containing RETAIN/REMOVE, added/support work, and canonical transformation impact; the exact aggregate shape is an implementation detail for S2A-2.
5. Provider capabilities are semantically separate, while concrete providers may implement both with shared configuration and transport.
6. Bot0 row-level effort behavior remains unchanged for this restoration, and the combined façade remains for compatibility.

Remaining implementation details do not require a new architecture decision but must be handled carefully in S2A-2:

- whether future callers need richer typed fields beyond `task_context` and `transformation_context`;
- whether additional host effort allocators need adapters beyond the current baseline allocation mapping;
- whether Bot0's current row-level effort projection requires a separately approved migration after compatibility testing;
- whether the compatibility façade's historical request mapping needs additional caller-specific preservation rules.

## 25. Implementation sequence for S2A-2

1. Freeze current compatibility behavior with tests around `decompose()` and the Bot0-consumed root symbols.
2. Define task-only request semantics and return a reusable operational decomposition with baseline effort allocation/weights.
3. Add task-only application orchestration and validation without transformation intent.
4. Define transformation request semantics containing an existing operational decomposition and actual transformation context/data.
5. Add transformation-only orchestration and validation for RETAIN/REMOVE and added/support work.
6. Invoke the existing `domain/accounting.py` authority from transformation decomposition after facts and explicit quantities are validated.
7. Refactor `decompose()` into the compatibility composition of `decompose_task(...)` and `decompose_transformation(...)`.
8. Add frozen-baseline reuse and two-capability integration tests.
9. Verify Bot0 imports, row-level effort behavior, and result projection remain compatible without modifying Bot0.
10. Use the frozen-baseline contract to define S4B multi-transformation benchmark execution.

## 26. Factual audit findings versus approved decisions

The factual findings remain unchanged: the current implementation combines all three stages in `decompose()`, passes mixed request data including `transformation_intent` to operational generation, has no task-only or transformation-only public application operation, and first introduced the combined path in commit `14af572`. Those are observations about the repository and its history.

The approved post-audit architecture intentionally differs from that current state. It establishes two primary application capabilities, removes `transformation_intent` from the new canonical APIs, assigns reusable baseline effort to task decomposition, requires transformation decomposition to consume that baseline, and embeds the accounting invocation in transformation decomposition while preserving `domain/accounting.py` as the mathematical authority.

## 27. Approved Architecture Decisions

The following decisions are approved for S2A-2 and supersede the previously open alternatives in section 24:

- There are exactly two primary application capabilities: task decomposition and transformation decomposition.
- Task decomposition answers what work exists and returns operational subtasks plus reusable baseline effort allocation/weights.
- Transformation decomposition answers what happens to that work under actual transformation context/data and returns RETAIN/REMOVE, added/support work, and canonical transformation impact.
- Transformation decomposition consumes a fixed existing task decomposition and must not inherently regenerate it.
- `transformation_intent` is not part of either new canonical API. Its current production presence is a factual compatibility concern, not an approved design field.
- Accounting mathematics remain in `domain/accounting.py`. Transformation decomposition invokes those functions after validated transformation facts and explicit quantities exist.
- No application-level `account_transformation(...)` sibling is to be introduced unless future evidence establishes a separate public use case.
- A concrete provider may implement both semantic capabilities without duplicated configuration, SDK clients, transport, or authentication infrastructure.
- The historical combined `decompose(...)` may remain as a compatibility façade and should compose the two approved capabilities.
- S4B must persist or identify one reviewed baseline decomposition and evaluate multiple transformations against that same baseline and effort allocation.

## 28. S2A-2 implementation outcome

The boundary restoration implements the approved two-capability shape without changing the accounting domain or provider prompts. `application/task_decomposition.py` exposes `decompose_task(...)` and returns `TaskDecomposition` with validated operational subtasks and optional explicit baseline allocations. `application/transformation_decomposition.py` exposes `decompose_transformation(...)` and returns `TransformationDecompositionResult` containing the supplied baseline, validated classifications, added work, and canonical impact.

`TaskDecompositionRequest` contains task/process context, optional baseline effort, and explicit effort weights; it has no `transformation_intent`. `TransformationDecompositionRequest` contains an existing task decomposition, transformation context/data, and explicit accounting input. Baseline allocations are applied to classification rows before the existing `run_staged_pipeline(...)` handoff, so transformation evaluation uses the frozen baseline rather than regenerating or re-estimating it.

`ports/provider.py` now exposes `TaskDecompositionProvider` and `TransformationDecompositionProvider` capability protocols while retaining `DecompositionProvider` as the composite compatibility port. Concrete providers remain single implementations with shared configuration and transport. Provider-stage invocation and validation are shared through `application/_provider_stage.py`.

The historical `decompose(...)` remains compatible through an internal adapter. It composes the new task and transformation application operations, while adapting the legacy `DecompositionRequest` and its `transformation_intent` only at that compatibility boundary. The value is not part of or passed through the new task-decomposition contract.

Focused tests in `tests/test_task_transformation_boundaries.py` cover task-only execution, transformation-only execution over a fixed baseline, baseline reuse across two transformations, accounting handoff, compatibility composition, provider capability checks, and rejection of `transformation_intent` in the new task request. The full pre-existing suite remains covered separately.

The implementation uses the smallest additional result contracts needed to make the boundary explicit: `BaselineEffortAllocation`, `TaskDecomposition`, `TaskDecompositionRequest`, `TransformationDecompositionRequest`, and `TransformationDecompositionResult`. No third application-level accounting capability was added.

## 29. Overall assessment

The intended architecture is supported by the migration and Path A/Path B audit evidence. The current standalone implementation has good internal validation and accounting boundaries, but its only application-level generation entry point combines task decomposition, transformation classification, and accounting. The combined behavior began in the first provider-orchestration commit (`14af572`), not through a documented refactor of previously separate standalone services.

The approved restoration is a two-capability application split with accounting embedded in transformation decomposition and a retained compatibility façade. No accounting formula change, provider prompt change, Bot0 modification, or broad package redesign is justified by this audit.

**READY FOR S2A-3**
