# Semantic Evaluation Orchestration Migration

Status: Prompt 4 implementation, verified and cleaned up in Prompt 5.

## 1. Final execution path

Operational decomposition now follows:

```text
generate operational decomposition
  -> provider envelope validation
  -> deterministic structural validation
  -> SemanticEvaluator evaluation of the complete decomposition
       -> accept: baseline allocation -> TaskDecomposition
       -> repair: targeted provider repair -> structural validation -> re-evaluation
       -> reject: semantic failure
```

Only an accepted, structurally valid decomposition reaches baseline effort allocation. Repair is bounded to two attempts.

## 2. Application ownership and evaluator resolution

`application/task_decomposition.py` owns evaluator placement, decision handling, repair feedback, and re-evaluation. `decompose_task(..., evaluator=None)` accepts narrow explicit evaluator injection. When omitted, the application uses the provider's callable `evaluate()` capability. This activates the existing OpenAI, DeepSeek, and Gemini implementations by default. A custom task provider without `evaluate()` must receive an explicit evaluator and otherwise raises `SemanticEvaluatorUnavailableError`.

The `TaskDecompositionProvider` protocol remains unchanged; custom providers are not required to implement evaluator behavior.

## 3. Removed keyword-validation paths

Operational validation no longer invokes lexical semantic checks. The operational verb allowlist, abstract-label patterns, and operational semantic-error function were removed. Consequently, planning, scheduling, drafting, analysis, decision-making, and similar cognitive work are not rejected by a keyword gate. The remaining forbidden-language assertion is used only by the pre-existing transformation classification stages and is outside operational evaluation.

## 4. Structural validation boundaries

`validate_operational_decomposition` still validates the Pydantic contract, task/subtask identity, unique IDs, contiguous sequence indexes, dependency references, self-dependencies, duplicate dependencies, dependency precedence, and provider envelope/provenance. Structural failures map to `ProviderContractValidationError` and prevent evaluator invocation. Repaired responses pass through the same validation before re-evaluation.

## 5. Repair and re-evaluation state transitions

Evaluator findings are formatted with their code, severity, affected subtask ID, and message and passed to the existing provider repair hook. A repair decision with no repair hook fails explicitly. Each repaired response is envelope-validated, structurally validated, and evaluated as a complete decomposition. Acceptance returns the repaired response; rejection terminates without another repair. A second repair decision after the second attempt raises semantic failure with the final findings.

## 6. Error mapping

- Structural output failure: `ProviderContractValidationError`.
- Valid evaluator `reject`: `ProviderSemanticValidationError` with structured findings.
- Repair unavailable or exhausted: `ProviderSemanticValidationError` with final findings and attempt metadata.
- Malformed injected evaluator output, inconsistent decision/findings, wrong rubric version, or unknown finding subtask: `SemanticEvaluatorContractError`.
- Evaluator transport/API exception: `ProviderExecutionError` (or the provider's existing typed provider error).
- Missing evaluator capability: `SemanticEvaluatorUnavailableError`.

Evaluator exceptions are never converted into semantic decisions.

## 7. Public API

`decompose_task` gained one optional keyword-only `evaluator` parameter. Existing signatures and the convenience `decompose_task -> decompose_transformation` composition remain otherwise unchanged. No evaluator method was added to `TaskDecompositionProvider`.

## 8. Tracing

The existing opt-in JSONL tracer and request correlation ID are reused. Structural validation, evaluator decisions/findings (`semantic_evaluation`), repair requests/outputs, repaired structural validation, and final execution summary are recorded through the existing tracer. Provider adapters continue to record their evaluator request/response details; credentials and hidden reasoning are not logged.

## 9. Tests and verification

Provider evaluator integration tests remain credential-free and exercise structured accept/repair/reject and provider error boundaries. Application-focused tests cover evaluator resolution, acceptance, suggestions, repair/re-evaluation, bounded repair, rejection, unavailable capabilities, malformed evaluator results, transport failures, and structural failures. The full prescribed verification is `pytest`, Ruff check/format, compile/import checks, and `git diff --check`.

## 10. Prompt 5 completion

Prompt 5 removed the remaining active forbidden-language gate from transformation classification, deleted the obsolete semantic-validation module, migrated repository fixtures/tests to evaluator-driven decisions, and updated current API documentation. Historical audit documents retain their pre-migration findings for traceability. Transformation accounting and effort semantics remain unchanged.
