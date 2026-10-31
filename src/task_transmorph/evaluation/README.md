# Evaluation

Provider-neutral schemas and rubric text for semantic evaluation. This package defines *what an evaluation request contains*, *what a decision plus findings look like*, and *the guidance an evaluator is judged against*. It contains no evaluator implementation, no prompts, no transport, and no LLM calls.

Dependency direction: `evaluation/` → `contracts/` (stage and accounting models it snapshots) and `pydantic`. It is imported by `interfaces/`, `application/`, `providers/`, and the top-level package; it imports none of them. `contracts/` deliberately does not import it — `TransformationDecompositionResult.semantic_evaluation` is typed `Any` to keep that edge absent.

The behavioral interface lives next door: `interfaces/semantic_evaluator.py` declares the `SemanticEvaluator` protocol over these types. Providers implement it; the application invokes it.

## Module overview

There are two evaluation checkpoints, and they share one vocabulary:

1. **Baseline evaluation** runs after structural validation of an operational decomposition and before deterministic allocation. It may accept, request targeted repair, or reject the decomposition.
2. **Transformation evaluation** runs once after deterministic accounting succeeds. It is diagnostic-only: it never repairs, mutates, or recalculates the transformation result.

Both checkpoints return the same `SemanticEvaluation` result; only the request payloads differ. The transformation request carries the whole frozen chain plus the computed accounting impact; its rubric focuses on cross-stage consistency instead of baseline quality.

What lives here:

- `contracts.py` — five Pydantic models and five stable enums.
- `rubric.py` — two versioned, provider-neutral rubric texts.

What does not live here:

- The `SemanticEvaluator` protocol (`interfaces/`), provider prompts (`providers/prompts.py`), structured-output parsing (`providers/_semantic.py`), retry/repair policy, tracing, and decision enforcement (`application/`).

## Directory structure

```text
 evaluation/
 ├── __init__.py   re-exports 14 names (four rubric constants, ten classes/enums)
 ├── contracts.py  request/result models and stable finding enums
 └── rubric.py     versioned baseline and transformation rubric text
```

There are no subpackages. `contracts.py` depends only on `task_transmorph.contracts`; `rubric.py` depends on nothing.

## Core interfaces/types

### Requests

**`SemanticEvaluationRequest`** — the complete baseline decomposition presented to the evaluator:

- `task`, `task_context`, `operational_decomposition`;
- `rubric_version` (required), `request_id`, `correlation_id`.

**`TransformationSemanticEvaluationRequest`** — the complete frozen transformation:

- `task`, `transformation_context`, `parent_output_contract`;
- `task_decomposition`, `retain_remove_classification`, `agentic_task_synthesis`, `human_agent_activity_modeling`, `activity_effort_estimation`, `accounting`;
- `rubric_version`, `request_id`, `correlation_id`.

Both are frozen and forbid unknown fields, so an evaluator cannot receive a silently mislabeled artifact.

### Results

**`SemanticEvaluation`** — `decision`, `findings`, `rubric_version`, `evaluator_provenance`. A model validator enforces the decision/severity relationship at construction time:

- `ACCEPT` — suggestions only; any repairable or blocking finding is invalid.
- `REPAIR` — at least one repairable finding, and no blocking finding.
- `REJECT` — at least one blocking finding.

**`SemanticFinding`** — `subtask_id` (optional; `None` means a decomposition-level finding), `code`, `category`, `severity`, `message`, optional `evidence`, optional `criterion`, and `affected_references` (defaults to empty).

**`SemanticEvaluatorProvenance`** — `provider_id`, optional `model_id`, `request_id`, `correlation_id`. Transport-neutral by design; adapters populate it after parsing.

### Enums

- `SemanticEvaluationDecision` — `accept`, `repair`, `reject`.
- `SemanticFindingSeverity` — `suggestion`, `repairable`, `blocking`.
- `SemanticFindingCategory` — `abstraction`, `outcome`, `overlap`, `granularity`, `completeness`, `policy`.
- `SemanticFindingCode` — seven stable machine-readable codes (`insufficient_operational_specificity`, `outcome_not_work`, `overlapping_subtasks`, `inappropriate_granularity`, `incomplete_coverage`, `internal_meta_task`, `clarify_work_description`).
- `TransformationSemanticCriterion` — `human_responsibility_completeness`, `double_counting`, `task_boundary`, `active_human_effort`, `occurrence_assumptions`.

Enum values are lower-case snake case; pass the value (`"task_boundary"`) or the enum member. The model accepts either, but not the member *name* in upper case.

## Rubrics

`rubric.py` owns two plain strings and their versions:

- `SEMANTIC_EVALUATION_RUBRIC` — version `1.3`. Baseline scope, coverage, effort plausibility, severity and decision boundaries.
- `TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC` — version `1.1`. Cross-stage scope, responsibility reconciliation, and the five transformation criteria.

The transformation rubric weights the criteria as high/high/high/medium/medium for responsibility completeness, double counting, task boundary, active human effort, and occurrence assumptions respectively.

These constants are the single source of rubric text. `providers/prompts.py` interpolates them into the evaluator prompts, so the module itself contains no prompt scaffolding and no provider-specific wording.

## Usage examples

### Evaluate a baseline decomposition

```python
from task_transmorph.contracts import (
    OperationalDecomposition,
    OperationalSubtask,
    TaskReference,
)
from task_transmorph.evaluation import (
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
    SemanticEvaluation,
    SemanticEvaluationDecision,
    SemanticEvaluationRequest,
    SemanticFinding,
    SemanticFindingCategory,
    SemanticFindingCode,
    SemanticFindingSeverity,
)

task = TaskReference(task_name="Review an invoice")
decomposition = OperationalDecomposition(
    task=task,
    operational_subtasks=(
        OperationalSubtask(
            sequence_index=1,
            subtask_id="review",
            subtask_name="Review invoice against purchase order",
            effort_rationale="Once per invoice; matching records requires focused review.",
        ),
    ),
)

request = SemanticEvaluationRequest(
    task=task,
    task_context={"department": "accounts payable"},
    operational_decomposition=decomposition,
    rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
    request_id="request-1",
)

result = SemanticEvaluation(
    decision=SemanticEvaluationDecision.ACCEPT,
    findings=(
        SemanticFinding(
            subtask_id="review",
            code=SemanticFindingCode.INCOMPLETE_COVERAGE,
            category=SemanticFindingCategory.COMPLETENESS,
            severity=SemanticFindingSeverity.SUGGESTION,
            message="Consider naming the matched document.",
            evidence="operational_subtasks[0]",
        ),
    ),
    rubric_version=request.rubric_version,
)

assert result.decision is SemanticEvaluationDecision.ACCEPT
assert result.rubric_version == SEMANTIC_EVALUATION_RUBRIC_VERSION
```

### A transformation finding names its criterion

```python
from task_transmorph.evaluation import (
    TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
    SemanticEvaluation,
    SemanticFinding,
    SemanticFindingCategory,
    SemanticFindingCode,
    SemanticFindingSeverity,
    TransformationSemanticCriterion,
)

finding = SemanticFinding(
    subtask_id="review",
    code=SemanticFindingCode.INCOMPLETE_COVERAGE,
    category=SemanticFindingCategory.COMPLETENESS,
    severity=SemanticFindingSeverity.BLOCKING,
    message="Approval responsibility is not represented in W1.",
    evidence="human_agent_activity_modeling.activities",
    criterion=TransformationSemanticCriterion.HUMAN_RESPONSIBILITY_COMPLETENESS,
    affected_references=("review",),
)

result = SemanticEvaluation(
    decision="reject",
    findings=(finding,),
    rubric_version=TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
)

assert result.findings[0].criterion.value == "human_responsibility_completeness"
```

### Invalid decision/severity combinations fail at construction

```python
from pydantic import ValidationError

from task_transmorph.evaluation import SemanticEvaluation, SemanticFinding


def finding(severity: str) -> SemanticFinding:
    return SemanticFinding(
        code="incomplete_coverage",
        category="completeness",
        severity=severity,
        message="Example finding.",
    )


for decision, severity in (
    ("accept", "repairable"),
    ("repair", "suggestion"),
    ("reject", "repairable"),
):
    try:
        SemanticEvaluation(
            decision=decision, findings=(finding(severity),), rubric_version="1.3"
        )
    except ValidationError:
        pass
    else:
        raise AssertionError(f"{decision} + {severity} should be invalid")
```

## Dependency relationships

```text
                 contracts/ (stages, accounting)
                          ▲
                          │
                     evaluation/          ← contracts + pydantic only
             ┌────────────┼──────────────┬────────────────┐
             │            │              │                │
        interfaces    application    providers      task_transmorph
     SemanticEvaluator  _semantic_   _semantic.py,   (public exports)
                        evaluation.py  prompts.py
```

- `interfaces/semantic_evaluator.py` — the runtime-checkable `SemanticEvaluator` protocol over `SemanticEvaluationRequest | TransformationSemanticEvaluationRequest` → `SemanticEvaluation`.
- `application/_semantic_evaluation.py` — shared invocation: calls `evaluate()`, converts unexpected exceptions to `ProviderExecutionError`, validates the returned contract and rubric version, and emits tracing.
- `application/task_decomposition.py` — resolves the evaluator (injected, else the provider's `evaluate()`), builds baseline requests, and enforces accept/repair/reject policy.
- `application/transformation_decomposition.py` — builds the transformation request after accounting and runs one diagnostic pass.
- `providers/_semantic.py` — serializes requests, parses structured output, stamps provenance, and additionally enforces referenced-subtask identity and, for transformation requests, that every finding carries a criterion plus evidence and affected references.

Boundary notes:

- The contract models enforce decision/severity consistency. They do not check rubric-version equality or referenced IDs — those are adapter/application responsibilities.
- Transformation evaluation never feeds back into the result: it cannot repair the baseline, change classifications, or alter W0/W1.

The package exposes 14 names. Ten are re-exported by `task_transmorph`; `SEMANTIC_EVALUATION_RUBRIC`, `SEMANTIC_EVALUATION_RUBRIC_VERSION`, `SemanticEvaluationRequest`, and `SemanticEvaluatorProvenance` are available only from `task_transmorph.evaluation`.

## Verification

Credential-free tests cover the contracts, rubric content, provider adapters with mocks, and orchestration:

- `tests/test_evaluation_contracts.py` — round-trips, decision/severity matrix, finding references, enum stability, rubric phrases.
- `tests/test_semantic_evaluator_providers.py` — adapter parsing, provenance, rubric-version and subtask-identity rejection.
- `tests/test_transformation_semantic_evaluation.py` — transformation request assembly, criteria, and diagnostic-only behavior.
- `tests/test_effort_estimation.py` — evaluator injection in the baseline flow.

Live provider benchmarks stay explicitly opt-in; the ordinary suite must not require credentials.

## Changing this module

1. Treat the enums, request fields, and `SemanticEvaluation` invariants as public contract. Changing them affects providers, application policy, and external consumers.
2. Rubric text is behavior. Bump the corresponding `*_VERSION` when guidance changes materially, and update the representative-phrase tests.
3. Keep the package provider-neutral: no SDK imports, no prompt scaffolding, no network, no filesystem.
4. New finding codes or criteria must be added to the enums and to the rubric that uses them; do not add free-form strings as a shortcut.
5. If a public name is added or removed, update `evaluation/__init__.py` and check whether the top-level `task_transmorph` surface should change too.
6. Run `pytest`, `ruff check src tests`, `ruff format --check src tests`, and `python -m compileall -q src`. Review `docs/invariants/registry.yaml` and `docs/reference/SEMANTIC_EVALUATION.md` when semantics move.
