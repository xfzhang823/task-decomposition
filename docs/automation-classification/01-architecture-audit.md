# Architecture Audit: RETAIN/REMOVE and Added Work

## Status and evidence

This is the initial audit phase. No production code was modified. The named trace is available at `logs/llm/task_decomposition_2026-10-17_014615.jsonl`; it has 22 JSONL events and correlation `td-bedf5a99240f40bebbbe6bd7dbcc7322`. It ends with successful added-work validation and does not contain a final accounting event or the host-side accounting input/result. Therefore the trace verifies the provider stages, but cannot by itself prove how the reported 28.61% reduction was finally calculated.

The trace does verify a six-row operational decomposition, semantic evaluation `accept`, a six-row classification with only `subtask-4` (`Create Production Schedule`) marked `remove`, and an empty added-work array (trace lines 2–10, 11–16, and 17–22 respectively). The classification and added-work responses contain no rationale.

## Current architecture and execution flow

The canonical path is:

```text
decompose_task()
  -> operational provider output
  -> structural validation
  -> baseline semantic evaluation
  -> TaskDecomposition + optional frozen allocations
decompose_transformation()
  -> RETAIN/REMOVE provider output
  -> structural/cross-stage validation
  -> apply frozen baseline allocations
  -> added-work provider output
  -> structural/cross-stage validation
  -> staged handoff validation
  -> domain/accounting.py deterministic W0/W1 metrics
```

`decompose_task()` deliberately has no transformation context or accounting ([task_decomposition.py](../../src/task_transmorph/application/task_decomposition.py):44–56). The semantic evaluator runs on the baseline before transformation and returns a baseline-quality decision; it is not a future-state automation judge.

`decompose_transformation()` reuses `request.task_decomposition.operational_decomposition` and does not regenerate it. It calls RETAIN/REMOVE at lines 43–55, applies allocations at 96–131, calls added work at 56–66, and passes both validated provider results plus explicit accounting input to its internal accounting handoff at 67–72 ([transformation_decomposition.py](../../src/task_transmorph/application/transformation_decomposition.py)).

The provider payload is assembled by `stage_payload()` ([providers/_shared.py](../../src/task_transmorph/providers/_shared.py):55–84). For transformation stages it contains the task, `transformation_context`, and operational decomposition; added work additionally receives the prior classification. It does not serialize accounting input, baseline allocations, a typed capability catalog, tool/data access, authorization, autonomy, approval gates, or exception behavior.

The OpenAI adapter uses strict structured JSON schemas and converts numeric boundary values to `Decimal` ([providers/openai.py](../../src/task_transmorph/providers/openai.py):123–150, 166–187). Stage invocation checks response stage and provider provenance before application validation ([application/_provider_stage.py](../../src/task_transmorph/application/_provider_stage.py):26–67). This is untrusted-output validation, not semantic validation of whether a label is true.

## Exact prompts and contracts

### RETAIN/REMOVE

The active prompt is `RETAIN_REMOVE_PROMPT` ([providers/prompts.py](../../src/task_transmorph/providers/prompts.py):46–68). It says to assess current AI-enabled technology, software integrations, workflow automation, optimization, and transferable capabilities; `REMOVE` means technology can execute most of the core activity with limited recurring human execution; `RETAIN` means substantial recurring execution remains human. It explicitly says to assess technological capability rather than deployment, industry adoption, or authorization, and says empty transformation context does not imply RETAIN (lines 52–60).

The output rule requests only `subtask_id` and `classification`, sets rationale and effort fields to null, and forbids explanations (lines 62–67). The public model nevertheless has optional `rationale` ([contracts/stages.py](../../src/task_transmorph/contracts/stages.py):95–126). This is a prompt/schema inconsistency in observability, not a validation failure.

The request contract has only `transformation_context: dict[str, str]` ([contracts/provider.py](../../src/task_transmorph/contracts/provider.py):39–48). In the trace, the classifier input has `transformation_context: {}` (line 11). Thus the prompt selects technological capability as the intended basis, while the actual run supplies no concrete future-state capability or operating context. It does not make a deployment decision, but it also cannot establish what the proposed system can access or do in this transformation.

### Added work

The active prompt is `ADDED_WORK_PROMPT` ([providers/prompts.py](../../src/task_transmorph/providers/prompts.py):70–78). It defines only `AI_INTERACTION` and `AI_VERIFICATION`, excludes baseline work and out-of-execution system lifecycle work, says not to invent rows, and expressly allows `added_work_rows` to be empty. It says amounts are unset unless callers supply explicit accounting inputs.

The contract permits an empty result and optional estimates ([contracts/stages.py](../../src/task_transmorph/contracts/stages.py):139–173). Structural validation checks task identity, unique IDs, known dependencies, and optional sequence indexes, but does not require a row for a removed baseline activity or infer one from a REMOVE label ([validation/stages.py](../../src/task_transmorph/validation/stages.py):120–136).

### Deterministic accounting boundary

The application passes explicit `AbsoluteEffortInput` or `NormalizedAccountingInput` into the staged pipeline; the pipeline explicitly states that providers must not invent effort ([application/staged_pipeline.py](../../src/task_transmorph/application/staged_pipeline.py)). `resolve_support_work()` is the sole support resolver for host/estimate/auto selection and category aggregation. The staged pipeline receives its concrete result before invoking accounting.

`domain/accounting.py` is the deterministic authority. Normalized accounting uses W0 = 1, converts support according to its declared basis, sets `added = interaction + verification`, and computes `W1 = retained + added` ([domain/accounting.py](../../src/task_transmorph/domain/accounting.py):96–145). Absolute accounting validates units and reconciliation, computes the same quantities, and exposes `gross_removed_work_ratio`, `added_human_work_ratio`, `net_remaining_work_ratio`, and `net_substitution_ratio` ([domain/accounting.py](../../src/task_transmorph/domain/accounting.py):148–213). No LLM output calculates these metrics.

## Evidence-based findings

1. **Verified: the trace's classifier is capability-oriented but under-contextualized.** The prompt names current technology and explicitly excludes deployment and authorization as decision criteria. The payload has an empty transformation context and no capability/tool model (trace line 11; `_shared.py`:65–84). This explains why the run cannot distinguish generic technological possibility from the actual target operating model. It does not prove that any particular row should have been REMOVE.

2. **Verified: the six-row result is structurally valid, not semantically adjudicated.** The trace shows successful structural validation at lines 14–16. Validators enforce identity, coverage, cardinality, ordering, and model constraints; they do not evaluate automation feasibility, atomicity, or rationale ([validation/stages.py](../../src/task_transmorph/validation/stages.py):72–117). The single REMOVE is therefore an accepted provider judgment, not a conclusion independently established by the library.

3. **Verified: baseline semantic evaluation does not close this gap.** The trace's evaluation is `accept` (lines 7–10), but that stage evaluates the operational decomposition, not future-state responsibility. It can accept a broad but reasonable baseline row that later combines automated and human-dependent work.

4. **Verified: binary labels do not represent partial responsibility.** `ClassifiedSubtask.classification` is an enum with only RETAIN/REMOVE and no fraction ([contracts/decomposition.py](../../src/task_transmorph/contracts/decomposition.py):95–126; [contracts/stages.py](../../src/task_transmorph/contracts/stages.py):95–106). A row such as “monitor production progress and troubleshoot issues” or “create a production schedule” can contain automated retrieval/calculation plus human exception handling, approval, or editing. The current contract neither detects that mixture nor requires decomposition. This is a granularity/semantic gap, not evidence that the expected result should contain more REMOVE labels.

5. **Verified: an empty added-work result is explicitly allowed even when a row is REMOVE.** The added-work prompt says both “do not disguise added work as RETAIN/REMOVE rows” and `added_work_rows` may be empty (prompts.py:71–76). The added validator has no relationship rule from `REMOVE` to a required added row (validation/stages.py:120–136). This is coherent with the taxonomy: removing baseline work does not necessarily introduce new human interaction or verification. It also means zero added work is an allowed semantic conclusion, not an automatic validator defect.

6. **Verified: added work distinguishes only two new execution categories.** The taxonomy intentionally covers new AI interaction and new AI-output verification. Existing baseline oversight, ordinary human work retained under RETAIN, and external system design/deployment/maintenance are excluded ([added-work-taxonomy/02-design.md](../added-work-taxonomy/02-design.md):3–20). Consequently, the current stage does not separately model “existing baseline oversight” or “genuinely new recurring work” beyond the prompt's exclusions; it places new recurring execution-time intervention into one of the two categories or omits it. This preserves the established taxonomy rather than silently reviving the older governance/support/lifecycle buckets discussed in [04-accounting-alignment-audit.md](../added-work-taxonomy/04-accounting-alignment-audit.md):32–56.

7. **Verified: missing estimates are not defaulted to zero.** Added-work rows carry semantic evidence and optional estimates, not accounting amounts. Estimate mode fails when a non-empty category lacks a computable estimate; empty categories resolve to explicit zero support with compatible basis and units.

8. **Verified: support amounts are basis-dependent, not inherently hours or percentages.** Absolute support requires `unit` and `time_basis`; ratio bases carry no unit/time metadata ([contracts/effort.py](../../src/task_transmorph/contracts/effort.py):30–36, 62–96). The allowed absolute units are effort, hours, days, or FTE and the time basis is per operation/day/week/month/year ([contracts/effort.py](../../src/task_transmorph/contracts/effort.py):11–27). A value such as `0.08` is meaningful only with its basis; normalized contribution is already baseline-relative and is not multiplied by removed work a second time (effort.py:62–67; accounting.py:47–82).

9. **Verified: diagnostic rationale can be captured without changing the result shape, but it is currently suppressed.** The model has an optional `rationale` field, yet the active prompt forces it null. A future implementation could capture provider diagnostics in a trace/review artifact or add an opt-in diagnostic envelope while preserving the public classification fields. This requires an explicit contract/privacy decision; no diagnostic conclusion can be recovered from this trace.

10. **Verified: explicit accounting and classification can be independently representable.** When complete allocations are present, `_apply_baseline_allocation()` supplies row effort/ratios and `_validate_effort_handoff()` compares retained/removed sums to explicit accounting ([transformation_decomposition.py](../../src/task_transmorph/application/transformation_decomposition.py):96–131; [staged_pipeline.py](../../src/task_transmorph/application/staged_pipeline.py):88–186). When rows have no effort/ratio values, the handoff returns without this comparison (staged_pipeline.py:90–97, 124–161). The accounting equations are not the defect; the seam permits an unverified projection in the no-row-allocation case. The prior audit documents this same boundary in detail ([08-retain-remove-classification-audit.md](../added-work-taxonomy/08-retain-remove-classification-audit.md):117–134).

## The reported 28.61% result

The trace's operational weights are `0.15`, `0.204`, `0.105`, `0.305`, `0.10192`, and `0.20005` (trace lines 4–6). They sum to `1.06597`; normalizing the removed `Create Production Schedule` weight gives approximately `0.305 / 1.06597 = 28.61%`. This is a plausible reconstruction of the reported percentage from the observed decomposition, but the trace does not record a final accounting input/result, so it must remain an inference rather than a verified library output. Current operational weights are relative estimates, and deterministic accounting requires an explicit accounting contract; no production code is changed to make this inferred calculation authoritative.

The reported zero AI interaction and verification effort is consistent with an empty added-work response and zero support inputs, but the host-side accounting values are not in the trace. It is therefore not possible to determine whether the result came through the fully linked allocation handoff, a no-allocation path, or an external projection.

## Root-cause hypotheses, ranked

### High confidence — missing future-state context

The classifier received `{}` and no typed capability, data/tool access, authorization, autonomy, approval, or exception model. The prompt asks for capability judgment but provides only baseline activities. This is a confirmed input deficiency, not proof of a wrong label.

### High confidence — binary classification is applied to baseline rows not proven atomic for transformation

The operational prompt optimizes for useful human activities, while the classification schema requires whole-row binary labels. No stage checks whether a row mixes automatable core work with human-dependent exceptions or approvals. This is confirmed by the contracts and validators.

### Medium confidence — empty added work follows the explicit anti-invention rule

The model saw one REMOVE row but was told not to reclassify baseline work as added and that the result may be empty. The trace cannot reveal whether it judged no new interaction/verification necessary or simply omitted it. The prompt/contract path makes the output unsurprising and valid.

### Medium confidence — accounting was sourced independently of the provider rows

The 28.61% value can be reconstructed from relative weights, but no final accounting event is logged. If explicit accounting lacked row allocations, the current handoff permits the projection. This is a confirmed representational possibility; the incident-specific path is unconfirmed.

### Low confidence — conservative model interpretation

The broad verbs “gather,” “assess,” “identify,” “communicate,” and “monitor” may have led to RETAIN where automation could perform most core work. The trace contains no rationale, so this remains a hypothesis. Existing audit 09 records the same limitation for an earlier production-scheduling run and should not be treated as proof for this run.

## Minimal recommendations for later phases

### Prompt changes

- State the approved whole-row rule: `REMOVE` only when the future-state system performs the complete defined core activity and no recurring human execution remains within that row; otherwise RETAIN or require decomposition.
- Clarify how approval, editing, exception handling, escalation, and accountability affect the rule, without assuming that any one of them automatically requires RETAIN.
- Require the model to abstain or return the approved insufficient-context behavior when the future-state facts needed for a defensible decision are absent; do not silently turn an empty context into either label.
- Add concise calibration examples for fully automated, recommendation-only, approval-gated, and mixed activities. Do not mandate more REMOVE classifications.

### Schema and diagnostics

- Decide whether to type `transformation_context` with capability/data/tool/authorization/approval/exception fields or retain a free-form context with explicit required semantics.
- Preserve the binary public classification contract unless a separate approved API change is made. Capture rationale/evidence in an opt-in diagnostic artifact or trace envelope, keeping secrets out of logs.
- Keep added-work categories limited to the established execution taxonomy. If recurring work outside interaction/verification is needed, resolve ownership in `docs/added-work-taxonomy/` before changing contracts.

### Orchestration and validation

- Add a transformation-specific mixed-responsibility check or review/repair outcome; do not introduce partial percentages or regenerate the baseline decomposition.
- Record stage inputs, classification counts, allocation presence/source, reconciliation status, and final accounting input/result in trace metadata.
- Decide whether explicit accounting remains independently authoritative. If allocations and labels are available, fail closed on mismatch; if not, mark the result explicitly unverified rather than implying row-derived accounting.
- Preserve provider parity, untrusted-output validation, optional SDK isolation, and the current ordering of task then transformation stages.

### Accounting

- Do not replace deterministic formulas with LLM estimates. Keep W0/W1, support basis conversion, unit checks, tolerance, and zero-denominator behavior in `domain/accounting.py`.
- Treat an empty added-work list as zero support only under the existing explicit-input/empty-category semantics; do not infer added work from REMOVE alone.
- Add known-answer tests for normalized and absolute support, including zero interaction/verification, mixed categories, incompatible units/bases, and explicit accounting/classification mismatch.

## Existing coverage and missing regression cases

Existing tests cover structural identity/coverage/order and cross-stage references (`tests/test_staged_pipeline.py`, `tests/test_added_work_taxonomy.py`), provider schema serialization and numeric canonicalization (`tests/test_openai_provider.py`), deterministic known-answer accounting and support aggregation (`tests/test_mathematical_validation.py`), and end-to-end stage ordering/accounting (`tests/test_task_transformation_boundaries.py`). The current tests also explicitly allow an empty added-work result and reject non-empty rows with missing amounts.

Verification snapshot: running `pytest -q` in the current worktree produced
235 passed, 32 failed, and 3 skipped. No production files were changed for
this audit. The failures include provider/evaluator fixtures that return stale
or wrong-stage payloads and prompt assertions whose expected wording does not
match the active prompt (for example, a test expects `ongoing system
maintenance`, while the active prompt says infrastructure/model maintenance).
This is a baseline verification issue, not evidence that the six-row trace is
invalid; it should be resolved or explicitly quarantined before implementation
phases rely on a green suite.

Missing cases for the next phase are:

- empty/insufficient future-state context with an approved, testable outcome;
- fully capable and authorized execution versus recommendation-only and approval-gated execution;
- mixed rows containing automated core work plus human exceptions, editing, or approval;
- classification diagnostic capture with unchanged public output and no credentials;
- a removed row with zero newly introduced human work, and a removed row with new interaction/verification work;
- explicit existing baseline oversight versus genuinely new recurring execution-time work;
- absolute and normalized amount basis/unit/time validation, including omitted categories and non-empty missing amounts;
- complete allocations plus contradictory explicit accounting must fail, while absent allocations must be marked according to the approved policy;
- trace fixtures that include transformation context and final reconciliation/accounting provenance; and
- the observed six-row production-scheduling fixture, asserting only the structural facts actually evidenced by the trace rather than prescribing expected classifications.

## Next-phase acceptance criteria

Phase 02 may be accepted only when the approved context and binary semantics are documented, implemented without changing accounting formulas, and covered by credential-free provider-parity tests. It must demonstrate that a model can return either RETAIN or REMOVE based on supplied facts, that mixed responsibility is not silently represented as a whole-row conclusion, and that diagnostics remain optional and contract-safe. Phase 03 must separately verify added-work taxonomy decisions and amount semantics. Phase 04 must prove the full handoff from classifications and allocations to deterministic accounting, including explicit handling of the no-allocation seam.

