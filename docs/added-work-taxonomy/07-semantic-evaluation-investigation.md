# Semantic Evaluation Investigation

## Scope and evidence

This investigation reads the complete 32-line JSONL trace at `logs/llm/task_decomposition_2026-10-14_225453.jsonl` and correlates it with the current evaluator contract, prompt/rubric, OpenAI adapter, and repair orchestration. No implementation code was changed.

## Execution timeline

1. The initial `operational_decomposition` request used `gpt-4o-mini` with a 4,000-token budget and completed successfully. The model returned nine subtasks covering orders, inventory, machine capacity, workforce availability, schedule creation, conflict resolution, finalization, communication, and schedule adherence. Structural validation passed.
2. The first `semantic_evaluation` request used the same model with the configured 2,000-token budget. It returned `decision="repair"` with two `repairable` findings: `subtask-9` was described as oversight rather than a distinct scheduling task (`incomplete_coverage`), and `subtask-6` needed more detail about identifying and resolving conflicts (`insufficient_operational_specificity`). The application accepted this evaluation and issued repair attempt 1.
3. Repair attempt 1 completed successfully and structural validation passed. The repaired output changed subtask 6 to identify conflicts, changed subtask 7 to resolve them, and changed subtask 9 to confirm schedule compliance.
4. The second `semantic_evaluation` again returned `decision="repair"`, with three `repairable` findings: subtask 9 did not explain how deviations would be handled, subtask 6 could name conflict types such as resource clashes or timing issues, and subtask 1 should explain how orders are prioritized. The application accepted this evaluation and issued repair attempt 2.
5. Repair attempt 2 completed successfully and structural validation passed. The resulting decomposition changed subtask 1 to collect and prioritize orders, subtask 6 to identify potential resource or timing conflicts, and subtask 9 to monitor compliance and address deviations.
6. The final `semantic_evaluation` request was sent with the same 2,000-token budget, but no successful response event was recorded. The SDK/application trace records a `ValidationError`: `repair evaluations cannot contain blocking findings`. Execution terminated with `ProviderOutputError: OpenAI structured output failed during semantic_evaluation`.

## Observed findings versus inference

The first two evaluator responses and all repair instructions are directly present in the trace. Both responses consistently used `repair` with only `repairable` severities, so they satisfied the Pydantic invariant at that point. The repairs were not structural failures; both passed structural validation. The request also supplied `task_context.domain="customer_support"` for a Production Scheduling task; that context mismatch is observed evidence and could have influenced the evaluator's judgment, although the trace cannot prove that it did.

The final model output is not directly present. There is no line 30 `llm.response`, `llm.parsed`, or raw output record. The logged exception contains the top-level invalid combination but not the complete finding list. Therefore the only confirmed fact about the final response is that it contained `decision="repair"` and at least one `blocking` finding, which the model/schema contract rejects. The exact blocking code, subtask, message, and whether repairable findings were also present cannot be established from this trace.

## Contract and prompt audit

`SemanticEvaluation` defines three decisions and three finding severities. Its validator is internally coherent: `accept` allows suggestions only, `repair` requires at least one repairable finding and forbids blocking findings, and `reject` requires a blocking finding. The validator is therefore not demonstrably incorrect and should not be weakened merely to accept the live response.

The rubric also defines the intended distinction: `repair` is for a material actionable defect that can be corrected while preserving the useful decomposition; `reject` is for a blocking defect that makes the decomposition fundamentally unsuitable; suggestions are for nonblocking clarity improvements. However, the prompt does not give a deterministic rule for assigning severity to individual finding codes or for resolving mixed findings. It asks the model to choose both an overall decision and independent finding severities.

The trace shows evaluator over-strictness as a contributing factor before the terminal error. Findings such as “could benefit from specifying” and “should indicate ... to improve operational clarity” are optional specificity improvements in context, yet they were labeled `repairable` and triggered two repairs. The rubric says not to require further decomposition and to distinguish optional improvements, but it does not explicitly prohibit repair for wording-level improvements. This calibration ambiguity likely encouraged repeated repairs even though the decomposition was materially usable.

The direct terminal cause is different: the final model produced an inconsistent decision/severity combination. This is a provider-output contract violation, not evidence that the Pydantic validator should accept blocking findings under `repair`.

## Repair-loop audit

`decompose_task()` performs one evaluation, then at most two repair attempts using `for attempt in range(1, 3)`. Each repaired response is structurally validated and re-evaluated. A valid `reject` terminates immediately; a third `repair` terminates with `ProviderSemanticValidationError`. In this run, the loop did not reach its normal third-repair terminal path because the OpenAI adapter failed while parsing the final evaluator response.

The orchestration correctly treats an evaluator contract failure as a provider-output failure rather than converting it into acceptance or rejection. It does not retry malformed evaluator decisions. That preserves meaningful validation, but it makes a single model inconsistency terminal after the repair budget has already been consumed.

The two repair cycles also reveal feedback drift: each repair addressed the previous wording request but the evaluator generated new specificity requests for other subtasks. This is consistent with an over-sensitive rubric/prompt calibration problem, not a structural repair failure. The current repair prompt says to apply minimal corrections, but the evaluator prompt does not define a threshold at which clarity becomes material enough to require repair.

## OpenAI parsing and traceability

The OpenAI adapter calls `responses.parse(..., text_format=SemanticEvaluation)`. In the failing call, the SDK raised during parsing/validation, before `_evaluate_inner()` received a response object. Consequently, the adapter could not call `tracer.response()` and the trace contains no raw response. The exception also exposed no response/body/raw-response attributes, so the existing exception tracing had no provider payload to attach.

The trace is therefore sufficient to identify the invalid combination, but not to inspect or recover the exact final JSON. This is an observability gap in the provider/SDK boundary, not proof that the model emitted malformed JSON; the available evidence indicates schema-valid JSON whose Pydantic cross-field validator rejected its semantics.

## Root cause and contributing factors

Confirmed root cause: the final evaluator response combined `decision="repair"` with at least one `blocking` finding. The `SemanticEvaluation` cross-field validator rejected that combination, and the OpenAI structured parser surfaced the rejection as a provider-output failure.

Contributing factors: the semantic prompt/rubric permits the model to make two related judgments independently—overall decision and per-finding severity—without an explicit mixed-severity policy. It also leaves enough ambiguity for optional specificity improvements to be labeled `repairable`, which caused two unnecessary or marginal repair cycles. The mismatched `customer_support` context may have added domain noise. The trace does not establish whether the final blocking finding itself was substantively correct.

Not supported by the evidence: a failure of structural validation, a repair-hook failure, an exceeded output-token budget, an accounting/taxonomy issue, or an incorrect Pydantic invariant.

## Recommended smallest robust correction

First clarify the semantic rubric/prompt, without changing the schema or budgets. State that suggestions are for optional wording or specificity improvements; `repair` is reserved for material defects that impair execution or omit a required task component; `reject` is required whenever any finding is blocking; and a response containing both blocking and repairable findings must use `reject`. Add one production-scheduling example showing that reasonable planning, conflict resolution, and schedule communication are acceptable without extra micro-specificity.

Second add a narrow deterministic consistency check at the provider/application boundary only as an explicit diagnostic safeguard: if an evaluator payload has blocking findings with `repair`, report a contract error that includes the severities and finding identifiers, rather than attempting to reinterpret the decision. Do not downgrade blocking findings or silently convert the decision.

For observability, preserve the raw provider response or SDK error body when available before structured parsing fails, and include a sanitized representation in the trace. This is useful but secondary to prompt calibration and should remain a small adapter-boundary change.

I do not recommend weakening the Pydantic validator, adding a retry for this semantic inconsistency, increasing the token budget, or expanding the repair limit. A bounded retry could mask the inconsistent evaluator contract and would not address the repeated repair over-triggering.

## Likely files for a reviewed implementation

- `src/task_transmorph/evaluation/rubric.py` and `src/task_transmorph/providers/prompts.py` for severity/decision calibration.
- `src/task_transmorph/providers/openai.py` and `src/task_transmorph/tracing.py` for failure-time provider-output observability.
- `src/task_transmorph/evaluation/contracts.py` only if the reviewed design chooses a different explicit decision model; no schema change is currently required.
- `src/task_transmorph/application/task_decomposition.py` only for diagnostic handling or terminal-error reporting; the current two-attempt bound is already explicit and bounded.

## Focused regression tests needed

- A prompt/rubric contract test asserting that optional specificity is a suggestion and material omission is repairable or blocking according to explicit examples.
- A contract test retaining rejection of `repair` plus `blocking`, and retaining rejection of `reject` without a blocking finding.
- An OpenAI adapter test for a provider response containing `repair` plus `blocking`, asserting a provider-output failure and diagnostic trace data without acceptance.
- A trace test covering SDK structured-parse failure with and without an attached raw response/body.
- An orchestration test proving two valid repair cycles remain bounded and that a malformed third evaluator decision terminates as a provider-output error.
- A live-fixture regression using the Production Scheduling decomposition that accepts the repaired, materially adequate output without requiring additional wording-only repairs.

## Remaining uncertainty

The exact final blocking finding is unavailable because the SDK raised before the adapter logged a response. Confirming whether that blocking judgment was substantively warranted requires rerunning with provider response/error-body capture enabled or an equivalent replay fixture. The smallest evidence-based correction is therefore prompt/rubric calibration plus improved parse-failure traceability, followed by focused tests; no implementation change is made in this investigation.

## Implementation and verification

The investigation corrections were implemented without changing the added-work taxonomy, accounting contracts, W0/W1 formulas, repair budget, or AgenticAICompass.

- `src/task_transmorph/evaluation/rubric.py` now defines operational completeness and executability as the acceptance threshold, explicitly treats wording/specificity/presentation improvements as suggestions, and states the severity precedence: suggestions only produce `accept`, repairable findings without blocking findings produce `repair`, and any blocking finding produces `reject`. The Production Scheduling-specific rubric example was removed to keep the general prompt domain-neutral.
- `src/task_transmorph/providers/prompts.py` now repeats the concise decision rules at the provider boundary and requires blocking findings to use `reject`.
- `examples/openai_decompose.py` now defaults its CLI domain to `production_scheduling`, correcting the source of the earlier `customer_support` context mismatch. No domain inference or automatic correction was added. The example's explicit support inputs were also updated to the active two-category accounting contract.
- `src/task_transmorph/providers/openai.py` and `src/task_transmorph/tracing.py` now record safe structured-parse diagnostics when available: decision values, finding severities, and allowlisted provider error metadata. Raw request content and credentials are not added, existing redaction remains active, and `ProviderOutputError` behavior is unchanged.
- Regression tests cover prompt calibration, material repair/rejection combinations, mixed blocking/repairable rejection, parse failures with and without provider details, redaction, bounded repairs, and the corrected example context.

Focused verification passed: `102 passed` across evaluation contracts, semantic orchestration/provider tests, OpenAI provider tests, the example-context test, and tracing tests. Formatting, `git diff --check`, and isolated compilation passed. The full suite reached `240 passed, 5 failures, 3 skipped`; the failures are existing unrelated DeepSeek semantic-fixture behavior and live provider/network tests, including DNS connection failures in the restricted environment.

The requested live command completed successfully with the existing stage budgets. The new trace is `logs/llm/task_decomposition_2026-10-14_234344.jsonl`. It reached operational decomposition, first-pass semantic `accept`, RETAIN/REMOVE classification, `AI_INTERACTION`/`AI_VERIFICATION` added-work classification, and deterministic accounting. The semantic evaluation used `production_scheduling` context, emitted 37 output tokens, and produced no repair or truncation event.

Final live accounting was `ai_interaction_work=8`, `ai_verification_work=6`, `added_human_work=14`, `W0=100`, `W1=74`, `gross_removed_work_ratio=0.40`, `added_human_work_ratio=0.14`, `net_remaining_work_ratio=0.74`, `net_substitution_ratio=0.26`, and `net_augmentation_multiplier=1.351351351351351351351351351`. The result was classified as `gain`; added effort was counted exactly once.

Remaining limitations: one successful live run demonstrates end-to-end execution, not statistical evaluator reliability. The original failing trace still lacks the exact final blocking finding because the SDK provided no raw response or error body; the new diagnostics will capture decision/severity metadata or safe provider details on future failures when the SDK exposes them.
