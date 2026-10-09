# Semantic Evaluator Provider Integration

**Status:** Prompt 3 implementation. Provider-backed evaluator calls are implemented, but application orchestration and removal of the existing keyword validator are intentionally deferred.

## 1. Files and integration approach

Changed files:

- `src/task_decomposition/evaluation/` remains the provider-neutral contract/rubric/protocol package from Prompt 2.
- `src/task_decomposition/providers/_semantic.py` adds shared evaluator payload serialization and post-provider contract checks.
- `src/task_decomposition/providers/prompts.py` adds the shared `SEMANTIC_EVALUATION_PROMPT`.
- `src/task_decomposition/providers/openai.py` adds `evaluate()` using the existing Responses API structured parser.
- `src/task_decomposition/providers/deepseek.py` adds `evaluate()` using the existing OpenAI-compatible chat-completions JSON path.
- `src/task_decomposition/providers/gemini.py` adds `evaluate()` using the existing Gemini JSON-schema generation path.
- `src/task_decomposition/providers/_shared.py` allows provider failure mapping to use the new evaluator stage name without changing existing stage behavior.
- `src/task_decomposition/tracing.py` allows response and parsed events to carry their explicit stage.
- `tests/test_semantic_evaluator_providers.py` adds deterministic mocked-provider coverage.

No application orchestration, decomposition repair loop, transformation logic, accounting logic, or existing keyword validator was changed.

Each concrete provider now structurally satisfies the existing `SemanticEvaluator` protocol without adding a method to `TaskDecompositionProvider`. SDK imports remain lazy in the provider constructors. No separate transport framework, registry, agent framework, Thought Graph, or multi-agent evaluator was introduced.

## 2. Evaluator invocation and structured-output contracts

Each provider exposes:

```python
evaluate(request: SemanticEvaluationRequest) -> SemanticEvaluation
```

The request payload contains:

- original task name and description;
- task context;
- the complete operational decomposition;
- requested rubric version;
- request and correlation identifiers.

The response is parsed and validated as `SemanticEvaluation`. The provider methods return a valid `SemanticEvaluation` for `accept`, `repair`, or `reject`; they do not raise an exception for a valid semantic rejection.

The shared `_semantic.py` helper additionally verifies:

1. a parsed response is present;
2. Pydantic contract and decision/finding consistency validation succeeds;
3. returned `rubric_version` exactly matches the request;
4. every non-null finding `subtask_id` exists in the submitted decomposition;
5. authoritative adapter provenance is attached to the result.

Unknown fields, malformed JSON, empty parsed output, invalid decision/severity combinations, unknown subtask IDs, and rubric mismatches cannot be accepted.

## 3. Shared evaluator prompt

`SEMANTIC_EVALUATION_PROMPT` combines:

- `SEMANTIC_EVALUATION_RUBRIC_VERSION`;
- the complete `SEMANTIC_EVALUATION_RUBRIC`;
- instructions to evaluate the complete decomposition in the task context;
- instructions to return only the structured evaluation object;
- instructions to provide concise actionable findings without hidden reasoning or numerical scores.

The serialized request is supplied as JSON. The rubric explicitly allows planning, scheduling, drafting, analysis, judgment, decision-making, and deliverable creation when they represent meaningful work. It distinguishes nonblocking suggestions from repairable and blocking findings. The prompt contains no operational-verb allowlist, lexical heuristic, or deterministic acceptance rule.

Generation and semantic evaluation remain separate: the generation methods continue to use their existing prompts, while `evaluate()` independently assesses the complete proposed decomposition.

## 4. Provider-specific implementation

### OpenAI

`OpenAIDecompositionProvider.evaluate()` calls the existing `client.responses.parse()` with `SemanticEvaluation` as `text_format`. It records the evaluator stage as `semantic_evaluation` and preserves the existing model and max-output-token configuration.

If the Responses SDK raises a JSON/Pydantic parsing failure before returning a response, the evaluator adapter maps it to `ProviderOutputError`. Other SDK failures map to `ProviderExecutionError`, and authentication/permission failures map to `ProviderAuthenticationError`. This keeps malformed structured output distinct from transport failure while retaining the existing generation behavior.

### DeepSeek

`DeepSeekDecompositionProvider.evaluate()` uses the existing chat-completions client with `response_format={"type": "json_object"}`. The response content is decoded as JSON and validated against `SemanticEvaluation`. Empty content and malformed JSON produce `ProviderOutputError`; API and authentication failures use the existing provider failure mapping.

### Gemini

`GeminiDecompositionProvider.evaluate()` uses `generate_content()` with `response_mime_type="application/json"` and `SemanticEvaluation` as the response schema. It accepts the SDK's parsed object or text fallback, then validates the result against the same shared helper. Empty output, schema errors, and invalid evaluator contracts produce `ProviderOutputError`.

## 5. Error mapping

The implemented boundary distinguishes:

- **Semantic rejection:** returned `SemanticEvaluation(decision="reject", ...)` with a blocking finding.
- **Evaluator contract/output failure:** `ProviderOutputError`, including malformed JSON, empty structured output, invalid Pydantic output, inconsistent decision/finding combinations, unknown subtask IDs, and rubric-version mismatch.
- **Provider/API execution failure:** `ProviderExecutionError`, including timeout and unavailable service errors.
- **Authentication failure:** `ProviderAuthenticationError`.
- **Provider configuration failure:** existing `ProviderConfigurationError` during lazy SDK/client setup.

No application-level retry, repair orchestration, or keyword-validation fallback is implemented here. Provider failures are never converted to `reject` or `accept`.

## 6. Tracing

All three adapters reuse `TraceLogger` and the existing JSONL destination/configuration. Evaluator calls use the distinct stage `semantic_evaluation` and `kind="evaluation"`.

With tracing enabled, the shared tracer records:

- request/correlation and invocation IDs;
- provider, model, generation parameters, and structured schema;
- complete evaluator messages/payload subject to existing redaction;
- raw provider response and parsed output where available;
- validation success/failure and structured findings;
- latency, usage, and provider metadata where exposed by the SDK;
- provider exceptions and underlying causes.

Response and parsed events now receive the explicit evaluator stage, so request, response, parsed, validation, and execution-summary records can be filtered together by `semantic_evaluation` and correlation ID. Tracing remains disabled by default and does not log credentials or hidden reasoning.

## 7. Tests and verification

`tests/test_semantic_evaluator_providers.py` uses fake SDK clients and covers:

- all three providers;
- valid `accept`, `repair`, and `reject` decisions;
- nonblocking suggestions;
- complete request payload construction;
- rubric-version mismatch;
- unknown subtask IDs;
- empty and malformed structured output;
- OpenAI parse failures;
- provider timeouts and authentication failures;
- provenance;
- evaluator trace stage and correlation IDs.

Verification completed:

- focused evaluator and existing provider tests: **62 passed**;
- Ruff checks: passed;
- Ruff formatting check: passed;
- isolated `compileall`: passed;
- `git diff --check`: passed;
- provider import isolation check: passed.

## 8. Known limitations

- OpenAI `responses.parse()` may fail before returning a response object, so the original raw response is not always available. The existing tracer captures exception metadata and any SDK-attached response data when exposed.
- DeepSeek's OpenAI-compatible JSON response does not provide the same structured parsed-object surface as OpenAI; raw content is decoded and validated locally.
- Gemini's parsed/text and usage/metadata surfaces vary by SDK response. Unavailable data remains unavailable rather than being fabricated.
- The evaluator capability is implemented on concrete adapters but is not yet wired into application orchestration.
- The existing keyword semantic validator remains active until the later migration phase by explicit scope decision.

## 9. Deferred Prompt 4 work

Prompt 4 will integrate `SemanticEvaluator` into the operational decomposition path after structural validation, preserve the existing maximum of two repair attempts, feed structured findings into targeted repair, revalidate/re-evaluate repaired decompositions, and preserve final diagnostics. It will also define the application-level handling of evaluator unavailability. Transformation classification and accounting remain outside that work.
