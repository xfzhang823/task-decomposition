# Semantic Evaluator Contracts and Rubric

**Status:** Prompt 2 implementation. This document covers contracts, the provider-neutral rubric, and foundational tests only. Provider calls and application orchestration are deferred to Prompt 3 and later.

## 1. Implemented scope

The new `task_decomposition.evaluation` package defines the boundary between a complete, structurally valid operational decomposition and a future LLM semantic evaluator. It does not call an SDK, change generation or repair behavior, invoke the evaluator from the application, or alter the existing keyword validator in this phase.

The package contains:

- `contracts.py`: Pydantic request, finding, decision, severity, category, code, and optional provenance contracts.
- `rubric.py`: versioned provider-neutral evaluation guidance.
- `ports.py`: the provider-independent synchronous `SemanticEvaluator` protocol.
- `__init__.py`: focused package exports.

The later migration will remove keyword-based semantic acceptance and rejection entirely. The new rubric deliberately does not reproduce an operational-verb allowlist, abstract-label regexes, forbidden-phrase matching, or a numerical quality score.

## 2. Contracts

### `SemanticEvaluationRequest`

`SemanticEvaluationRequest` includes:

- `task: TaskReference`, reusing the existing task identity and description contract;
- `task_context: dict[str, str]` for relevant host-provided context;
- `operational_decomposition: OperationalDecomposition`, reusing the complete domain model;
- `rubric_version`;
- optional `request_id` and `correlation_id` for later tracing and repair linkage.

The request is frozen and rejects unknown fields, consistent with existing contracts. It contains the complete decomposition rather than an isolated subtask so evaluation can consider coverage, overlap, and granularity in context.

### `SemanticFinding`

Each finding contains:

- optional `subtask_id`; `None` represents a decomposition-level finding;
- stable `SemanticFindingCode`;
- `SemanticFindingCategory`: `abstraction`, `outcome`, `overlap`, `granularity`, `completeness`, or `policy`;
- `SemanticFindingSeverity`: `suggestion`, `repairable`, or `blocking`;
- concise actionable `message`;
- optional `evidence` reference such as a subtask field path.

The contract contains no hidden reasoning, chain-of-thought field, arbitrary quality score, or provider SDK type.

### `SemanticEvaluation`

The result contains:

- `decision`: `accept`, `repair`, or `reject`;
- zero or more structured findings;
- the `rubric_version` used;
- optional transport-neutral `SemanticEvaluatorProvenance` with provider, model, request, and correlation identifiers.

The result is frozen and rejects unknown fields. Provider adapters can populate provenance later without making this package depend on an SDK response object.

## 3. Decision and finding consistency

The Pydantic model enforces these deterministic contract rules:

| Decision | Required/allowed findings |
| --- | --- |
| `accept` | Suggestions are allowed; `repairable` and `blocking` findings are invalid. |
| `repair` | At least one `repairable` finding is required; `blocking` findings are invalid. Suggestions may accompany it. |
| `reject` | At least one `blocking` finding is required. Suggestions or additional findings may accompany it. |

Suggestions alone never require repair. A broad but valid subtask is not rejected merely because it could be decomposed further; the evaluator must identify a material defect to return `repair` or `reject`.

The consistency validator checks the shape and decision/finding relationship. It does not assign a score or make the semantic judgment itself.

## 4. Stable finding codes

The initial deliberately small code set is:

| Code | Intended use |
| --- | --- |
| `insufficient_operational_specificity` | A label does not make the meaningful work understandable in context. |
| `outcome_not_work` | A state, result, or outcome is presented without the work that produces or records it. |
| `overlapping_subtasks` | Two or more subtasks materially duplicate the same work. |
| `inappropriate_granularity` | A subtask is materially too broad, fragmented, or otherwise unreasonable for the task context. |
| `incomplete_coverage` | The decomposition misses a material part of the original task. |
| `internal_meta_task` | Internal decomposition, rationale, or evaluator activity is incorrectly presented as business work. |
| `clarify_work_description` | Optional nonblocking improvement to make valid work clearer. |

Codes are enums so provider structured-output adapters and future tracing can depend on stable serialized values. Categories and severities are also enums for the same reason.

## 5. Rubric

`SEMANTIC_EVALUATION_RUBRIC_VERSION` is currently `"1.0"`. `SEMANTIC_EVALUATION_RUBRIC` is a provider-neutral prose rubric intended to be embedded into a future provider prompt or otherwise supplied to an evaluator adapter.

The rubric requires contextual evaluation of the complete decomposition. It recognizes physical work, system interaction, communication, information processing, planning, scheduling, drafting, outlining, research, analysis, evaluation, judgment, decision-making, and deliverable creation as legitimate work when the work is meaningful and appropriately scoped.

It asks the evaluator to distinguish:

- work from goals, states, and outcomes;
- material defects from optional clarity improvements;
- overlap and missing coverage from merely related subtasks;
- unreasonable fragmentation from a valid broad unit of work;
- business work from internal decomposition or meta-analysis.

The examples cover production scheduling, invoice review and approval decisions, customer onboarding, pure outcomes, internal meta-tasks, overlapping work, and missing work. They are guidance for contextual judgment, not lexical acceptance or rejection rules.

## 6. Evaluator protocol and ownership

`SemanticEvaluator` in `evaluation/ports.py` is a synchronous runtime-checkable protocol:

```python
evaluate(request: SemanticEvaluationRequest) -> SemanticEvaluation
```

It is intentionally separate from `TaskDecompositionProvider`. Existing providers are not required to implement it in Prompt 2, and no provider registry or adapter is introduced here. Prompt 3 will reuse the existing OpenAI, DeepSeek, and Gemini structured-output infrastructure behind this interface.

Responsibilities are separated as follows:

- deterministic validation owns schema, required fields, IDs, sequence/order, dependencies, stage identity, and accounting invariants;
- the evaluator owns contextual operational-semantic judgment for the complete operational decomposition;
- providers own SDK transport and structured-output parsing;
- application orchestration will own evaluation placement, targeted repair, and bounded re-evaluation.

Transformation classification, transformation decomposition, and accounting remain outside this initiative.

## 7. Error semantics

A valid semantic rejection is a well-formed `SemanticEvaluation` with `decision="reject"` and at least one `blocking` finding. It is not an exception caused by the evaluator transport.

An invalid evaluator response—such as malformed JSON, a schema violation, an unknown field, or an inconsistent decision/finding combination—must fail at the contract boundary with a Pydantic validation error. It must not be converted into a semantic `reject` result.

A provider/API execution failure—such as a timeout, authentication error, or unavailable evaluator—will remain a provider/application execution error in the later integration. It is not represented by `SemanticEvaluation` and is not converted into `reject`.

Prompt 2 intentionally does not define transport retries, provider exception mapping, or application fallback behavior. The approved architecture requires explicit evaluator-unavailability errors and no fallback to keyword validation once migration is integrated.

## 8. Structured-output compatibility

The contracts use Pydantic models, string-valued enums, tuples/lists that serialize as JSON arrays, optional scalar fields, and no SDK-specific types. This is suitable for the existing structured-output approaches used by OpenAI, DeepSeek, and Gemini.

Provider adapters must validate parsed evaluator output against `SemanticEvaluation` before application code trusts it. They must preserve the rubric version and findings as structured data. Raw provider metadata and tracing remain adapter concerns and are deferred to Prompt 3.

## 9. Tests

`tests/test_evaluation_contracts.py` covers:

- request and response JSON serialization round trips;
- all decisions and severities;
- invalid decision/finding combinations;
- subtask-specific and decomposition-level findings;
- stable code and category values;
- rubric version and representative examples;
- distinction between provider failure and semantic rejection;
- package import without loading OpenAI or Gemini SDK modules.

The rubric tests verify that the intended guidance is present. They do not claim to prove an LLM's contextual judgment without a live model call. Existing operational-validation tests are unchanged.

## 10. Deferred Prompt 3 work

Prompt 3 should add only provider integration and its deterministic mocked tests:

1. Implement provider-backed `SemanticEvaluator` capabilities using existing adapter abstractions.
2. Add structured evaluator prompts that incorporate the versioned rubric without introducing keyword heuristics.
3. Preserve provider SDK isolation and validate every parsed response with these contracts.
4. Capture evaluator request/response metadata through the existing shared tracer.
5. Define provider-specific execution/parse error mapping while keeping it distinct from semantic rejection.

Application orchestration, repair integration, removal of the old runtime keyword validator, and re-evaluation remain deferred to later prompts.
