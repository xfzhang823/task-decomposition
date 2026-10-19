# RETAIN/REMOVE Implementation Verification

## Status and conclusion

This is an audit-only verification of the existing implementation. No production code, prompt, schema, validator, adapter, accounting logic, or test was changed.

**Recommendation: Minor Fixes completed; no further RETAIN/REMOVE implementation change.** The core policy is implemented and tested, and Phase 02 now captures concise rationale through the existing optional field and trace path. Transformation-specific mixed-activity handling remains deferred; it does not justify changing the binary contract, raising the REMOVE rate, or adding a new stage now.

## Requirement-by-requirement matrix

1. **Measure technological automation potential**
   - Status: Implemented.
   - Evidence: `RETAIN_REMOVE_PROMPT` directs assessment using current AI, integrations, workflow automation, optimization, conventional automation, and transferable capabilities (`src/task_decomposition/providers/prompts.py:46-60`).

2. **Do not make deployment or authorization the metric**
   - Status: Implemented.
   - Evidence: The prompt explicitly says to assess technology rather than deployment, industry adoption, or authorization (`prompts.py:56`). Tests assert this wording and the empty-context rule (`tests/test_openai_provider.py:347-367`).

3. **Preserve the “most of the core operational activity” threshold**
   - Status: Implemented.
   - Evidence: `REMOVE` means most of the core activity with limited recurring human execution; `RETAIN` means substantial recurring execution remains (`prompts.py:51-60`). Tests cover automated-with-oversight and human-intensive examples (`tests/test_openai_provider.py:381-429`).

4. **Keep binary public output**
   - Status: Implemented.
   - Evidence: `TransformationClassification` has only `RETAIN` and `REMOVE` (`src/task_decomposition/contracts/decomposition.py:12-15`); `ClassifiedSubtask` has no partial percentage or mixed enum (`src/task_decomposition/contracts/stages.py:95-136`).

5. **Preserve the existing baseline decomposition**
   - Status: Implemented.
   - Evidence: Transformation orchestration passes the existing operational decomposition to classification, applies existing allocations, and does not regenerate it (`src/task_decomposition/application/transformation_decomposition.py:43-72,96-131`).

6. **Provider parity and structured output**
   - Status: Implemented.
   - Evidence: OpenAI, Gemini, and DeepSeek adapters invoke the same classification prompt/schema path (`src/task_decomposition/providers/openai.py:360-372`, `src/task_decomposition/providers/gemini.py:191-199`, `src/task_decomposition/providers/deepseek.py:206-214`). Focused provider and parity tests pass.

7. **Structural classification validation**
   - Status: Implemented.
   - Evidence: Validation enforces task identity, unique IDs, exact coverage, count, optional order, and model constraints (`src/task_decomposition/validation/stages.py:72-117`).

8. **Semantic adjudication of labels**
   - Status: Not Needed by current ownership.
   - Evidence: Validators intentionally accept provider semantic facts; they do not independently decide whether a label is technologically correct. The prompt/provider is the semantic proposer, while the application validates structure.

9. **Mixed-activity identification**
   - Status: Partial.
   - Evidence: Baseline semantic evaluation supports granularity findings and repair before transformation (`src/task_decomposition/evaluation/contracts.py:35-88`, `src/task_decomposition/application/task_decomposition.py:92-166`), but it has no transformation context and no classification-specific mixed finding. The classification validator does not detect mixed responsibility.

10. **Diagnostic rationale/evidence**
    - Status: Implemented for future executions.
    - Evidence: `ClassifiedSubtask.rationale` is optional (`src/task_decomposition/contracts/stages.py:100-106`), `RETAIN_REMOVE_PROMPT` now requests one concise evidence-based sentence, and tracing captures the parsed response (`src/task_decomposition/tracing.py:165-245`). The historical Production Scheduling trace predates this change and contains no rationale.

11. **Transformation context**
    - Status: Partial.
    - Evidence: The request carries `transformation_context`, but it is an untyped `dict[str, str]` and may be empty (`src/task_decomposition/contracts/provider.py:39-48`). The prompt correctly avoids treating empty context as RETAIN, but the run is necessarily under-contextualized.

12. **Accounting consistency**
    - Status: Implemented for linked allocations; Partial at no-allocation seam.
    - Evidence: `_validate_effort_handoff` rejects mismatch when complete row effort/ratios are present (`src/task_decomposition/application/staged_pipeline.py:88-186`). If row allocations are absent, it permits explicit accounting without row-level reconciliation. This is the known audit boundary, not a RETAIN/REMOVE formula defect.

13. **Added-work interaction**
    - Status: Not Needed for this verification.
    - Evidence: Added-work semantics and taxonomy remain unchanged and are outside this verification’s change scope.

## Current execution path

The existing path is:

```text
TaskDecomposition
  -> existing operational decomposition and allocations
  -> provider RETAIN/REMOVE classification
  -> structural classification validation
  -> allocation application
  -> provider added-work classification
  -> cross-stage validation
  -> explicit accounting handoff
  -> deterministic domain accounting
```

`stage_payload()` supplies the transformation task, transformation context, and operational decomposition to the RETAIN/REMOVE stage (`src/task_decomposition/providers/_shared.py:55-84`). Added-work receives the prior classification as well. Provider adapters use structured schemas and stage provenance; `_provider_stage.py:26-67` checks stage/provenance before application validation.

The implementation therefore already satisfies the core Phase 02 policy. It does not infer classification from accounting, and accounting does not infer classification from the provider response.

## Production Scheduling trace verification

The available trace is `logs/llm/task_decomposition_2026-10-17_014615.jsonl`, correlation `td-bedf5a99240f40bebbbe6bd7dbcc7322`. It records:

- six operational subtasks and accepted baseline semantic evaluation;
- six structurally valid classifications;
- five `RETAIN` rows and one `REMOVE` row, `Create Production Schedule`;
- an empty added-work list; and
- successful structural validation through the added-work stage.

The historical trace contains no classification rationale and no final accounting input or accounting result. The reported 28.61% can be reconstructed as `0.305 / 1.06597`, but remains an inference from operational weights, not a verified final library accounting event. The output is therefore a valid model judgment under the current prompt, not proof of a defect or proof that more rows should have been removed. The empty added-work result is also permitted by the active added-work contract and is not evidence of a RETAIN/REMOVE bug.

## Mixed activities: what is already handled?

The operational prompt asks for distinct human activities and the semantic evaluator’s rubric says granularity should support independent automation assessment. The evaluator can return repairable or blocking granularity findings, and the existing task path can perform bounded operational repair (`src/task_decomposition/application/task_decomposition.py:108-166`). This is useful pre-classification protection against obviously vague or overlapping rows.

It does not establish that every row is atomic for a particular transformation. For example, “monitor production progress and troubleshoot issues” may contain automated status collection and recurring human exception diagnosis. The current transformation path neither detects that mixture nor silently splits the row. That is an intentional consequence of the fixed-baseline boundary, not a hidden mixed classification.

The smallest justified conclusion is therefore: baseline decomposition and semantic evaluation provide partial protection; transformation-specific mixed responsibility remains an unresolved design decision. No mixed-activity implementation should be started until its diagnostic/review policy is explicitly approved.

## Diagnostics and trace infrastructure

Diagnostic capture is partly already available:

- the public result can carry optional `rationale` without changing its binary fields;
- the trace records stage prompts, serialized input, structured schemas, raw provider output, parsed output, validation events, and redacted sensitive values (`src/task_decomposition/tracing.py:68-89,165-245`);
- the named historical trace predates rationale capture and therefore contains no classification rationale.

Thus a new generic tracing system is not justified. Any future mixed-activity diagnostic needs only an approved representation and policy for whether it is advisory, blocking, or routed to review. That is a design decision, not a verified implementation defect.

## Existing test coverage

The focused verification suite passed: **121 tests passed** across:

- added-work taxonomy and prompt contract tests;
- staged pipeline identity, ordering, cross-stage, and accounting handoff tests;
- OpenAI structured prompt/schema and classification calibration tests;
- provider parity tests for OpenAI, Gemini, and DeepSeek;
- task/transformation boundary tests;
- semantic evaluator contract/orchestration tests; and
- trace capture and redaction tests.

The credential-free repository baseline remains **264 passed, 6 skipped**. The six skipped tests are explicitly opt-in integration tests. No test evidence requires more `REMOVE` classifications.

## Confirmed gaps ranked by severity

### Medium — transformation-specific mixed-activity policy is unresolved

The current implementation cannot distinguish a materially mixed baseline row from a whole-row activity during classification validation. This can make a binary result difficult to interpret, but the repository has intentionally not introduced partial classifications or baseline mutation. Resolve the policy before implementation; do not treat it as evidence that existing labels are wrong.

### Low — historical traces lack classification rationale

The existing contract and trace infrastructure now capture concise rationale for future classifications. The Production Scheduling trace remains unauditable at the rationale level because it predates the implementation. This is a historical observability limitation, not a contract or accounting inconsistency.

### Low — transformation context is untyped and may be empty

The current prompt semantics are explicit, but an empty context cannot describe specific capabilities or constraints. This limits evidence quality without making the classification invalid under the current technological-potential policy.

### Low — no-allocation accounting reconciliation seam

The staged handoff can accept explicit accounting without comparing it to row labels when row allocations are absent. This is already documented in audits 08 and 09 and is outside RETAIN/REMOVE semantics. It should not be changed as part of this verification.

## Duplicate or obsolete recommendations

- The Phase 01 suggestion that `REMOVE` require complete execution and no recurring human execution is stricter than the active prompt and Phase 02 policy. It is superseded, not an implementation requirement.
- Recommendations to increase the number of `REMOVE` labels are not defects or acceptance criteria. Audit 09’s calibration discussion is already reflected in the current prompt and tests.
- A new evaluator stage, partial percentages, a `MIXED` enum, and transformation baseline splitting remain out of scope and are not justified by the current evidence.
- Audit 08’s accounting contradiction findings concern independently supplied accounting and the no-allocation seam; they do not establish a classification contract or formula inconsistency in the linked path.

## Minimal recommendation

No further RETAIN/REMOVE implementation change is justified by this verification. The existing binary schema, provider adapters, validator, orchestration, and accounting remain unchanged; concise rationale capture now reuses the existing optional field and trace path. Transformation-specific mixed-activity handling remains deferred pending concrete evidence and explicit approval, without adding stages, percentages, or baseline mutation.

