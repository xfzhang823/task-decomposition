# Semantic evaluation

This is the current reference for semantic evaluation in `task-transmorph`. Historical phase reports remain under `docs/semantic-evaluation/` and are not current API guidance.

## Responsibilities

There are two distinct evaluation stages:

1. **Task decomposition evaluation** evaluates the complete baseline operational decomposition against the original task. It may identify missing or poorly defined baseline activities, task-boundary problems, dependency issues, and implausible effort or occurrence assumptions. Accepted results proceed to deterministic baseline allocation; repair remains bounded by the existing application policy.
2. **Transformation evaluation** evaluates one completed transformation against the frozen baseline, original task reference, and parent-output contract. It checks retained human responsibility completeness, semantic double counting, task-boundary preservation, active human-effort semantics, and transformed occurrence assumptions. It does not redesign the baseline, recommend additional automation, or recalculate W0/W1.

Both stages use the provider-neutral `SemanticEvaluationRequest`/`SemanticEvaluation` contracts, shared provider adapters, structured-output parsing, provenance, tracing, and decision/severity invariants. The transformation request is evaluated once after deterministic accounting succeeds; it is diagnostic-only and does not automatically repair or mutate the transformation result.

## Routing and models

`decompose_task` resolves the baseline evaluator through the selected provider's existing `evaluate()` capability or an explicitly injected evaluator. `decompose_transformation` uses the same provider interface after transformation accounting. No separate evaluator framework or provider implementation is used.

For OpenAI, `OpenAIProviderConfig.model` controls generation and baseline evaluation. `transformation_evaluator_model` is an optional dedicated model override. If the provider model remains its default, transformation evaluation resolves to `gpt-6-luna`; an explicit run-scoped model or dedicated configuration override remains supported. Gemini and DeepSeek continue to use their existing provider configuration and adapter paths.

## Rubrics and findings

The current rubric versions are exposed by `task_transmorph.evaluation.rubric`: baseline semantic evaluation uses `SEMANTIC_EVALUATION_RUBRIC_VERSION`, and transformation evaluation uses `TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION`. Findings are structured with criterion, severity, rationale/evidence, and affected references where supplied by the artifact. Provider adapters validate the structured result before application code trusts it.

Transformation findings must be concrete and evidence-grounded. The evaluator must distinguish reviewing, deciding, authorizing, communicating, and executing; avoid inventing responsibilities outside the parent-output contract; and accept reasonable model-generated occurrence assumptions without requiring empirical measurements. A decision must be consistent with finding severities under the existing `SemanticEvaluation` contract.

## Deterministic boundary

Pydantic contracts, identity, dependency, ordering, provider-output, accounting, and W0/W1 calculations remain deterministic application/domain responsibilities. Providers propose semantic judgments; they do not provide authoritative accounting metrics. Semantic evaluation does not recalculate accounting or replace deterministic validators.

## Verification

Credential-free tests cover contracts, provider adapters with mocks, orchestration, model routing, transformation replay, import isolation, and deterministic accounting. Live provider benchmarks remain explicitly opt-in. The release verification record should report the current test result and should not reuse counts or file inventories from historical phase reports.
