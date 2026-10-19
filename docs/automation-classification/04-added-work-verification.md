# Added-Work Classification and Accounting Handoff Verification

## Status and conclusion

This is an audit-only verification. No production code, prompt, schema, validator, test, or accounting formula was changed.

**Conclusion: No Changes.** The existing added-work taxonomy, provider contract, structural validation, canonical accounting conversion, and deterministic W0/W1 calculations are internally consistent. The Production Scheduling empty result is structurally valid and does not prove that new human work was required. The remaining limitations are evidence and traceability boundaries, not confirmed production defects.

## Requirement-by-requirement matrix

1. **AI_INTERACTION represents genuinely new execution-time human interaction with AI**
   - Status: Implemented.
   - Evidence: The prompt defines instructing, guiding, clarifying, intervening, redirecting, retrying, and similar execution-time interaction as `AI_INTERACTION` (`src/task_decomposition/providers/prompts.py:71-75`). The taxonomy establishes the same boundary (`docs/added-work-taxonomy/02-design.md:3-20`).

2. **AI_VERIFICATION represents genuinely new verification of AI-generated work**
   - Status: Implemented.
   - Evidence: The prompt defines inspecting, validating, correcting, and approving AI-generated outputs as `AI_VERIFICATION` (`src/task_decomposition/providers/prompts.py:73-74`). The public enum contains only the two canonical execution categories (`src/task_decomposition/contracts/stages.py:139-143`).

3. **Existing baseline work is not relabeled as added work**
   - Status: Implemented.
   - Evidence: The prompt explicitly excludes existing baseline work even when AI participates, and tells the provider not to disguise added work as RETAIN/REMOVE rows (`src/task_decomposition/providers/prompts.py:72,75`). The added-work contract is separate from `ClassifiedSubtask` (`src/task_decomposition/contracts/stages.py:146-173`).

4. **System lifecycle work is excluded**
   - Status: Implemented.
   - Evidence: Design, implementation, deployment, technical documentation, guardrails, infrastructure/model maintenance, and passive waiting are excluded from execution-level added work (`src/task_decomposition/providers/prompts.py:74`; `docs/added-work-taxonomy/02-design.md:11-16`).

5. **Added work does not reinterpret RETAIN/REMOVE**
   - Status: Implemented.
   - Evidence: Added-work validation receives the prior classification only for cross-stage identity context; it does not infer rows from labels (`src/task_decomposition/validation/stages.py:120-153`). There is no REMOVE-to-added-work requirement.

6. **Empty added work is valid**
   - Status: Implemented.
   - Evidence: The prompt expressly permits `added_work_rows` to be empty (`src/task_decomposition/providers/prompts.py:75`), the contract defaults the tuple to empty (`src/task_decomposition/contracts/stages.py:166-173`), and tests verify empty output and complete root fields (`tests/test_added_work_taxonomy.py:76-91`).

7. **Nonempty rows have structural validation**
   - Status: Implemented.
   - Evidence: Validation enforces task identity, unique work IDs, known subtask dependencies, and all-or-none sequence indexes (`src/task_decomposition/validation/stages.py:120-136`). It does not require a row for every REMOVE label, which is correct for the taxonomy.

8. **Nonempty rows with missing amounts are handled explicitly**
   - Status: Partial by design.
   - Evidence: `AddedWorkItem.amount` is optional at the provider boundary (`src/task_decomposition/contracts/stages.py:151-158`). When rows are converted into derived support inputs, a missing amount raises `MissingAccountingInputError` rather than defaulting to zero (`src/task_decomposition/application/staged_pipeline.py:189-198`); this is covered by `tests/test_staged_pipeline.py:340-355`. In the canonical transformation path, explicit host support inputs are passed as an override and therefore take precedence over provider row amounts (`src/task_decomposition/application/transformation_decomposition.py:67-72`).

9. **Explicit zero is distinct from an omitted amount**
   - Status: Implemented for accounting conversion; Partial for provider semantics.
   - Evidence: An empty category is converted to an explicit zero with the accounting input's compatible unit/time basis (`src/task_decomposition/application/staged_pipeline.py:222-234`). A row with `amount=None` is not itself a quantified zero, but the provider contract intentionally leaves amounts unset unless the caller supplies explicit accounting inputs (`src/task_decomposition/providers/prompts.py:77`).

10. **Support units, time bases, and ratio bases are preserved**
    - Status: Implemented.
    - Evidence: Absolute support requires unit and time basis; normalized and ratio bases reject those metadata (`src/task_decomposition/contracts/effort.py:62-96`). Category aggregation rejects incompatible bases or absolute units/time bases (`src/task_decomposition/application/staged_pipeline.py:222-250`).

11. **Explicit accounting inputs have defined precedence**
    - Status: Implemented.
    - Evidence: `run_staged_pipeline()` uses `support_work_override` when supplied and otherwise derives support from added rows (`src/task_decomposition/application/staged_pipeline.py:46-63`). Transformation orchestration always passes `request.accounting_input.support_work` as that override (`src/task_decomposition/application/transformation_decomposition.py:67-72`). Existing tests verify provider amounts do not replace explicit accounting support (`tests/test_provider_application.py:265-277`).

12. **Added work is aggregated without double counting**
    - Status: Implemented.
    - Evidence: Rows are grouped independently by `AI_INTERACTION` and `AI_VERIFICATION`, then summed once per category (`src/task_decomposition/application/staged_pipeline.py:189-219,222-250`). Accounting sums the two converted support values into `added_human_work` and computes W1 as retained work plus added work (`src/task_decomposition/domain/accounting.py:109-144,180-212`). Tests cover category aggregation and total-effort parity (`tests/test_mathematical_validation.py:347-380`).

13. **Accounting formulas are deterministic and provider-independent**
    - Status: Implemented.
    - Evidence: The staged pipeline delegates to `account_absolute()` or `account_normalized()` and explicitly prohibits providers from inventing effort (`src/task_decomposition/application/staged_pipeline.py:40-67`). Known-answer, absolute/normalized equivalence, zero-support, and monotonicity tests cover the accounting domain (`tests/test_mathematical_validation.py:123-216`).

14. **Provider parity and cross-stage handoff are preserved**
    - Status: Implemented.
    - Evidence: OpenAI, Gemini, and DeepSeek parity tests produce identical canonical accounting (`tests/test_provider_parity.py:99-138`). The application validates operational output, RETAIN/REMOVE output, and added-work output before accounting (`src/task_decomposition/validation/stages.py:139-154`; `src/task_decomposition/application/transformation_decomposition.py:43-72`).

15. **Final accounting is traceable to provider and host inputs**
    - Status: Partial.
    - Evidence: The returned result contains validated added-work rows, provenance, and deterministic accounting (`src/task_decomposition/application/transformation_decomposition.py:74-93`). However, the provider trace records the added-work request, response, and structural validation but not the host-side accounting input or final accounting result. The named trace therefore proves an empty provider array, not the exact accounting path that produced the reported zero support.

## Architecture and accounting handoff

The current flow is:

```text
TaskDecomposition
  -> RETAIN/REMOVE classification
  -> apply frozen baseline allocations
  -> added-work provider stage receives prior classification
  -> added-work structural and cross-stage validation
  -> explicit support-work override, or row-derived support conversion
  -> deterministic absolute or normalized accounting
  -> TransformationDecompositionResult
```

`stage_payload()` sends the task, transformation context, operational decomposition, and—only for added work—the prior RETAIN/REMOVE classification (`src/task_decomposition/providers/_shared.py:55-84`). It does not send accounting input. This keeps providers from supplying authoritative W0/W1 metrics, but it also means the added-work provider cannot quantify amounts from the host accounting contract. The prompt therefore correctly says to leave amounts unset unless explicit inputs are supplied (`src/task_decomposition/providers/prompts.py:77`).

The canonical transformation path passes explicit support inputs into `run_staged_pipeline()` as an override (`src/task_decomposition/application/transformation_decomposition.py:67-72`). Consequently, provider rows describe semantic added work, while host accounting inputs determine the support quantities in the final result. If the override is absent, row amounts are aggregated by category; a nonempty row without an amount fails, and an empty category becomes an explicit zero with a compatible basis.

The accounting domain preserves the established bases. Normalized contribution and baseline-relative support values remain baseline-relative; gross-removed-work ratios are multiplied by gross removed work only once; absolute support is divided by W0 for normalized outputs and requires matching absolute units/time bases (`src/task_decomposition/domain/accounting.py:47-82`). W1 is retained work plus AI interaction plus AI verification, with no provider arithmetic.

## Distinctions the current stage can and cannot establish

The prompt provides the correct taxonomy distinctions for a provider judgment:

- new execution-time instruction, intervention, retry, or redirection is interaction;
- new inspection, validation, correction, or approval of AI output is verification;
- existing coordination, oversight, approval, troubleshooting, and quality work remain baseline work unless the transformed workflow genuinely introduces a new activity;
- occasional exceptions are included only when they create genuinely new execution-time human intervention or verification;
- system design, deployment, maintenance, and passive waiting are excluded.

The contract cannot independently determine whether a described activity is genuinely new. It accepts provider semantic facts and validates structure. An empty list is therefore ambiguous between “no new human work is required” and “the provider did not identify any,” but that ambiguity is not an accounting defect and does not justify forcing nonzero overhead. A nonempty row with no amount is a different state: it identifies work but is unquantified. Direct derived accounting rejects it; canonical explicit accounting can proceed using the host-supplied support values.

## Production Scheduling trace

The available trace is `logs/llm/task_decomposition_2026-10-17_014615.jsonl`, correlation `td-bedf5a99240f40bebbbe6bd7dbcc7322`. The added-work request at trace line 17 contains an empty transformation context, the six-row operational decomposition, and the complete prior classification with one `REMOVE` row. The provider returned `added_work_rows: []` at line 18, and structural validation accepted the complete root object at lines 20–21.

The trace supplies no evidence that new AI interaction or verification was required, but it also cannot prove that none was required. It shows a structurally valid provider conclusion under a prompt that explicitly permits an empty result and prohibits inventing work. The existence of one REMOVE label is not sufficient evidence of added human work.

The trace does not contain the host-side `AbsoluteEffortInput` or `NormalizedAccountingInput`, a support override, a final accounting event, or a final accounting result. Therefore the reported zero interaction and verification effort is consistent with the provider response and with explicit zero support inputs, but is not verified by this trace as a complete accounting handoff. No additional human activity should be inferred from the trace alone.

Additional diagnostic evidence would materially improve confidence only if it records the host accounting mode/input, whether support override was used, and the final deterministic accounting output. The provider response itself does not need to be changed to make the empty result valid.

## Existing regression coverage

The relevant credential-free focused suite passed: **81 passed** across added-work taxonomy, staged pipeline, provider application, mathematical validation, task/transformation boundaries, provider parity, and trace tests.

Existing coverage verifies:

- both canonical categories and rejection of obsolete categories (`tests/test_added_work_taxonomy.py:51-73`);
- empty added-work output and complete root fields (`tests/test_added_work_taxonomy.py:76-91`);
- separation from baseline RETAIN/REMOVE rows (`tests/test_added_work_taxonomy.py:118-135`);
- prompt exclusions and category meanings (`tests/test_added_work_taxonomy.py:138-150`);
- missing row amounts, incompatible bases, and partial classification effort (`tests/test_staged_pipeline.py:340-405`);
- explicit accounting precedence over provider amounts (`tests/test_provider_application.py:265-277`);
- absolute and normalized accounting, zero added work, scale equivalence, and monotonicity (`tests/test_mathematical_validation.py:123-216`);
- category aggregation without double counting (`tests/test_mathematical_validation.py:347-380`);
- provider parity and cross-stage sequencing (`tests/test_provider_parity.py:99-138`; `tests/test_task_transformation_boundaries.py:232-280`);
- trace capture of the provider-stage sequence (`tests/test_tracing.py:302-325`).

Genuinely missing coverage is host-side trace reconciliation: no test currently asserts that the accounting input, support override/derived path, and final accounting result are emitted together in the execution trace. This is an observability gap, not evidence that the current accounting calculation is wrong. There is also no test that can distinguish a semantically omitted added-work row from a justified empty result without an external expected-work oracle; adding such a test would require a product policy or benchmark, not a structural validator.

## Confirmed gaps ranked by severity

### Medium — host accounting inputs and final results are absent from provider traces

The named trace proves the provider's empty array and structural acceptance, but not whether explicit zero support or another host accounting input produced the final result. This limits incident reconstruction and is already consistent with the repository boundary that providers do not own accounting. No formula or precedence defect was confirmed.

### Low — empty versus omitted added work is not distinguishable from the contract alone

`added_work_rows: []` is a valid semantic result, but the contract has no confidence, rationale, or completeness signal. The current prompt's anti-invention rule makes this intentional. Resolving it would require a diagnostic or evaluation policy, not a new category or mandatory overhead assumption.

### Low — provider row amounts are intentionally non-authoritative

Rows may be identified without amounts, while host accounting supplies quantities. This is safe because derived accounting rejects missing amounts and canonical transformation explicitly documents host-input precedence. It can make a provider row's quantitative contribution invisible unless the host input and final result are traced together.

## Minimal recommendations

No production correction is justified. Preserve the existing taxonomy, prompt, contracts, validation, precedence, units, and formulas. If future incident reconstruction requires stronger evidence, consider a separate audit/trace enhancement that records redacted accounting mode, support-input basis, whether an explicit override was used, and final W0/W1 fields. That would be an observability design change and should not be implemented as an added-work semantic change.

Do not require nonzero interaction or verification, infer added work from REMOVE, reinterpret baseline oversight as added work, or use added work to compensate for coarse decomposition. Mixed-activity handling remains deferred under Phase 02 and is outside this verification.

## Final recommendation

**No Changes.** Phase 03 can close without implementation changes. The added-work taxonomy and accounting handoff are implemented consistently; the Production Scheduling empty result is valid but only partially observable because host accounting was not recorded in the provider trace. Further work, if approved, belongs to an explicit traceability/evaluation phase rather than a correction to added-work classification or accounting.
