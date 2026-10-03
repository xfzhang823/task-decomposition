# Task Decomposition

`task-decomposition` is a host-neutral Python library for decomposing operational work and evaluating a specified transformation against a reusable baseline.

## Architecture

```text
process / task
      ↓
decompose_task(...)
      ↓
TaskDecomposition
      ↓
decompose_transformation(...)
      ↓
TransformationDecompositionResult
```

Task decomposition answers “What work exists?” It produces validated operational subtasks and explicit baseline effort allocation or weights.

Transformation decomposition answers “What happens to that work under the specified transformation?” It consumes an existing `TaskDecomposition`, classifies subtasks as `RETAIN` or `REMOVE`, identifies added/support human work, and invokes deterministic canonical accounting.

`decompose(...)` is a convenience operation that composes these two capabilities. It is not a separate architecture and does not own duplicate decomposition or accounting logic.

## Repository ownership

This repository owns operational task decomposition, baseline effort allocation, transformation-specific RETAIN/REMOVE classification, added/support-work classification, deterministic transformation accounting, and provider adapters for decomposition.

This repository does not own workflow execution, workflow throughput or capacity computation, scenario orchestration, simulation, Monte Carlo, grid search, workforce planning, or alternative-scenario management. Hosts and downstream systems own those concerns.

## Task decomposition

`decompose_task(request, provider, effort_allocator=None)` accepts a `TaskDecompositionRequest` containing a task reference, task/process context, and optional explicit baseline effort and weights. It asks a `TaskDecompositionProvider` for operational subtasks, validates the untrusted response, and returns a frozen `TaskDecomposition`.

The reusable baseline invariant is central: transformation decomposition consumes an existing task decomposition and does not regenerate its subtasks or re-estimate its baseline effort.

## Transformation decomposition

`decompose_transformation(request, provider)` accepts a `TransformationDecompositionRequest` containing an existing `TaskDecomposition`, `transformation_context`, and explicit absolute or normalized accounting input. It asks a `TransformationDecompositionProvider` for RETAIN/REMOVE and added-work proposals, validates each stage, and returns a `TransformationDecompositionResult` containing the transformation facts and canonical impact.

There is no sibling application-level `account_transformation(...)` operation. The application invokes the deterministic accounting domain after transformation facts are validated; low-level accounting functions remain directly callable for deterministic use cases and tests.

## Deterministic accounting

`src/task_decomposition/domain/accounting.py` is the single mathematical authority. For baseline human work `W0`, the model is:

```text
W0 = retained_human_work + gross_removed_work
added_human_work = governance_work + operational_support_work + lifecycle_support_work
W1 = retained_human_work + added_human_work
gross_removed_work_ratio = gross_removed_work / W0
net_remaining_work_ratio = W1 / W0
net_substitution_ratio = 1 - net_remaining_work_ratio
net_augmentation_multiplier = W0 / W1
```

Gross removed work is not net substitution. Added human work reduces net substitution and can produce negative net substitution when `W1 > W0`. Effect is derived from `W0` and `W1` as `GAIN`, `NEUTRAL`, or `DEGRADATION`; ratios are not clamped.

Accounting supports normalized mode with `W0 = 1.0` and absolute mode with explicit effort unit and time basis. Support inputs use an explicit `RatioBasis`: baseline ratio, gross-removed-work ratio, already-normalized contribution, or absolute effort. Zero baseline and zero post-transformation human effort are rejected because their required ratios or multiplier are undefined.

## Providers

The provider boundary is split by capability:

```text
TaskDecompositionProvider
  → operational decomposition

TransformationDecompositionProvider
  → RETAIN / REMOVE
  → added human work

DecompositionProvider
  → composite capability for providers implementing both
```

OpenAI, Gemini, and DeepSeek adapters may implement both capabilities while sharing only narrow provider infrastructure. Provider output is untrusted: the application validates it before advancing to the next stage, and providers never calculate authoritative W0, W1, substitution, augmentation, or effect values.

The deterministic core does not require an LLM SDK. Install optional provider support with:

```bash
uv pip install -e '.[openai]'
uv pip install -e '.[gemini]'
uv pip install -e '.[deepseek]'
uv pip install -e '.[providers]'
```

Configure `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `DEEPSEEK_API_KEY`, or inject credentials through the provider-specific configuration object. Bot0 is not required to use this package.

## Minimal provider-driven usage

The concrete live example is in [`examples/openai_decompose.py`](examples/openai_decompose.py). A custom or fake provider can use the same application contracts without installing an SDK.

Task decomposition only:

```python
from task_decomposition import decompose_task

baseline = decompose_task(task_request, provider, effort_allocator=allocator)
```

Transformation decomposition from that existing baseline:

```python
from task_decomposition import decompose_transformation

impact = decompose_transformation(transformation_request, provider)
```

Full convenience composition:

```python
from task_decomposition import decompose, TaskDecompositionRequest, TaskReference
from task_decomposition.providers.openai import OpenAIDecompositionProvider

request = TaskDecompositionRequest(task=TaskReference(task_name="Review an invoice"), task_context={"domain": "accounts_payable"})
result = decompose(request, OpenAIDecompositionProvider(), transformation_context={"goal": "Draft invoice checks while retaining approval"}, accounting_input=accounting_input)
```

The example assumes `accounting_input` is an explicit `AbsoluteEffortInput` or `NormalizedAccountingInput`; providers may not invent authoritative effort or final metrics.

## Validation and testing

Pydantic contracts enforce field and value constraints. Stage validation enforces identity, cardinality, dependency, and effort invariants. Semantic validation rejects non-operational or meta-only provider output. Deterministic accounting then validates and computes the canonical impact.

Hard validity is machine-checkable: schemas, identities, dependencies, allocations, accounting reconciliation, and derived identities must hold. Semantic quality is a separate human-review concern covering completeness, overlap, granularity, effort plausibility, transformation plausibility, and support-work plausibility.

The `benchmarks/` corpus and review helpers support credential-free framework tests and opt-in live review. Ordinary tests do not require network access or provider credentials. S4B-2 did not execute live providers because no provider keys were configured, so live semantic quality remains deferred to manual evaluation.

Run the normal checks with:

```bash
pytest
ruff check src tests
ruff format --check src tests
python -m compileall -q src
git diff --check
```

## Further documentation

- [`docs/DECOMPOSITION_MODEL.md`](docs/DECOMPOSITION_MODEL.md) explains the two capabilities and their contracts.
- [`docs/ACCOUNTING_MODEL.md`](docs/ACCOUNTING_MODEL.md) explains quantities, equations, modes, units, ranges, and edge behavior.
- [`AGENTS.md`](AGENTS.md) gives concise maintenance rules for coding agents.
