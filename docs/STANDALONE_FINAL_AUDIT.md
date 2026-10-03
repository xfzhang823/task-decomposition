# Standalone Final Audit — S1

**Scope:** audit only. No production cleanup, API redesign, deletion, move, or
Bot0 change was performed.

**Audited repository:** `/home/xzhang/dev/task_decomposition`

**Reference repository:** `/home/xzhang/dev/AgenticAICompass`

**Observed revision:** `96394af` (`uv lock`). The worktree also contains one
unrelated untracked `tree.py`; the ignored local `.env`, build output, caches,
and `src/task_decomposition.egg-info/` were not modified.

## 1. Repository structure

The repository is now a real `src/`-layout package, not the empty scaffold
described by the original Phase 3 migration document.

```text
task_decomposition/
  src/task_decomposition/
    contracts/       # Pydantic value objects and staged/result contracts
    domain/          # deterministic accounting and row allocation
    validation/      # structural and semantic stage validation
    application/     # typed staged and provider-driven orchestration
    ports/           # provider, effort, and benchmark protocols
    providers/       # OpenAI, Gemini, DeepSeek adapters and prompts
    errors.py
    __init__.py      # broad root public export surface
  tests/             # 66 collected tests
  examples/
    openai_decompose.py
  README.md
  pyproject.toml
  uv.lock
  main.py            # tracked hello-world entry point
```

There is no `docs/` directory before this report. The generated
`src/task_decomposition.egg-info/` directory exists locally but is ignored and
not tracked. `main.py` is not an installed package entry point and is not
referenced by the package or tests.

The original plan proposed additional modules such as
`contracts/lifecycle.py`, `contracts/results.py`, `domain/effects.py`,
`domain/finalization.py`, `validation/invariants.py`,
`application/staged_generation.py`, `application/finalize.py`, and
`application/export.py`. None exists. Their responsibilities are either
implemented in fewer modules or remain unimplemented.

## 2. Ownership map

The ownership map is:

- **Task/stage contracts:** standalone `contracts/stages.py` and
  `contracts/provider.py`; Bot0 maps input in `task_decomposition_adapter.py`.
  This is the correct staged-generation split.
- **Effort value objects:** standalone `contracts/effort.py`; Bot0 supplies
  explicit accounting and optional weights. Units and bases are standalone.
- **W0/W1 accounting:** standalone `domain/accounting.py`; Bot0 copies values
  into legacy DTOs. Standalone is authoritative for the migrated flow.
- **Row effort allocation:** standalone `domain/allocation.py`; Bot0’s
  `_EffortAllocatingProvider` invokes `allocate_effort()`. Policy/config stays
  Bot0-owned.
- **Stage validation:** standalone `validation/stages.py` and
  `validation/semantic.py`; Bot0 retains legacy schema/read/finalization
  validation. Responsibilities overlap at the compatibility boundary.
- **Provider execution:** standalone concrete providers; Bot0 factory selects
  them. This is the correct provider split.
- **Provider protocol:** standalone `ports/provider.py`; Bot0 adapters
  implement it. This is the correct port direction.
- **Review/approval/lifecycle:** not standalone; Bot0 lifecycle, wizard, and
  review services. This remains host policy, but the planned standalone
  finalization API is absent.
- **Persistence/API/frontend:** not standalone; Bot0 owns ORM, API, and UI.
- **Benchmark retrieval:** protocol only in `ports/benchmark.py`; no verified
  implementation. It is currently an unused extension point.

## 3. Internal dependency map

The observed standalone dependency direction is:

```text
contracts/errors
        ↑
domain ─┼─ validation
        ↑       ↑
application ───┘
        ↑
ports/provider
        ↑
providers (lazy vendor SDK imports)
```

Concrete edges include:

- `contracts/effort.py` → `errors.py`.
- `contracts/accounting.py`, `decomposition.py`, and `stages.py` → effort,
  provenance, and accounting contracts.
- `domain/accounting.py` → accounting, decomposition, effort contracts and
  accounting errors.
- `domain/allocation.py` → effort contracts and accounting errors.
- `validation/stages.py` → stage contracts, semantic assertions, and stage
  errors.
- `application/staged_pipeline.py` → stage validation and domain accounting.
- `application/provider_service.py` → provider contracts, provider port,
  stage validation, and `run_staged_pipeline`.
- Concrete providers → standalone contracts/prompts/errors; vendor SDKs are
  imported lazily inside provider builders only.
- `task_decomposition/__init__.py` → contracts, domain, application,
  validation, errors, and ports; it does not import concrete SDKs.

No standalone source import of Bot0, SQLAlchemy, FastAPI, workflow compute,
Anthropic, or another host framework was found. The import-boundary tests
enforce this result.

## 4. Boundary findings

Positive evidence:

- Core package import succeeds without vendor SDK imports.
- Provider SDKs are isolated behind concrete provider modules.
- The provider port uses only standalone request/response contracts.
- Domain accounting has no provider, environment, persistence, or host import.
- Provider output is wrapped as `ProviderStageResponse` and validated before
  stage advancement.

Risks:

- `providers/__init__.py` imports all adapter modules on
  `import task_decomposition.providers`; this is safe today because SDK imports
  are lazy, but it is a wider adapter import surface than direct submodules.
- `ProviderStageResponse.payload` is `Any` at `contracts/provider.py:63-70`.
  This is appropriate for an untrusted envelope, but callers that bypass
  `decompose()` can skip application validation.
- The root package exports domain, application, validation, and optional-port
  symbols together; the API is explicit but not minimal.
- Bot0 has already crossed the intended Wave 4 boundary: its service, adapter,
  provider factory, demo, and tests import standalone symbols.

## 5. Public API inventory

`src/task_decomposition/__init__.py:5-122` is the effective root API. It
exports:

- contracts: `AbsoluteEffortInput`, `NormalizedAccountingInput`,
  `EffortQuantity`, `EffortUnit`, `TimeBasis`, `RatioBasis`,
  `SupportWorkInput`, `SupportWorkInputs`, `TransformationRow`,
  `TransformationClassification`, `TaskReference`, all staged contracts,
  `StagedDecompositionResult`, provenance contracts, and accounting results;
- domain functions: `account_absolute`, `account_normalized`,
  `classify_effect`, `allocate_effort`, `aggregate_baseline_rows`;
- application functions: `decompose`, `run_staged_pipeline`;
- validation functions and semantic assertions;
- all error classes;
- `DecompositionProvider`, `EffortAllocator`, and `BenchmarkProvider`.

Concrete provider classes are exposed from
`task_decomposition.providers.openai`, `.gemini`, and `.deepseek`, not from
the root package.

Potentially internal-looking symbols currently public include
`TransformationRow`, `aggregate_baseline_rows`, `allocate_effort`, low-level
validators, and optional benchmark/effort ports. Their root `__all__` entries
make them public whether or not they are stable by policy.

## 6. Exact Bot0-consumed API

The exact direct imports found under AgenticAICompass are:

`app/services/assumption_trail/service.py:90`:

- `DecompositionProvider`
- `ProviderError`

`app/services/assumption_trail/task_decomposition_adapter.py:16-33`:

- `AbsoluteEffortInput`, `DecompositionProvider`, `DecompositionRequest`,
  `EffortQuantity`, `NormalizedAccountingInput`, `ProvenanceRef`, `RatioBasis`,
  `StagedDecompositionResult`, `SupportWorkInput`, `TaskReference`,
  `TimeBasis`, `EffortUnit`, `TransformationClassification`,
  `ProviderStageResponse`, `RetainRemoveClassification`, `allocate_effort`

The same adapter imports root `decompose` dynamically at `:359`.

`transformation_decomposition_demo.py:14-36` consumes:

- `AddedWorkCategory`, `AddedWorkClassification`,
  `AddedWorkClassificationRequest`, `AddedWorkItem`, `ClassifiedSubtask`,
  `EffortQuantity`, `EffortUnit`, `OperationalDecomposition`,
  `OperationalDecompositionRequest`, `OperationalSubtask`,
  `ProviderProvenance`, `ProviderStage`, `ProviderStageResponse`,
  `ProvenanceRef`, `RatioBasis`, `RetainRemoveClassification`,
  `RetainRemoveClassificationRequest`, `SupportWorkInput`, `TaskReference`,
  `TimeBasis`, and `TransformationClassification`.

`standalone_provider_factory.py:7` consumes root `DecompositionProvider` and
`:8-19` imports all three concrete provider/config pairs from submodules.
Bot0 tests additionally consume `SupportWorkInputs` and the same stage,
effort, classification, and provenance symbols.

Exact integration calls:

- `build_standalone_request_from_execution_input()` maps Bot0 execution input
  into standalone request data.
- `run_standalone_decomposition()` calls root `decompose()` through
  `_EffortAllocatingProvider`.
- `_EffortAllocatingProvider.classify_retain_remove()` calls root
  `allocate_effort()` when provider rows lack effort.
- `project_standalone_result_to_candidate()` reads the canonical result and
  creates Bot0 review/persistence DTOs.
- `project_legacy_path_a_export()` maps canonical
  `gross_removed_work_ratio` to the historical Bot0 field named
  `substitution_ratio`.
- `serialize_standalone_result()` and `deserialize_standalone_result()` use
  `StagedDecompositionResult` as the persisted JSON boundary.

This is concrete evidence that standalone is already a Bot0 runtime dependency,
despite older migration documents describing this adapter as future work.

## 7. Domain-model findings

Canonical standalone concepts are implemented as follows:

- `EffortQuantity` carries value, unit, and time basis.
- `SupportWorkInput` requires an explicit `RatioBasis`.
- `TransformationClassification` distinguishes `RETAIN` and `REMOVE`.
- `OperationalSubtask` carries stable identity, ordering, dependencies, and
  portable provenance.
- `AddedWorkItem` separates added work from baseline rows and restricts
  categories to governance, operational support, and lifecycle support.
- `CanonicalTransformationImpact` carries absolute/normalized values and
  derived metrics.
- `StagedDecompositionResult` joins validated stages with canonical accounting
  and provider provenance.

Duplicated or parallel concepts:

- Bot0 has a separate `TransformationRow` at
  `agent/assumption_trail/schemas/transformation_decomposition.py:208`, plus
  separate summary, review, export, and Bot0-ID models. It is not the same
  class as standalone `contracts/decomposition.py:17`.
- Bot0 has separate `OperationalSubTask`, `TransformationRow`, and summary
  objects in its review envelope. The adapter maps standalone rows into these
  objects at `task_decomposition_adapter.py:217-316`.
- Standalone `TransformationRow` is a lower-level utility not used by the
  staged provider path. It is used by `aggregate_baseline_rows()` and its
  standalone tests, while `ClassifiedSubtask` is the active staged model.
- Historical Bot0 Path A schemas/reasoning and Path B persisted envelopes
  remain compatibility models.

Missing planned concepts:

The target plan named portable lifecycle/finalization readiness and export
contracts. Standalone currently has no lifecycle enum, finalization guard,
finalization error, finalized export contract, or export application service.
Bot0 owns `Bot0FinalizationContext` and its finalization guard instead.

## 8. Accounting-authority findings

For standalone-backed execution, the single formula authority is
`src/task_decomposition/domain/accounting.py`:

- `account_normalized()` at lines 97-148 fixes `W0=1.0`;
- `account_absolute()` at lines 151-218 validates absolute units and balance;
- `classify_effect()` at lines 86-94 derives `GAIN`, `NEUTRAL`, or
  `DEGRADATION`;
- support basis conversion is `_support_to_normalized()` and
  `_support_to_absolute()` at lines 48-83;
- `aggregate_baseline_rows()` at lines 221-234 is a separate aggregation
  utility.

The implemented equations are:

```text
W0 = retained + gross removed
added = governance + operational support + lifecycle support
W1 = retained + added
gross removed ratio = gross removed / W0
net remaining ratio = W1 / W0
net substitution = 1 - net remaining ratio
net augmentation = W0 / W1
```

`W1 > W0` is unclamped and effect classification is derived.

Repository-wide authority is not yet singular. Bot0 still contains historical
Path A accounting in
`agent/assumption_trail/reasoning/transformation_decomposition.py`, and the
adapter re-expresses canonical values in legacy DTOs at
`task_decomposition_adapter.py:282-349` and `:470-536`.

Those are projections/compatibility calculations in the standalone-backed
path, but they are alternate formulas in the repository as a whole. Therefore:

- **single authority:** standalone `domain/accounting.py` for the migrated
  standalone flow;
- **not yet single repository-wide authority:** historical Bot0 Path A and
  Bot0 legacy validation/projection paths remain active.

`application/provider_service.py:80-85` passes
`request.accounting_input.support_work` as `support_work_override`. Explicit
caller accounting, not provider-added row amounts, is authoritative. This is
safe for accounting integrity, but means the added-work stage is not itself the
source of support amounts in provider-driven execution.

## 9. Staged-pipeline findings

The actual responsibility flow is:

```text
Bot0 execution input or standalone caller
  -> DecompositionRequest
  -> provider.generate_operational_decomposition()
  -> validate_operational_decomposition()
  -> provider.classify_retain_remove()
  -> validate_retain_remove_classification()
  -> provider.classify_added_work()
  -> validate_added_work_classification()
  -> explicit accounting/effort handoff
  -> run_staged_pipeline()
  -> account_absolute() or account_normalized()
  -> StagedDecompositionResult
  -> Bot0 compatibility/review/persistence projection
```

Evidence:

- sequencing is `application/provider_service.py:50-86`;
- response stage/provenance checks are lines 110-139;
- validation conversion to provider errors is lines 142-170;
- deterministic handoff is `application/staged_pipeline.py:46-85`.

The pipeline is provider-independent and fail-fast. It does not ask providers
for W0, W1, substitution, augmentation, or effect.

The main responsibility gap is finalization/export: standalone ends at
`StagedDecompositionResult`; the plan’s portable finalized artifact boundary
is not implemented.

## 10. Validation versus policy/domain ownership

Standalone validation/domain rules:

- Pydantic shape and non-negative effort validation are in contracts.
- Balance, units, ratio basis, denominator, and derived metrics are in domain
  accounting.
- Identity, cardinality, ordering, dependency references, and category shape
  are in `validation/stages.py:25-187`.
- Provider sequencing and provenance matching are in
  `application/provider_service.py:110-139`.

Policy-like rules currently in standalone:

`validation/semantic.py:11-57` has a hard-coded forbidden-phrase list and
operational-verb list. `assert_operational_subtasks_are_concrete()` at lines
71-89 rejects output without one of a fixed set of verbs. This is useful
provider-output safety validation, but it is heuristic semantic/process policy,
not purely mathematical domain validation. It requires S4B evidence before
its vocabulary or acceptance criteria are expanded.

Bot0 owns reviewer identity, review status, approval, finalization, audit
history, persistence, tenancy, and API policy. Its
`Bot0FinalizationContext` and `assert_bot0_finalization_ready()` in
`task_decomposition_adapter.py:539-543` are not standalone accounting rules.

## 11. Provider findings

Isolation evidence:

- OpenAI uses Responses structured parsing in `providers/openai.py:147-173`.
- Gemini uses `google-genai` JSON schema generation in
  `providers/gemini.py:84-113`.
- DeepSeek uses JSON mode through OpenAI-compatible Chat Completions in
  `providers/deepseek.py:87-127`.
- All three use the same stage contracts and shared prompts.
- All three have provider-specific IDs/configuration/defaults/provenance.
- SDK imports are lazy and concrete-provider-only.

Parity evidence:

`tests/test_provider_parity.py:66-89` drives equivalent fake outputs through
all three adapters and checks identical canonical results. Provider-specific
unit tests cover response mapping and failure wrapping.

This proves adapter parity for equivalent typed outputs, not semantic parity
of live model behavior. No live Gemini or DeepSeek credentials were available;
their optional smoke tests are not normal CI tests.

Provider risk: prompts are shared, but semantic assertions are English phrase
and verb heuristics. No realistic-process corpus shows that all three providers
produce acceptable granularity, dependencies, or support rows. That is an S4B
gap, not a reason to tune providers in S1.

## 12. Ports findings

Port findings:

- **`DecompositionProvider`:** `ports/provider.py:14-34`; consumed by Bot0’s
  factory/service. It is an active boundary for three providers and fakes.
  Classification: `KEEP_PUBLIC_API`.
- **`EffortAllocator`:** `ports/effort_allocator.py:12-40`; no standalone
  implementation/caller, while Bot0 uses direct `allocate_effort()`. It is
  conceptually justified for host-provided row effort, but currently unused
  and not wired into application orchestration. Classification: `UNKNOWN`.
- **`BenchmarkProvider`:** `ports/benchmark.py:10-30`; no implementation or
  caller. It is future optional lookup only. Classification: `INTERNALIZE` or
  defer public commitment.

The deterministic `allocate_effort()` function is actively consumed by Bot0 and
has standalone tests. The optional `EffortAllocator` port is not the current
allocation path.

## 13. Packaging/dependency findings

`pyproject.toml` declares Python `>=3.10`, package discovery under `src`, and
optional extras for `openai`, `gemini`, `deepseek`, and aggregate `providers`.
`uv.lock` contains the corresponding provider packages and extras.

Findings:

- Runtime dependencies include `black`, `pylance`, and `pylint` at
  `pyproject.toml:7-12`. These are development/static-analysis tools and are
  likely misclassified as runtime dependencies.
- `pytest` and `ruff` are in the dev dependency group, while `black` is
  duplicated in runtime and dev dependencies.
- DeepSeek reuses the OpenAI SDK, so its optional extra is valid but has no
  provider-specific SDK package.
- Aggregate `providers` installs OpenAI and Gemini; DeepSeek is covered because
  it uses OpenAI, but that relationship is implicit.
- Package description remains the placeholder `Add your description here` in
  `pyproject.toml:4` and generated metadata.
- No CI workflow, type-check configuration, or package release configuration
  is present in the standalone repository.

## 14. Generated-artifact findings

`src/task_decomposition.egg-info/` is generated by setuptools builds and is
ignored by `.gitignore`, but exists in the worktree and is included in its own
generated `SOURCES.txt`. It is not tracked. `build/`, `dist/`, bytecode,
pytest, Ruff, and virtual-environment artifacts are ignored.

Classification: `REMOVE_GENERATED_ARTIFACT` as worktree hygiene; no production
change was made in S1.

The untracked `tree.py` is not generated by the package and appears user-added.
It was not changed. The ignored `.env` was not inspected, staged, or modified.

## 15. Bot0/AgenticAICompass leakage

No standalone source import of Bot0, ORM, FastAPI, workflow compute, scenario
services, or Bot0 provider infrastructure was found. The intended dependency
direction is present: `AgenticAICompass -> task_decomposition`.

Bot0-specific concepts remain in its adapter boundary:

- workflow/version/tenant/candidate IDs;
- Bot0 review status and finalization context;
- legacy summary/export DTOs;
- persistence serialization;
- mapping of Bot0 provenance references.

The adapter carries those fields in its own `Bot0TaskDecompositionRequest`,
but does not pass that type into standalone contracts. This is correct leakage
containment, although the integration itself is already active.

## 16. Extraction/migration residue

The implementation is ahead of the original plan, but residue remains:

- README still says Wave 1 deliberately does not implement provider generation,
  even though later sections document concrete providers.
- The original plan’s lifecycle/finalization/export module set is absent.
- Bot0 historical Path A schemas/reasoning and Path B persistence remain
  active compatibility surfaces.
- Root `TransformationRow`/`aggregate_baseline_rows()` retain a Path A-shaped
  utility beside staged `ClassifiedSubtask`.
- `main.py` is the original hello-world scaffold and has no relationship to
  the package.
- The current example covers only OpenAI although three providers exist.
- The package description remains scaffold text.

These are not deletion-safe without caller and release decisions.

## 17. Dead/redundant code

Cleanup candidates:

- `main.py` hello-world `main()`: tracked, not imported or tested, and not a
  package entry point. Classification: `DELETE_DEAD`.
- `src/task_decomposition.egg-info/`: generated, ignored, and not tracked.
  Classification: `REMOVE_GENERATED_ARTIFACT`.
- `TransformationRow` and `aggregate_baseline_rows()`: separate utility path,
  covered only by standalone tests. Classification: `INTERNALIZE`.
- `EffortAllocator`: no implementation/caller; Bot0 uses direct allocation.
  Classification: `UNKNOWN`.
- `BenchmarkProvider`: no implementation/caller. Classification: `INTERNALIZE`.
- Root low-level validators: public but no direct Bot0 use found.
  Classification: `KEEP_PUBLIC_API` pending caller audit.
- OpenAI/Gemini/DeepSeek adapters: used by factory, tests, and parity.
  Classification: `KEEP_PROVIDER`.
- Shared provider helper: used by Gemini and DeepSeek.
  Classification: `KEEP_PROVIDER`.
- Stage/domain contracts: used by Bot0 and tests. Classification: `KEEP_CORE`.
- Bot0 adapter projection arithmetic: active compatibility caller.
  Classification: `MOVE_RESPONSIBILITY` later.
- Historical Bot0 Path A formulas: active historical/read/lifecycle surface.
  Classification: `KEEP_TEST` / `MOVE_RESPONSIBILITY`.
- Untracked `tree.py`: user worktree file, not package-owned.
  Classification: `UNKNOWN`.

No provider adapter is dead: all three are exercised by unit/parity tests and
Bot0’s factory can construct them.

## 18. Complete test inventory

The standalone suite collects 66 tests across 14 files:

Test ownership and coverage:

- `test_accounting.py`: Wave 1 formulas, modes, effects, degradation, ratio
  bases, and invalid inputs.
- `test_domain_utilities.py`: deterministic row allocation and aggregation.
- `test_staged_pipeline.py`: stage contracts, identity, dependencies,
  semantic assertions, and effort handoff.
- `test_provider_application.py`: orchestration, validation gates, provider
  failure, explicit accounting, and degradation.
- `test_openai_provider.py`: OpenAI mapping, errors, provenance, config, and
  full application.
- `test_gemini_provider.py`: Gemini mapping, errors, provenance, config, and
  full application.
- `test_deepseek_provider.py`: DeepSeek JSON mapping, errors, provenance,
  config, and full application.
- `test_provider_parity.py`: identical canonical results from equivalent
  outputs of all providers.
- `test_import_boundary.py`: core host/framework import boundary.
- `test_provider_import_isolation.py`: concrete SDK isolation from core import.
- `test_package_smoke.py`: root package/accounting smoke.
- `test_openai_smoke.py`, `test_gemini_smoke.py`, and `test_deepseek_smoke.py`:
  optional live-provider paths.

The three smoke tests skip without credentials. Normal tests are offline and
do not require API keys.

## 19. Testability gaps

- No installed-wheel test imports the built artifact in a fresh environment
  without provider extras.
- No test verifies environment-variable mapping without constructing an actual
  SDK client.
- No standalone test covers the complete Bot0 adapter-to-persistence path;
  those tests live in Bot0.
- No standalone persisted-result compatibility fixture exists; Bot0 owns that
  serialization/deserialization coverage.
- No property-based or fuzz testing exists for malformed provider envelopes or
  dependency graphs.
- No realistic human-process corpus exists for provider semantic quality.
- No test asserts that callers cannot bypass validation by directly invoking
  `run_staged_pipeline()` or constructing a result; the boundary is enforced by
  convention/application use rather than by type capability.

## 20. Mathematical/numerical validation gaps

Existing coverage is strong for the reference case and primary edge cases, but
S4A should add:

- tolerance boundary tests immediately below, at, and above
  `DEFAULT_TOLERANCE = Decimal("0.000000001")`;
- consistency tests between exact equality in
  `staged_pipeline.py:117-183` and tolerance-based balance checks in
  `domain/accounting.py:106-108` and `:166-168`;
- parameterized absolute/normalized equivalence for every support basis;
- very small, very large, repeating-decimal, and high-precision Decimal cases;
- explicit support-greater-than-gross-removed cases in both modes;
- invariants reconstructing `W1`, ratios, and augmentation reciprocals;
- all-zero support with positive W1 and the exact W1-zero boundary;
- classification effort and baseline-ratio reconciliation using tolerance;
- whether normalized result fields being `None` for absolute quantities is
  sufficient for downstream consumers;
- whether `aggregate_baseline_rows()` should enforce W0 balance or remain an
  aggregation-only primitive.

## 21. Semantic/process validation gaps

Current semantic validation is heuristic. It checks forbidden phrases and a
fixed operational-verb list, but does not establish:

- appropriate process granularity;
- collective coverage of the source task;
- useful dependency graphs beyond valid references/order;
- defensible RETAIN/REMOVE labels;
- genuinely new added work rather than renamed baseline work;
- consistent distinction among governance, operational support, and lifecycle
  work;
- preservation of important business controls;
- comparable semantic quality across providers.

S4B should define a realistic-process evaluation set and measure these as
validation/process outcomes. It should not tune prompts or create expected
provider outcomes from desired accounting metrics before the benchmark exists.

## 22. Example findings

`examples/openai_decompose.py` is concise and correctly demonstrates explicit
absolute accounting input at lines 41-50; it avoids asking the provider to
invent effort. It only demonstrates OpenAI and does not show Gemini/DeepSeek,
provider selection, or normalized mode.

There is no Gemini/DeepSeek example and no provider-selection example despite
README guidance to replace the provider import. This is an
`ADD_DOCUMENTATION` and possibly `ADD_TEST_COVERAGE` candidate, not a
production defect.

`main.py` remains a hello-world example that can mislead users into believing
the repository has a script entry point.

## 23. Documentation/math-explanation gaps

README coverage is good for primary equations and gross/net distinction, but
incomplete for a final public contract:

- no concrete multi-stage example shows task → subtasks → classifications →
  added work;
- units and time bases are named but not explained with conversion or
  compatibility examples;
- ratio bases are listed but their denominator behavior is not tabulated;
- no worked gross-removed-work-based support-ratio example;
- no worked support-greater-than-gross-removed example;
- no explicit numerical-range statement says support and W1 are not clamped;
- zero-baseline and zero-net behavior is not shown as input, error, and reason;
- provider sections do not show Gemini/DeepSeek code or explain DeepSeek’s
  OpenAI SDK transport reuse;
- the README contains a historical Wave 1 statement that is stale if read as a
  current capability statement;
- no release/compatibility policy identifies stable root symbols;
- no root `AGENTS.md` exists.

## 24. Proposed root `AGENTS.md` scope

S2 should add a concise root `AGENTS.md`, not a large architecture copy. It
should state:

1. package scope and the `src/task_decomposition` source root;
2. Python `>=3.10` and required verification commands;
3. ownership: contracts/domain/application/validation are provider-neutral;
4. provider SDKs are optional and isolated under `providers/`;
5. Wave 1 accounting is authoritative; providers never calculate final
   metrics;
6. explicit effort/accounting input is required; do not invent effort;
7. Bot0 is a read-only reference unless a task explicitly authorizes
   integration;
8. `.env` must never be read into reports, staged, or committed;
9. cleanup must preserve Bot0-consumed symbols until caller audit proves
   migration;
10. test, lint, import-boundary, package-build, and `git diff --check` commands.

## 25. Exact cleanup candidates and classifications

The exact cleanup classifications are:

- `main.py` hello-world: tracked, not imported or tested, and not a package
  entry point. `DELETE_DEAD`. Do not delete in S1.
- `src/task_decomposition.egg-info/`: generated, ignored, and not tracked.
  `REMOVE_GENERATED_ARTIFACT`. Do not remove in S1.
- `black`, `pylance`, and `pylint` runtime dependencies: tooling not imported
  by the package. `MOVE_DEV_DEPENDENCY`. Confirm policy in S2.
- Placeholder project description at `pyproject.toml:4`:
  `ADD_DOCUMENTATION`. Update in S2/S4C.
- `TransformationRow` and `aggregate_baseline_rows()`: separate utility path.
  `INTERNALIZE`, pending caller decision.
- `EffortAllocator`: no implementation/caller; future host extension.
  `UNKNOWN`. Decide whether it remains public.
- `BenchmarkProvider`: no implementation/caller. `INTERNALIZE` or defer to an
  optional extension.
- Root low-level validators: root-public, but no direct Bot0 use found.
  `KEEP_PUBLIC_API` until public API policy is approved.
- OpenAI/Gemini/DeepSeek adapters: used by factory, tests, and parity.
  `KEEP_PROVIDER`.
- Shared provider helper: used by Gemini and DeepSeek. `KEEP_PROVIDER`.
- Stage/domain contracts: used by Bot0 and tests. `KEEP_CORE`.
- Bot0 adapter projection arithmetic: active compatibility caller.
  `MOVE_RESPONSIBILITY` later; do not alter in S1.
- Historical Bot0 Path A formulas: active historical/read/lifecycle surface.
  `KEEP_TEST` / `MOVE_RESPONSIBILITY`; do not delete in S1.
- Untracked `tree.py`: user worktree file, not package-owned. `UNKNOWN`; do not
  touch.
- Ignored `.env`: local secret file. `UNKNOWN`; do not inspect, stage, or
  delete.

## 26. Proposed S2 scope

S2 should be cleanup planning and public-boundary hardening, not broad deletion:

- add the concise root `AGENTS.md`;
- decide stable root API versus internal symbols using the exact Bot0 caller
  list above;
- classify `TransformationRow`, aggregation helpers, and optional ports;
- move tooling-only dependencies out of runtime dependencies if packaging
  policy confirms no runtime use;
- update package description and metadata policy;
- document generated-artifact handling;
- define the missing finalization/export decision before adding modules;
- create caller-preserving tests for any API internalization;
- do not delete Bot0 historical paths yet.

## 27. Proposed S3 scope

S3 should implement only approved structural cleanup after S2 decisions:

- internalize or retain low-level symbols based on caller evidence;
- remove `main.py` only if the package/example entry-point decision is made;
- keep Bot0 compatibility projections and add explicit source-of-truth comments;
- split or add lifecycle/finalization/export modules only if the contract
  decision is approved;
- remove generated artifacts from release/build workflows, not by changing
  production semantics;
- preserve provider isolation and root import behavior;
- update lock/package metadata after dependency classification.

## 28. Proposed S4A mathematical-validation scope

S4A should add property/invariant and boundary tests for:

- W0 balance and W1 derivation;
- normalized/absolute equivalence across every explicit support basis;
- gross removal versus net substitution distinction;
- augmentation reciprocal relation;
- unclamped degradation;
- zero baseline and zero W1 errors;
- unit/time-basis compatibility;
- Decimal tolerance and rounding boundaries;
- support greater than gross removed;
- row allocation conservation and classification-to-accounting reconciliation;
- serialized/deserialized accounting preservation through the Bot0 adapter.

## 29. Proposed S4B semantic/process-validation scope

S4B should construct a realistic, provider-agnostic process corpus covering
intake, verification, exception handling, approvals, record updates,
notifications, recurring maintenance, and control/audit work.

It should validate:

- concrete operational work versus meta commentary;
- stable identity and stage cardinality under realistic outputs;
- useful ordering/dependency graphs;
- baseline coverage and no unexplained task loss;
- defensible RETAIN/REMOVE labels;
- distinct new support/governance/lifecycle work;
- absence of invented authoritative effort;
- cross-provider semantic parity and failure/abstention behavior;
- human review agreement and validator false-positive/false-negative rates.

S4B must define acceptance criteria from observed/process-owner evidence. It
must not tune prompts, providers, or expected outcomes to force desired
accounting results.

## 30. Proposed S4C documentation/guidance scope

S4C should revise README and examples to include:

- current capability status across Waves 1–3C;
- a compact worked staged example;
- a ratio-basis table with denominators;
- units/time-basis examples and incompatibility errors;
- W0/W1 and gross/net formulas;
- unclamped degradation and effect classification examples;
- zero-baseline and zero-net edge cases;
- provider selection for OpenAI, Gemini, and DeepSeek;
- explicit effort/accounting ownership;
- stable versus internal API policy;
- Bot0 adapter boundary and no-Bot0 core requirement;
- realistic-process test expectations and limitations.

## 31. Blockers

No blocker prevents this audit from completing.

Before cleanup or API narrowing, these decisions are required:

1. whether portable finalization/export/lifecycle contracts are still in scope,
   since the plan names them but implementation stops at staged results;
2. whether historical Bot0 Path A formulas remain compatibility authority or
   must be migrated behind explicit adapters;
3. whether `EffortAllocator` and `BenchmarkProvider` are committed public
   extension points or speculative ports;
4. whether low-level root exports such as `TransformationRow` and direct
   validators are stable public API;
5. whether support amounts should remain caller-accounting authority or become
   a separately validated stage handoff with explicit reconciliation;
6. what semantic/process quality S4B must measure before prompt/provider
   changes are considered.

## 32. Overall architectural assessment

The standalone repository has a coherent deterministic core and a clear
provider boundary. Its strongest property is authority separation:
`domain/accounting.py` owns canonical W0/W1 and derived metrics, while provider
outputs are staged, untrusted, validated, and unable to supply final metrics.
The three provider adapters are isolated and parity-tested for equivalent
typed outputs.

The repository is not yet a complete realization of the original target
architecture. Lifecycle/finalization/export responsibilities named in the plan
are absent, the root API is broader than a minimal public contract, optional
ports are not equally justified by callers, and Bot0 compatibility projections
plus historical Path A code mean repository-wide authority is not yet singular.
Numerical tests cover canonical examples but lack tolerance/property coverage,
and semantic tests are heuristic rather than realistic-process validation.

The appropriate next step is a modified cleanup/design wave that freezes the
actual public boundary and resolves finalization/port ownership before any
deletion or broad refactor. S1 does not authorize those changes.

PROCEED WITH MODIFIED S2
