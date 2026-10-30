# Phase 02: Classification Design Decisions

## Status

Implementation complete for the approved rationale-capture scope. Items below
are proposed unless explicitly identified as established by an existing
contract. No classification category, threshold, schema shape, pipeline stage,
accounting behavior, or baseline decomposition was changed.

### Implemented Phase 02 decision

The existing optional `ClassifiedSubtask.rationale` field is the diagnostic
path. `RETAIN_REMOVE_PROMPT` now requests one concise, evidence-based sentence
for each classification and continues to set unrelated optional fields to
null. The existing provider adapters parse the same `RetainRemoveClassification`
contract, so the rationale is available in the public result when supplied by
the provider and is also retained by the existing `llm.parsed` trace event.
No new schema, validator, pipeline stage, trace event, or machine-readable
mixed-activity envelope was introduced. Existing binary labels and their
threshold are unchanged.

The historical Production Scheduling trace predates this change and contains
no rationale. Future executions can capture it without changing the result
shape or trace infrastructure.

## Governing constraints

Phase 02 must preserve the repository boundary: operational decomposition owns
baseline activities and allocations; transformation decomposition consumes the
existing `TaskDecomposition`; providers propose semantic facts; structural
validation protects stage identity and references; and
`domain/accounting.py` remains authoritative for deterministic W0/W1
calculation. In particular, transformation decomposition must not regenerate
or silently split the baseline.

## Classification semantics

### Established contract

The active `RETAIN_REMOVE_PROMPT` (`src/task_transmorph/providers/prompts.py:46-68`)
defines the current intended semantics:

- measure technological substitutability using current AI, integrations,
  workflow automation, optimization, conventional automation, and transferable
  capabilities;
- `REMOVE` means technology can execute **most of the core operational
  activity** with limited recurring human execution;
- `RETAIN` means substantial recurring human execution remains technically
  necessary;
- deployment, industry adoption, and organizational authorization are not
  classification criteria; and
- judgment, coordination, oversight, approval, accountability, escalation, and
  occasional exceptions do not automatically imply `RETAIN`.

The public classification is an identity-preserving binary enum with no
partial-automation field or third label
(`src/task_transmorph/contracts/decomposition.py:12-15`,
`src/task_transmorph/contracts/stages.py:95-136`).

### Proposed Phase 02 decision

Adopt that policy without replacing “most” with “complete.” Limited recurring
oversight, approval, accountability, or exceptional intervention does not
automatically defeat `REMOVE`. A material recurring human-dependent component
of the defined core activity does prevent an unqualified `REMOVE` at the
current whole-row granularity.

The classifier should answer:

> Can current technology perform most of the row’s defined core operational
> activity, with only limited recurring human execution remaining?

It should not answer whether the organization deployed, authorized, or adopted
the technology. Those facts may be useful diagnostics, but they are not the
metric under this proposal.

### Conflict with earlier documentation

Phase 01 suggested a possible rule requiring the “complete defined core
activity” and “no recurring human execution.” That is stricter than the active
prompt and this task’s proposed policy; it must remain an unapproved option,
not become Phase 02 policy. Related audit 09 uses “fully or substantially” and
treats limited oversight as compatible with `REMOVE`, which is consistent
with this proposal. Audit 08’s accounting consistency findings do not change
the classification threshold.

The transformation context is still an untyped `dict[str, str]` and may be
empty (`src/task_transmorph/contracts/provider.py:39-48`). That is an
evidence limitation, not permission to infer `RETAIN` or impose deployment
requirements.

## Mixed-activity handling

### Problem

A row may combine materially distinct automatable and human-dependent work,
such as status collection plus exception diagnosis, or schedule optimization
plus human exception resolution. Current validation checks identity, coverage,
ordering, and references, not whether a row is a sound unit for a binary
substitutability judgment (`src/task_transmorph/validation/stages.py:72-117`).

### Options

1. Add a partial percentage or `MIXED` enum. This violates the public contract
   and creates downstream accounting/consumer changes.
2. Split the row during transformation. This violates the fixed-baseline
   boundary.
3. Add a new transformation evaluator stage. This expands the pipeline beyond
   the epic scope.
4. Keep binary output and attach explicit mixed-activity diagnostic evidence to
   the existing classification call. A material human-dependent core component
   prevents an unqualified `REMOVE`; limited oversight or occasional
   exceptions alone do not. The baseline is not silently rewritten.

### Recommendation

Mixed-activity handling is explicitly deferred. If concrete evidence later
requires it, preserve binary fields, use the existing classification call, and
surface evidence through an approved diagnostic/review path. Do not introduce
partial percentages, a third category, baseline mutation, or free-text parsing
as an authoritative validator without an explicit contract.

The operational semantic evaluator has repair-oriented and granularity
findings (`src/task_transmorph/evaluation/contracts.py:11-88`), but it runs
before transformation and does not receive future-state classification
evidence. It can inform baseline fixtures; it is not sufficient by itself to
adjudicate transformation-specific mixed responsibility, and must not be used
to silently regenerate a fixed baseline.

## Test failure triage

`pytest -q` was rerun: **235 passed, 32 failed, 3 skipped**.

### Stale tests or fixtures — primary cause

**28 of the 32 failures** return semantic evaluation rubric version `1.0` from test doubles,
while production requires the canonical `1.1`
(`src/task_transmorph/evaluation/rubric.py:3`, enforced by
`src/task_transmorph/application/task_decomposition.py:186-219` and
`src/task_transmorph/providers/_semantic.py:47-58`). Affected groups are
provider application/parity, effort estimation, operational repair, task /
transformation boundaries, tracing, and full-application OpenAI/Gemini/DeepSeek
adapter tests.

Smallest fix: update fixtures to import and use
`SEMANTIC_EVALUATION_RUBRIC_VERSION`; do not weaken the production version
check. DeepSeek’s fake transport also dispatches semantic evaluation by looking
for a literal prompt phrase that the active prompt no longer contains. Fix the
fake to dispatch by request/schema or an explicit test hook, not prompt text.

### Prompt expectation mismatches

**Two failures** assert older wording:

- `test_added_work_taxonomy.py::test_prompt_defines_interaction_verification_and_exclusions`
  expects “ongoing system maintenance”; the active prompt says
  “infrastructure or model maintenance” (`prompts.py:73`).
- `test_openai_provider.py::test_provider_prompts_request_compact_optional_fields`
  expects “Keep each subtask name and description concise”; the active prompt
  says “Keep names and descriptions concise” (`prompts.py:23`).

Smallest fix: update assertions to the approved current wording, or change the
prompt only if the longer wording is explicitly approved. Do not delete or
weaken the semantic assertions.

### Actual production regressions

None was established by these 32 failures. The failures occur in semantic
fixture setup or literal prompt assertions, before the RETAIN/REMOVE stage, or
in optional live-provider execution. This does not eliminate the design risks
identified in Phase 01; it means they are not proven by this test failure set.

### Environment/dependency issues

The original baseline reported **two** live-provider failures (DeepSeek and
Gemini). A subsequent rerun exposed the separately existing OpenAI smoke test
as well; all three are live smoke tests. They are now explicitly opt-in and
skip without the opt-in flag. When enabled, failures must be reported
separately as provider/environment contract, network/rate-limit, or adapter
issues. They should not contaminate the credential-free baseline.

Trustworthy baseline definition:

- credential-free unit/contract suite green after fixture and assertion repair;
- live-provider smoke status separately reported with provider/model and
  response-contract details.

### Baseline repair completed

The following test-only corrections were applied:

- replaced hardcoded semantic rubric `1.0` fixture values with
  `SEMANTIC_EVALUATION_RUBRIC_VERSION`;
- changed DeepSeek fake transports to identify semantic requests from the
  serialized request payload’s `rubric_version`, not prompt wording;
- updated prompt assertions to check the active maintenance and concise-output
  requirements;
- added an explicit `RUN_LIVE_PROVIDER_TESTS=1` opt-in to the three provider
  smoke tests while retaining their `integration` markers.

Final verification:

- `pytest -q`: **264 passed, 6 skipped**;
- `pytest -q -m 'not integration'`: **264 passed, 6 deselected**;
- `pytest -q -m integration`: **6 skipped, 264 deselected**;
- targeted Ruff checks for all changed tests: passed;
- `ruff format --check src tests`: passed.

No production behavior, prompts, classification semantics, accounting
formulas, public contracts, or provider adapters were changed. The live tests
remain available only through explicit opt-in and were not executed as part of
the credential-free baseline.

## Explicit non-goals

This phase does not change production behavior, prompts, schemas, validators,
adapters, exports, accounting formulas, support bases, units, tolerances, or
zero behavior. It does not add stages, scenarios, simulation, alternatives,
workforce planning, partial percentages, a third public classification, added
work inferred from `REMOVE`, or baseline regeneration/silent repair.

## Decisions requiring explicit approval

1. Accept option 4 as the mixed-activity policy: binary label plus explicit
   diagnostic evidence.
2. Choose the diagnostic location: existing optional `rationale`, an opt-in
   trace/review envelope, or an internal structure; review privacy and
   consumers.
3. Decide whether a mixed finding is advisory, blocks the result, or requests
   human review/repair; the current enum has no review value.
4. Decide whether empty transformation context remains valid with an evidence
   diagnostic, or whether a typed context/request change is required.
5. The fixture maintenance and separate live-smoke verification gate are now
   established as test policy; approval is still required for the
   classification/mixed-activity design choices above.

## Phase 02 implementation acceptance criteria

- prompts and tests consistently use the “most of the core operational
  activity” policy, not “complete execution”;
- canonical rubric fixtures and schema/request-based provider fakes produce a
  green credential-free baseline;
- binary fields and public exports remain unchanged unless separately approved;
- fixtures cover fully automatable, oversight-only, approval-gated,
  exception-heavy, and materially mixed activities without prescribing a
  higher REMOVE rate;
- mixed-activity validation is explicitly deferred pending concrete evidence;
  no percentages, silent baseline rewriting, or new stage is introduced;
- concise classification rationale is captured through the existing optional
  public field and existing parsed-response trace event;
- empty-context behavior is explicitly tested under the approved decision;
- diagnostics contain no credentials or sensitive provider data;
- existing added-work taxonomy and deterministic accounting tests remain green;
- the required credential-free verification commands pass, with live smoke
  results reported separately.

## Phase 02 implementation verification

- Focused rationale and provider-parity tests: **37 passed**.
- Full credential-free `pytest -q`: **265 passed, 6 skipped**.
- The rationale test confirms that labels remain unchanged, rationale is
  present in the public `ClassifiedSubtask` result, and the same parsed
  response is present in existing trace metadata.
- Provider parity covers OpenAI, Gemini, and DeepSeek using the unchanged
  binary classification contract and unchanged deterministic accounting.
- Targeted `ruff check` and `ruff format --check` for changed source/tests
  pass. Repository-wide `ruff check src tests` remains nonzero because of 77
  pre-existing findings outside this change; none are in the changed source
  or newly added test logic.
- Mixed-activity detection remains deferred and was not added.
- Compatibility implication: `rationale` was already an optional public field;
  providers may now populate it, so consumers that ignore optional fields are
  unaffected. No required field, enum value, public export, or accounting input
  changed.
