# RETAIN/REMOVE classification audit

## Scope and evidence

This is an investigation-only audit. No implementation, test, taxonomy, accounting-formula, or AgenticAICompass changes were made.

The requested file `logs/llm/task_decomposition_2026-10-14_234344.jsonl` is not present in this checkout. The available newer Production Scheduling trace is `logs/llm/task_decomposition_2026-10-15_001927.jsonl`, correlation `td-7b139dfa582d49f69b2657d4ce6914bf`. It contains the same material symptom: eight operational subtasks, eight `retain` classifications, and no classification rationale. It does not contain a canonical accounting event or the explicit 60/40 accounting input, so the reported 40%/26% result cannot be attributed to that trace alone.

The audit also uses the current source and credential-free tests as architectural evidence. The intended meaning in this document is strict binary classification: `RETAIN` means the whole subtask remains human-performed; `REMOVE` means no human execution remains. A mixed-responsibility activity is not a valid binary row until decomposed further.

## Findings summary

1. **Confirmed: the classifier was not given an executable future-state AI context in the available trace.** Its `transformation_context` was `{}`. No capabilities, tools, autonomy, data access, action permissions, approval requirements, exception policy, or human-in-the-loop constraints were supplied. The classifier therefore had no concrete basis for deciding whether any baseline activity was actually removed.
2. **Confirmed: the prompt asks for a transformation classification, but does not define an authorization/equipment decision procedure.** It says “baseline human work remains human-performed” versus “removed or delegated,” but does not require the model to establish that AI is capable, connected, permitted, and trusted to perform the entire row.
3. **Confirmed: structural validation checks identity, coverage, ordering, and enum validity only.** It does not check that a row is atomic, detect mixed human/AI responsibility, require a rationale, or independently assess semantic consistency of RETAIN/REMOVE.
4. **Confirmed: the semantic evaluator runs before transformation classification and evaluates only the baseline operational decomposition.** Its rubric accepts a reasonable operational unit and explicitly says not to require further decomposition merely because a broad subtask could be split. It has no transformation context or binary automation atomicity criterion.
5. **Confirmed: the available eight rows are plausible baseline work units but are not proven atomic for strict binary automation.** “Develop production schedule,” “assign production orders,” “resolve scheduling conflicts,” and “communicate finalized schedule” can each contain human and AI portions depending on the future-state design. The evidence does not establish that any one should be REMOVE; it establishes that the rows are under-specified for that decision.
6. **Confirmed: accounting is deterministic and can be supplied independently of the provider’s classification proposal.** `W0 = retained + removed`, `W1 = retained + added`; 60 retained, 40 removed, and 14 added produce 40% gross removal and 26% net substitution. Those figures are mathematically consistent with the explicit accounting input, but not with all eight rows being retained.
7. **Confirmed: the current canonical transformation path has a consistency guard when allocations are present.** It applies frozen baseline allocations to every validated classification row and `_validate_effort_handoff` rejects a 60/40 accounting input if all allocated rows are RETAIN. Thus the reported contradiction is not reproducible through that fully linked path. It requires either a no-allocation/unchecked handoff, a downstream projection that bypasses classification, or a different/older orchestration path. The absent requested trace prevents identifying which one.
8. **Missing design decisions, not defects:** what future-state capabilities and permissions are authoritative; whether approval-only human involvement means the baseline subtask is retained or must be decomposed; what makes a row “entirely” removable; and whether accounting inputs are host-authoritative estimates or must always be derived from classified rows.

## 1. Classification path: what was evaluated?

The canonical flow is:

```text
decompose_task()
  -> validated operational baseline + optional frozen allocations
decompose_transformation()
  -> RETAIN/REMOVE provider stage
  -> added-work provider stage
  -> staged handoff validation
  -> deterministic accounting
```

`decompose_transformation()` passes the existing `OperationalDecomposition` and `TransformationDecompositionRequest` to `classify_retain_remove`; it does not regenerate the baseline. The provider serialization in `providers/_shared.py` includes the task, `transformation_context`, and operational decomposition. It does not include `accounting_input`, baseline allocations, or an AI capability/tool/authorization model.

The available trace confirms this precisely. The classifier user payload includes:

- task name and description: Production Scheduling;
- `transformation_context: {}`;
- the eight baseline subtasks and relative weights;
- no accounting input;
- no AI system description, tools, permissions, autonomy, approval constraints, or exception behavior.

The system prompt says:

> `RETAIN = baseline human work remains human-performed; REMOVE = human work is removed or delegated by the transformation.`

It also forbids explanations and rationale, so the output can only be audited for membership and identity, not for the classifier’s reasoning. The response contains exactly eight rows, all `retain`; structural validation succeeds.

The prompt’s noun “transformation” is therefore not grounded in a supplied future-state operating model. In the evidence run, the model can reliably see what a human does at baseline, but not what AI will do, is allowed to do, or must leave to a human. The all-RETAIN result is consequently an under-informed classification, not evidence that all eight activities necessarily remain human work.

The separate semantic evaluation does not repair this gap. It receives task context and the baseline decomposition, returns `accept`, and runs before the transformation stages. It evaluates operational completeness, not future-state human responsibility.

## 2. AI context and decision semantics

The intended strict rule requires a conjunction, even if the eventual API remains compact:

```text
REMOVE only if the future-state design establishes that AI/system execution
replaces the entire baseline subtask and no human execution remains.
Otherwise RETAIN, unless the row is first decomposed.
```

The current request model has only `transformation_context: dict[str, str]`. That is a free-form carrier, not a typed capability or authorization contract. The available trace leaves it empty. There is no current evidence that the classifier distinguishes:

- what an AI could technically do;
- what tools/data it actually has;
- what it is authorized to do;
- whether it may commit changes or only draft recommendations;
- whether human approval is mandatory;
- what happens on exceptions, low confidence, unavailable data, or policy conflicts;
- whether the human still reviews, edits, assigns, communicates, or approves part of the same activity.

This is the central confirmed classification deficiency. It is not appropriate to infer that production scheduling must be automated, or that any particular row must be REMOVE. The correct conclusion is that the input lacks the facts needed to select either label with confidence.

The prompt also collapses “delegated” into REMOVE without stating whether delegation to an AI recommendation followed by mandatory human approval counts as removal. Under the requested semantics, it does not: if the human still performs any execution within the baseline subtask, that row must be decomposed or retained as a whole. That interpretation requires approval as an explicit product decision because current prompt wording does not make it operationally unambiguous.

## 3. Atomicity and mixed responsibility

`OperationalSubtask` is described as “one observable human operational activity,” but neither its contract nor its semantic rubric defines atomicity relative to a future-state transformation. The baseline prompt explicitly asks for a reasonable unit of human work and says not to split a reasonable decision into trivial micro-steps. That is suitable for baseline decomposition, but it is not sufficient for strict binary automation classification.

The eight Production Scheduling rows are:

| Row | Baseline activity | Atomicity concern under strict binary classification |
|---|---|---|
| 1 | Review production orders | Could mean data retrieval, validation, prioritization, and exception interpretation; AI may do some while a human handles exceptions. |
| 2 | Check inventory availability | Could be fully system-readable, or could include investigating discrepancies and authorizing substitutions. |
| 3 | Evaluate machine capacity | Could be calculation plus judgment about maintenance, constraints, and exceptions. |
| 4 | Assess workforce availability | Could be lookup/matching plus labor-policy or managerial judgment. |
| 5 | Develop production schedule | Explicitly combines feasibility analysis, optimization, and judgment; likely mixed unless the future state gives AI full execution authority, but that is not supplied. |
| 6 | Assign production orders | Could be an automatic allocation or a human approval/editing activity; the row does not distinguish them. |
| 7 | Resolve scheduling conflicts | Exception-heavy judgment is especially likely to mix AI proposals and human decisions. |
| 8 | Communicate finalized schedule | Could be automatic distribution, or human confirmation, audience-specific communication, and escalation. |

This table is not a recommendation to mark any row REMOVE. It identifies why the current decomposition cannot support a defensible binary decision without future-state context and, for mixed rows, finer decomposition.

The semantic evaluator does not detect this problem: its rubric treats broad-but-reasonable operational units as acceptable and has no mixed-responsibility finding type. The stage validator likewise verifies that every baseline ID appears exactly once, but does not inspect descriptions for human/AI mixtures. The absence of `rationale` in the classification output makes post hoc detection harder.

## 4. Accounting contradiction

The reported values are internally consistent as accounting inputs:

```text
W0 = 100
retained = 60
gross removed = 40
added human work = 14
W1 = 60 + 14 = 74
gross removed ratio = 40 / 100 = 40%
net substitution = 1 - 74 / 100 = 26%
```

They are not consistent with an all-RETAIN classification if every baseline row has an effort allocation. Classification drives row aggregation conceptually: retained rows contribute to retained human work, removed rows contribute to gross removed work. All rows retained would imply removed baseline work of zero, before any added work is considered.

The current implementation has two separate authorities by design:

- providers propose semantic facts and do not calculate authoritative metrics;
- callers supply explicit absolute or normalized accounting input;
- `domain/accounting.py` validates the accounting identities and calculates the metrics.

That design explains how explicit 60/40 values can produce 40%/26% even when a provider proposes all RETAIN: accounting is deterministic from its explicit input and does not itself infer classification. This is a traceability/consistency risk, not a formula defect.

The current linked handoff is stronger than the symptom suggests. `decompose_transformation()` applies `TaskDecomposition.baseline_effort_allocations` to the classification. `run_staged_pipeline()` then checks that classified retained/removed sums equal the explicit accounting values (absolute mode), or equal the normalized ratios (normalized mode). With eight all-RETAIN rows and a complete 100-unit allocation, the handoff should raise `MissingAccountingInputError` rather than return 40%/26%.

The guard has known boundaries:

- if classification rows carry no effort/ratios and the request supplies explicit accounting, the handoff returns without comparing row labels to accounting;
- the accounting contract itself has retained and removed totals but no required row-level classification provenance;
- a downstream consumer can display explicit accounting metrics without inspecting the returned classification;
- the supplied trace does not log the accounting input or application result, so it cannot distinguish these cases.

Therefore the confirmed root cause is **semantic/accounting inputs are independently representable**. The specific production incident root cause remains unconfirmed because the named trace is absent and the available trace ends after added-work classification.

## 5. Relevant code paths

- `src/task_decomposition/providers/prompts.py`: baseline operational prompt, semantic evaluation prompt, and RETAIN/REMOVE prompt.
- `src/task_decomposition/providers/_shared.py:stage_payload`: serializes transformation context and operational decomposition, but no AI execution model or accounting input.
- `src/task_decomposition/application/task_decomposition.py:_validate_or_repair_operational`: semantic evaluation occurs on the baseline only.
- `src/task_decomposition/application/transformation_decomposition.py:_decompose_transformation`: invokes classification, applies frozen baseline allocation, invokes added work, and calls accounting.
- `src/task_decomposition/application/transformation_decomposition.py:_apply_baseline_allocation`: overwrites provider effort fields with host/frozen baseline allocations when available.
- `src/task_decomposition/validation/stages.py:validate_retain_remove_classification`: checks task identity, exact coverage, unique IDs, and optional sequence order; no atomicity or semantic classification check.
- `src/task_decomposition/application/staged_pipeline.py:_validate_effort_handoff`: checks row-to-accounting totals only when row-level effort/ratios are present; otherwise allows the explicit accounting input through.
- `src/task_decomposition/domain/accounting.py`: sole deterministic W0/W1 and ratio authority; no classification inference.
- `src/task_decomposition/contracts/provider.py` and `contracts/stages.py`: transformation context is untyped string metadata; classification has optional rationale but the prompt requires it to be null.

## Confirmed defects versus decisions requiring approval

### Confirmed defects

- The available classifier invocation has no usable future-state AI capability/authorization context (`transformation_context` is empty).
- The classifier contract/prompt does not require evidence that REMOVE is fully executable and authorized, nor does it define how approval, exceptions, and partial human involvement affect the label.
- Atomicity is validated only for baseline operational usefulness, not for binary future-state responsibility.
- Classification output is deliberately rationale-free, which prevents meaningful audit of why a row was retained or removed.
- Explicit accounting can be accepted without row-level consistency when classification rows have no effort/ratio fields, making contradictory facts representable at the application boundary.

### Missing design decisions

- The authoritative schema for AI capabilities, connected tools/data, write permissions, autonomy, approval gates, exception handling, and operating constraints.
- Whether a human approval, edit, exception review, or communication step means the original row is RETAIN, or mandates decomposition into separate retained/removed rows.
- Whether REMOVE requires demonstrated current-state authorization/equipment, or merely a proposed target-state capability.
- Whether the host’s explicit accounting is an independent estimate that may disagree pending review, or must be derived/rejected whenever classification and allocations are available.
- Whether classifier rationale/evidence is required for auditability and whether it is provider output or a separate review artifact.
- The approved granularity standard for activities such as scheduling, assignment, conflict resolution, and communication.

## Minimal recommended fixes (design only; not implemented)

1. Define and approve the future-state context contract before changing prompts. At minimum it should represent AI capabilities, available tools/data, action permissions, autonomy level, required human approvals, exception/fallback behavior, and the transformation objective. Empty context should be an explicit “insufficient basis” condition, not silently treated as a normal transformation.
2. Make the binary rule explicit: REMOVE is permitted only when the complete baseline activity has no remaining human execution under the approved future-state design. Otherwise retain or require decomposition; do not use partial percentages.
3. Add a transformation-specific atomicity review before classification, or extend semantic evaluation with the future-state context and a blocking mixed-responsibility finding. Preserve the baseline decomposition; if a row is mixed, return a review/repair outcome rather than silently assigning a partial meaning.
4. Preserve audit evidence for each classification decision. This can be a structured rationale/evidence object or a separate review record, subject to the public-contract decision. It should cite the capability, authorization, approval, and exception facts used.
5. Close the accounting seam by deciding whether explicit accounting remains independently authoritative. If row allocations and classifications are available, the safest minimal policy is to fail closed on mismatch, including the currently permissive no-row-effort case, or to mark the result explicitly as an unverified accounting projection. This is a consistency-policy change, not a formula change.
6. Add trace fields for the transformation context, allocation presence/source, classification counts, row-to-accounting reconciliation status, and final accounting input/result. Do not log secrets or provider credentials.

## Recommended implementation order after approval

1. Approve semantics and the future-state context/authorization contract.
2. Add credential-free contract fixtures for fully capable/authorized automation, recommendation-only AI, approval-required AI, exception-only human work, and empty/insufficient context.
3. Add atomicity/mixed-responsibility evaluation and review/repair behavior while retaining strict binary output.
4. Add classification evidence and trace reconciliation fields.
5. Tighten the accounting handoff according to the approved authority policy.
6. Run provider-parity and untrusted-output validation tests, then the repository verification suite. Do not modify accounting equations, added-work taxonomy, or AgenticAICompass as part of this audit’s fix.

## Regression tests to require

- Empty transformation context cannot produce an unqualified automation conclusion; it yields the approved insufficient-context behavior.
- A fully authorized AI that performs an entire subtask can be classified REMOVE, while a recommendation-only or approval-gated AI cannot remove the human responsibility for the full row.
- A row containing AI execution plus human exception handling is detected as mixed and must be decomposed/reviewed; no partial classification is accepted.
- Eight baseline rows with all RETAIN and complete 100-unit allocations cannot return accounting with 60 retained/40 removed.
- The same all-RETAIN result with absent row allocations follows the approved fail-closed or explicitly-unverified policy.
- Valid mixed classifications with complete allocations reconcile exactly to accounting, including the known 60/40 and 14-added-work case and normalized equivalent.
- Classification identity/coverage/order, strict enum values, provider parity, optional SDK isolation, and untrusted-output validation remain unchanged.
- Trace fixtures prove that transformation context and reconciliation status are recorded without credentials or sensitive values.

## Recommended next step

Recover and inspect the missing `2026-10-14_234344` trace and the host-side accounting request/result for the same correlation or request ID. In parallel, obtain approval on the future-state capability/authorization contract and the accounting-authority policy. Only after those decisions should implementation begin; no code changes are justified by this audit alone.

**Bottom line:** the all-RETAIN output is explained by an empty, untyped transformation context plus a classifier that sees baseline work but no executable future-state AI model. The 40%/26% metrics are valid for explicit 60/40 and 14-unit accounting, but are contradictory with the classification and should have been rejected by the fully linked path. The formula is not the defect; the missing future-state semantics and the independently admissible accounting handoff are the root design problems.
