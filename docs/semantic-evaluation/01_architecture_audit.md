# Semantic Evaluation Architecture Audit

**Status:** analysis only. This document records the current implementation and a proposed migration plan. No production behavior is changed by this audit.

## 1. Executive summary

The repository currently has a sound deterministic structural-validation boundary, but semantic validation is still a lexical heuristic. Operational decomposition is parsed by provider adapters, checked by `validation/stages.py`, and then either accepted or sent through the existing bounded repair loop. The repair loop re-runs the same deterministic semantic validator; it is not an independent semantic evaluator. Replacing that validator with structured LLM evaluation is an intentional behavior change, not a compatibility mode.

The current semantic validator is too narrow for the intended contract. It recognizes a fixed operational-verb allowlist and a small set of abstract-label regular expressions. Consequently, legitimate planning and deliverable-producing work such as `Develop Production Schedule`, `Draft Production Schedule`, and `Outline Preliminary Production Schedule` can be rejected because `develop`, `draft`, and `outline` are not in the allowlist. The validator also cannot reliably judge time consumption, distinctness, overlap, granularity, or whether a cognitive task is sufficiently specific. During implementation, all keyword-based semantic acceptance and rejection—including the allowlist, abstract-label regexes, and forbidden-phrase matching—will be removed rather than retained as a fallback.

The approved migration is to keep schema, identity, dependency, ordering, and accounting invariants deterministic, then add a provider-independent structured semantic evaluator after structural validation. The evaluator will assess the complete operational decomposition in one call and return machine-readable findings tied to subtask IDs where applicable. Existing provider structured-output and tracing abstractions should be reused. Existing bounded repair should consume evaluator findings and re-enter the same structural-validation/evaluation path. No evaluator call should recursively evaluate its own output, and the current maximum of two repair attempts remains the policy.

The approved architecture enables semantic evaluation by default once migration is complete, requires an explicit error when the evaluator is unavailable, and exposes a provider-independent `SemanticEvaluator` capability backed by the existing provider adapters. This initiative applies initially to operational task decomposition only. Transformation classification, transformation decomposition, and accounting validation remain unchanged and outside the evaluator migration. Remaining decisions concern model configuration, tracing privacy, and public API migration details.

## 2. Current architecture and execution flow

### Confirmed current execution path

The current task-only implementation follows this path:

```text
provider.generate_operational_decomposition
  -> ProviderStageResponse envelope/stage checks
  -> Pydantic OperationalDecomposition parsing in the provider adapter
  -> deterministic structural validation
  -> keyword-based semantic validation
  -> bounded repair using the provider's repair hook, if available
  -> revalidation of repaired output
  -> baseline effort allocation
  -> TaskDecomposition
```

The existing semantic validation relies on operational-verb allowlists, abstract-label regular expressions, and forbidden-phrase matching. These checks are deterministic lexical heuristics, not contextual semantic evaluation.

The current repair mechanism reuses these same validation rules. It does not invoke an independent LLM evaluator.

The convenience API composes task decomposition with transformation decomposition:

```text
decompose_task
  -> decompose_transformation(existing TaskDecomposition)
  -> accounting/staged transformation result
```

`src/task_decomposition/application/provider_service.py:21-50` owns this convenience composition. Transformation decomposition consumes the existing task decomposition; it does not regenerate it (`src/task_decomposition/application/transformation_decomposition.py:41-91`).

### Proposed execution path (not yet implemented)

The approved target architecture is:

```text
provider.generate_operational_decomposition
  -> ProviderStageResponse envelope/stage checks
  -> Pydantic OperationalDecomposition parsing
  -> deterministic structural validation
  -> LLM semantic evaluation of complete decomposition
       ├── accept -> baseline effort allocation
       ├── repair -> targeted repair
       │             -> structural revalidation
       │             -> LLM semantic re-evaluation
       └── reject -> semantic rejection error
  -> TaskDecomposition (accepted output only)
```

The migration will:

- Remove keyword-based semantic validation entirely, without a legacy fallback.
- Preserve deterministic structural and contract validation.
- Introduce a provider-independent `SemanticEvaluator`.
- Preserve the existing maximum of two repair attempts.
- Distinguish semantic rejection from evaluator execution or contract failures.
- Leave transformation decomposition and accounting behavior unchanged.

This target architecture is approved but has not yet been implemented.

### Detailed task path

1. `decompose_task` validates the provider capability, obtains a `TraceLogger` session, calls the operational provider operation through `call_stage`, and passes the result to `_validate_or_repair_operational` (`src/task_decomposition/application/task_decomposition.py:34-75`).
2. Provider adapters produce a `ProviderStageResponse` whose payload is untrusted provider output (`src/task_decomposition/contracts/provider.py:81-90`). The operational request includes the task, context, effort, request ID, and provenance (`src/task_decomposition/contracts/provider.py:25-59`).
3. `call_stage` invokes the operation, records provider exceptions, validates the response envelope, and checks returned stage and provider provenance (`src/task_decomposition/application/_provider_stage.py:32-73`).
4. `validate_operational_response` calls `validate_operational_decomposition` and maps semantic failures to `ProviderSemanticValidationError`; other stage failures become `ProviderContractValidationError` (`src/task_decomposition/application/_provider_stage.py:76-99`).
5. `validate_operational_decomposition` validates the Pydantic model, unique IDs, one-based contiguous sequence indexes, dependency references, self-dependencies, duplicate dependencies, and dependency precedence (`src/task_decomposition/validation/stages.py:25-66`). The eventual implementation removes the keyword semantic call from this structural path.
6. The migrated `_validate_or_repair_operational` evaluates the complete structurally valid decomposition. On a `repair` decision it records findings, then attempts the optional provider method `repair_operational_decomposition` up to two times. Each repair goes through `call_stage`, structural validation, and semantic re-evaluation. Structural failure in repaired output is not bypassed.
7. On semantic rejection after exhaustion, a semantic-validation error preserves findings, the original rejected response, the repair count, and the final response (`src/task_decomposition/errors.py:85-104`). Evaluator/API/schema failures use distinct execution or contract errors and are never represented as semantic rejection.
8. A valid operational decomposition is allocated and assembled into the frozen `TaskDecomposition` result (`src/task_decomposition/application/task_decomposition.py:66-75` and the allocation code following the validation helper).

### Provider and tracing boundaries

The provider protocol currently requires only `provider_id` and `generate_operational_decomposition` for task decomposition (`src/task_decomposition/ports/provider.py:14-24`). The repair hook is discovered dynamically with `getattr` by the application, so adding it as a required protocol method would break custom providers.

OpenAI uses `responses.parse()` in its structured-stage implementation (`src/task_decomposition/providers/openai.py`). DeepSeek uses an OpenAI-compatible chat-completions call and JSON parsing; Gemini uses `generate_content` with a JSON schema. Their adapters have provider-specific transport code but share application-stage and tracing conventions.

`TraceLogger` is the shared tracing abstraction (`src/task_decomposition/tracing.py`). It emits JSONL request, response, parsed-output, validation, repair, exception, and execution-summary events. Traces are disabled by default, use `logs/llm/task_decomposition.jsonl` by default when enabled, and carry correlation and invocation IDs. Provider SDK limitations can prevent OpenAI's raw response from being available when `responses.parse()` raises during internal Pydantic parsing; the tracer records raw-response availability separately from parsed-output state.

## 3. File and function ownership map

| Responsibility | Current owner | Relevant implementation |
| --- | --- | --- |
| Public task API | `application/task_decomposition.py` | `decompose_task`, `_validate_or_repair_operational` (`:34-190`) |
| Convenience task + transformation composition | `application/provider_service.py` | `decompose` (`:21-50`) |
| Transformation orchestration | `application/transformation_decomposition.py` | `_decompose_transformation` (`:41-91`) |
| Provider invocation envelope | `application/_provider_stage.py` | `call_stage`, provider ID checks (`:25-73`) |
| Operational response validation adapter | `application/_provider_stage.py` | `validate_operational_response` (`:76-99`) |
| Operational structural and semantic stage checks | `validation/stages.py` | `validate_operational_decomposition` (`:25-66`) |
| Lexical semantic rules | `validation/semantic.py` | forbidden phrases, verb allowlist, abstract-label patterns, `operational_subtask_semantic_errors` (`:12-138`) |
| Pydantic domain contracts | `contracts/stages.py` | `OperationalSubtask` (`:26-37`), `OperationalDecomposition` (`:40-46`), result contracts (`:75-94`) |
| Provider request/response contracts | `contracts/provider.py` | request models and `ProviderStageResponse` (`:25-90`) |
| Provider capability protocols | `ports/provider.py` | task and transformation provider protocols (`:14-50`) |
| Provider prompts | `providers/prompts.py` | operational and repair prompts (`:3-37`) |
| Provider structured transport | `providers/openai.py`, `deepseek.py`, `gemini.py` | provider SDK calls, parsing, repair hooks |
| Error mapping and repair diagnostics | `errors.py` | `ProviderSemanticValidationError` (`:85-104`) |
| Shared execution tracing | `tracing.py` | session, invocation, validation, repair, exception, summary events |

## 4. Validation responsibility audit

### Rules that should remain deterministic

These are structural or contract invariants and do not require an LLM judgment:

- Pydantic field types, required fields, minimum collection sizes, and schema shape (`contracts/stages.py`).
- Unique subtask IDs, contiguous one-based sequence indexes, valid dependency IDs, no self-dependencies, no duplicate dependencies, and dependency precedence (`validation/stages.py:25-64`).
- Stage identity, provider provenance, and response envelope shape (`application/_provider_stage.py:32-73`).
- Transformation identity/cardinality/order and retain/remove or added-work schema invariants (`validation/stages.py:69-151`).
- Allocation and accounting identities after a valid decomposition. These belong to the existing application/domain boundaries, not to an evaluator.

### Semantic judgments that should move to structured evaluation

The intended contract requires contextual judgment that a short keyword list cannot reliably provide:

- Whether a subtask is a reasonable, distinct unit of work that consumes non-zero human time.
- Whether planning, scheduling, analysis, evaluation, judgment, decision-making, or deliverable creation is described specifically enough to count as work.
- Whether a label is merely a goal, state, outcome, or vague completion statement.
- Whether subtasks are redundant, excessively fragmented, overlapping, incomplete, or at an inappropriate granularity for the input task.
- Whether a decision or cognitive activity says what is evaluated, determined, planned, created, or communicated rather than only naming a result.

These judgments will be returned as structured findings, not inferred from a provider's free-form explanation. A valid but broad subtask must not fail merely because further decomposition is possible; the evaluator should recommend refinement only when the subtask is not a reasonable distinct unit in context. Acceptance must be based on the evaluator's explicit decision and findings, not an arbitrary numerical quality threshold.

### Explicit policy prohibitions

The current `_FORBIDDEN_PHRASES` rules in `validation/semantic.py:12-34` are keyword and substring semantic checks, not objective structural invariants. They will be removed along with `_OPERATIONAL_VERBS`, `_ABSTRACT_LABELS`, and any equivalent lexical rule. Internal decomposition/meta-analysis activities will instead be expressed in the evaluator rubric and returned as structured findings. No legacy keyword-validation mode or silent fallback will remain.

The audit found no other keyword-based operational-work acceptance or rejection in the operational execution path beyond `validation/semantic.py`; the provider prompts are generation guidance, not runtime validation. Structural checks in `validation/stages.py` and response checks in `application/_provider_stage.py` are retained because they verify objective contracts.

### Decision and finding semantics

The evaluator returns exactly one top-level decision:

- `accept`: the complete decomposition is operationally acceptable.
- `repair`: material, actionable defects require targeted correction.
- `reject`: the decomposition is fundamentally unsuitable and should not be accepted through repair.

Findings use these severities:

- `suggestion`: nonblocking improvement; it may be reported but cannot change an `accept` decision to `repair`.
- `repairable`: material defect requiring correction; it requires a `repair` decision unless the evaluator also identifies a blocking defect.
- `blocking`: defect requiring rejection; it requires a `reject` decision.

Consistency rules are deterministic at the evaluation-contract boundary: `accept` cannot contain `repairable` or `blocking` findings; `repair` must contain at least one `repairable` finding and no `blocking` finding; `reject` must contain at least one `blocking` finding. Suggestions may accompany any decision. These rules validate the evaluator response structure; they do not score semantic quality numerically.

## 5. Current keyword validator and intentional removal

`src/task_decomposition/validation/semantic.py:36-82` defines `_OPERATIONAL_VERBS` and `_ABSTRACT_LABELS`. The current operational check is:

```python
text = " ".join(
    part for part in (subtask.subtask_name, subtask.description or "") if part
).strip().lower()

if _ABSTRACT_LABELS.fullmatch(text):
    errors.append(...)

if not any(
    re.search(rf"\b{re.escape(verb)}(?:s|ed|ing)?\b", text)
    for verb in _OPERATIONAL_VERBS
):
    errors.append(...)
```

The validator examines both `subtask_name` and `description`, not just the name (`:111-138`). This has several consequences:

- `Develop Production Schedule`, `Draft Production Schedule`, and `Outline Preliminary Production Schedule` do not contain any allowlisted base verb. They therefore receive the “does not describe a concrete operational action” error at the no-allowlisted-verb branch (`semantic.py:131-137`).
- None of the three names matches the current abstract-label regex at `semantic.py:127-129`; the rejection is the allowlist failure, not the abstract-label rule.
- `Make approval decision` matches the first abstract-label regex (`semantic.py:84-88`) and is rejected as too abstract even though `make` is not an operational allowlist verb.
- `Invoice approved` matches the state/outcome regex (`semantic.py:84-88`) and is rejected as a result rather than work.
- A description containing an allowlisted verb can make an otherwise vague name pass, because name and description are combined before the lexical search. Conversely, a forbidden phrase anywhere in nested output text can fail the whole response because `_iter_text_values` recursively visits strings (`semantic.py:91-151`).
- The inflection regex only derives `s`, `ed`, and `ing`; it is not a general morphological or contextual analysis. It cannot reason about whether the verb is being used as a meaningful unit of work.
- The validator does not measure time consumption, distinctness, overlap, granularity, completeness, or whether the text is a goal/state/outcome except for a few exact-ish patterns.
- `assert_no_forbidden_meta_language` reports the first matching forbidden phrase, while `operational_subtask_semantic_errors` accumulates per-subtask lexical errors. This produces useful basic diagnostics but not a complete semantic explanation.

### Classification of the three reported labels

| Label | Exact current condition | Contract assessment |
| --- | --- | --- |
| `Develop Production Schedule` | No abstract-label match; no allowlisted verb at `semantic.py:131-137` because `develop` is absent from `_OPERATIONAL_VERBS` (`:36-82`). | False positive under the intended contract. Developing a schedule is planning/creation work and normally consumes time. The evaluator should judge whether context makes it sufficiently specific and non-overlapping. |
| `Draft Production Schedule` | No abstract-label match; no allowlisted verb at `semantic.py:131-137` because `draft` is absent from the allowlist. | False positive under the intended contract. Drafting a deliverable is operational work. It may be too broad only if the surrounding task requires a more granular decomposition, which the current validator cannot determine. |
| `Outline Preliminary Production Schedule` | No abstract-label match; no allowlisted verb at `semantic.py:131-137` because `outline` is absent from the allowlist. | Usually a false positive. It describes creation/planning work. Whether “outline” is a reasonable unit or an unnecessary intermediate artifact is a granularity judgment, not something the current regex can establish. |

The exact current rejection for all three is therefore a lexical false positive, not evidence that the work is a pure state or outcome. `Outline Preliminary Production Schedule` may warrant evaluator scrutiny for granularity in a particular decomposition, but it is not inherently invalid. These findings explain the current behavior only; the allowlist, regexes, forbidden phrases, and equivalent keyword rules are scheduled for removal and must not be implemented as a compatibility fallback.

## 6. Generation and repair prompt consistency

`providers/prompts.py:3-22` already tells the generator to create reasonable, distinct, time-consuming human work and explicitly allows physical work, system interaction, communication, information processing, investigation, analysis, evaluation, judgment, and decision-making. It also rejects labels that merely state a goal, state, outcome, or completion. The repair prompt repeats those requirements (`:24-37`) and instructs the model to preserve valid subtasks and make the smallest correction.

This is directionally consistent with the intended contract, including the important distinction that decision-making can be valid when specific. However, there are gaps:

- The prompts do not explicitly illustrate planning, scheduling, drafting, outlining, or creating a deliverable as valid work.
- The prompts guide generation but do not provide an independent, structured semantic decision and finding schema.
- The current deterministic validator can contradict the prompt by rejecting legitimate verbs such as `develop`, `draft`, and `outline`.
- Repair feedback is currently derived from the lexical validator, so it cannot express context-sensitive findings such as overlap, inappropriate granularity, or insufficiently described evaluation criteria.

The prompt should be updated as part of evaluator migration, but generation guidance and evaluator authority should remain conceptually separate.

## 7. Proposed target architecture

### Boundary

Use this pipeline:

```text
Generation
  -> provider/schema parsing
  -> deterministic structural validation
  -> structured LLM semantic evaluation
  -> ACCEPT
       or targeted repair -> structural validation -> re-evaluation
  -> final result or bounded failure
```

The evaluator should assess the complete decomposition so it can detect overlap, missing coverage, and inappropriate granularity, while returning findings with optional `subtask_id` values for targeted repair.

This boundary applies only to the operational decomposition stage. Retain/remove classification, added-work classification, transformation orchestration, and accounting continue to use their current contracts and deterministic validation responsibilities.

### Minimal package shape

Add a provider-independent `evaluation/` package in a later implementation phase, for example:

```text
src/task_decomposition/evaluation/
  __init__.py
  contracts.py
  rubric.py
  ports.py
```

Proposed responsibilities:

- `contracts.py`: Pydantic contracts for an evaluation request, a finding, and an evaluation result.
- `rubric.py`: versioned prose rubric and explicit examples; it should not be another operational-verb allowlist.
- `ports.py`: a small evaluator capability protocol, independent of OpenAI, DeepSeek, or Gemini transport.

The approved contract shape is:

```text
SemanticEvaluationRequest
  decomposition
  source task and description
  context
  rubric_version
  correlation/request identifiers

SemanticFinding
  subtask_id: optional string
  code: stable machine-readable code
  category: abstraction | outcome | overlap | granularity | completeness | policy
  severity: suggestion | repairable | blocking
  message: concise actionable explanation
  evidence: optional label or field reference

SemanticEvaluation
  decision: accept | repair | reject
  findings: list[SemanticFinding]
  rubric_version
  evaluator provenance
```

Findings contain only observable output and rubric-based explanations; they must not contain hidden model reasoning. The evaluator evaluates the complete decomposition in one call, while findings reference affected subtask IDs where applicable. It does not call multiple evaluator agents, use a Thought Graph, or create an agent swarm.

The provider-independent interface is `SemanticEvaluator.evaluate(request) -> SemanticEvaluation`. Provider adapters implement that capability using the existing structured-output infrastructure. The evaluator is separate from generation: generation proposes a decomposition, while evaluation independently decides whether the complete proposal satisfies the rubric.

### Reuse of provider abstractions

Do not create a second provider transport framework. Reuse:

- `ProviderStageResponse` as the untrusted structured-output envelope, or a narrowly typed equivalent if a new evaluator stage requires a new stage identifier.
- Existing provider IDs, provenance, request IDs, `call_stage`, and `TraceLogger` session/invocation facilities.
- Existing provider SDK isolation and structured-output helpers in each adapter.

Because `TaskDecompositionProvider` is a public runtime protocol and custom providers currently need not implement repair, evaluator support should be exposed through the separate provider-independent `SemanticEvaluator` capability rather than making a new method mandatory on the existing protocol. That avoids breaking custom providers while giving application code one common interface. Only the adapter behind it should know whether it is OpenAI, DeepSeek, or Gemini.

## 8. Repair and orchestration design

### Decisions

- `accept`: the complete decomposition is operationally acceptable; suggestions may still be present.
- `repair`: one or more `repairable` findings are local/actionable and can plausibly be corrected by rewriting or minimally adjusting the decomposition.
- `reject`: one or more `blocking` findings make the decomposition fundamentally unsuitable.

`suggestion` findings never trigger repair. Suggested repairable findings include vague labels, missing operational specificity, accidental duplicate/overlapping subtasks, and material granularity issues. A valid but broad subtask is not automatically rejected merely because it could be decomposed further. Structural invalidity remains a deterministic failure and must be validated before the evaluator sees the output; evaluator output itself must also pass structural validation.

### Bounded flow

1. Generate once.
2. Parse and structurally validate.
3. Evaluate once.
4. Return on `accept`.
5. On `repair`, send the original structured output plus all actionable findings to the existing repair capability. Preserve already-valid subtasks where possible.
6. Run repaired output through the same parse, structural-validation, and evaluator path.
7. Stop after the existing maximum of two operational repair attempts unless an explicit future configuration changes it.
8. Never invoke the evaluator recursively on evaluator feedback, and never accept repaired output without both structural and semantic validation.

The existing repair policy should be preserved during this migration; replacing lexical validation with evaluation is not a reason to alter the retry budget.

### Failure handling

Provider/API failure, timeout, malformed evaluator output, and evaluator schema failure are execution or contract errors, not semantic rejection. They must use distinct error types/diagnostics and tracing, with no implicit retry loop beyond the explicitly configured decomposition repair attempts. A semantic evaluator cannot repair its own malformed response. Evaluator unavailability produces an explicit error; it never falls back to keyword validation. Final semantic errors preserve the original structured decomposition, each evaluation result/findings set, repair attempt count, final repaired response, and failed stage. Evaluation is enabled by default once this migration is complete, and structural validation remains mandatory in every mode.

## 9. Tracing and error-handling requirements

The existing JSONL tracer under `logs/llm/` is sufficient as the shared mechanism. Extend event vocabulary only where needed; do not add provider-specific loggers.

For each evaluation and repair, preserve the existing correlation ID and add a distinct invocation ID and stage such as `semantic_evaluation` or `semantic_repair`. Events should include:

- evaluator provider/model and generation parameters;
- complete request messages and structured schema, subject to existing redaction;
- raw response availability, provider metadata, parsed evaluation, token usage, and latency where available;
- structural validation result before evaluation;
- evaluation decision and machine-readable findings;
- repair feedback, attempt number, repaired structured output, and subsequent validation/evaluation;
- final execution summary with failed stage and error information.

The existing OpenAI limitation is important: `responses.parse()` may raise a Pydantic validation error before returning a normal response object. The current tracer can record the exception, attached response data, and raw-output availability when the SDK exposes them, but cannot guarantee the original raw body through that API path. A future adapter can use a lower-level/raw response hook only if supported by the pinned SDK, while preserving schema enforcement. Empty parsed output must remain distinguishable from unavailable raw output. DeepSeek and Gemini should follow the same event schema using the metadata each SDK exposes.

Tracing remains opt-in, credentials remain redacted, and prompts/responses must be documented as potentially sensitive business data. No hidden model reasoning or external upload should be added.

## 10. Compatibility risks

1. **Provider protocol changes.** Adding evaluator methods to `TaskDecompositionProvider` would break custom implementations and test doubles. Prefer an optional capability or separate evaluator port.
2. **Intentional public behavior change.** Callers may directly use `validate_operational_decomposition` or `operational_subtask_semantic_errors`. Removing lexical checks changes behavior: structural validation remains deterministic, while contextual semantic acceptance/rejection moves to `SemanticEvaluator`. This is intentional; no legacy keyword mode is retained. Public API migration details remain to be decided.
3. **Error types and payloads.** Existing callers may inspect `ProviderSemanticValidationError` attributes. Add evaluator diagnostics compatibly or preserve the existing attributes while adding structured findings.
4. **Stage identifiers and tracing.** Adding evaluator stages may affect `ProviderStage` enums, trace filters, snapshots, and consumers of provenance.
5. **Optional SDK isolation.** Evaluator support must not cause OpenAI, DeepSeek, or Gemini imports during core package import. Existing lazy/provider-specific loading must remain.
6. **Provider structured-output differences.** OpenAI, DeepSeek, and Gemini expose different raw-response and usage metadata. Common events need explicit unavailable fields rather than pretending all providers have identical access.
7. **Test expectations.** Existing tests currently define lexical semantic rejection and repair behavior. They should be split into structural, policy, evaluator, and orchestration tests rather than silently rewritten.
8. **Evaluator availability.** The evaluator is enabled by default after migration and unavailable-evaluator errors are explicit. Configuration must make provider, model, timeout, token budget, and rubric version visible in tracing and diagnostics.

## 11. Phased implementation plan aligned with Prompts 2–5

The following phases assume Prompts 2–5 are the subsequent implementation prompts.

### Prompt 2 — Contracts and rubric

- Add typed evaluation request, finding, and result contracts.
- Define a versioned rubric encoding the intended operational-work contract.
- Define decision/severity codes and evaluator error behavior as `accept`/`repair`/`reject` with `suggestion`/`repairable`/`blocking` findings.
- Move internal meta-task judgments into the evaluator rubric; remove deterministic keyword policy checks.
- Add contract-only tests, including all three production-scheduling examples and pure outcomes.

### Prompt 3 — Provider integration

- Add one provider-independent evaluator capability.
- Reuse existing provider adapters and structured-output schema enforcement.
- Add shared evaluator prompt and repair feedback format.
- Implement OpenAI, DeepSeek, and Gemini structured evaluator calls without eager optional SDK imports.
- Add mocked provider tests for accepted, rejected, malformed, and unavailable evaluator responses.

### Prompt 4 — Application orchestration and tracing

- Split deterministic structural validation from semantic evaluation at the application boundary.
- Preserve the existing two-attempt repair policy.
- Re-evaluate every repaired response through the normal path.
- Add evaluator/repair/final-decision trace events using the existing JSONL tracer.
- Preserve original and final structured responses and findings in final errors.
- Make the evaluator the default semantic path and return an explicit execution error when it is unavailable; do not add evaluator-disabled keyword fallback behavior.

### Prompt 5 — Migration, documentation, and rollout tests

- Update generation and repair prompts with planning, scheduling, drafting, outlining, and deliverable examples.
- Remove direct lexical semantic acceptance/rejection APIs and document the intentional public behavior change; determine any compatibility-preserving API names only from caller evidence.
- Add end-to-end deterministic mocked tests for invoice review, production scheduling, onboarding, cognitive work, outcomes, overlap, and incomplete decompositions.
- Add an optional live-model evaluation suite that is credential-gated and excluded from normal tests.
- Document rubric version, tracing, evaluator configuration, and provider limitations.

## 12. Remaining unresolved questions

The following decisions remain intentionally open:

1. **Evaluator model configuration:** Which provider/model, timeout, token budget, and environment/configuration names should be the supported defaults?
2. **Tracing privacy:** Is full prompt/response capture acceptable for all opt-in environments, or should a content-suppression mode be added for sensitive deployments?
3. **Public API migration:** Should the existing direct semantic-validator exports become structural-only, be deprecated, or be replaced with a clearly named evaluator-facing API? This requires caller evidence and an API compatibility plan.
4. **Provider capability discovery:** Should application wiring use an explicit registry/factory for `SemanticEvaluator`, or a narrowly scoped optional capability lookup while preserving the existing provider protocols?

