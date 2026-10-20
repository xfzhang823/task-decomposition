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

The supported application entry points are:

- `decompose_task(request, provider, *, effort_allocator=None, evaluator=None)` for creating a reusable baseline.
- `decompose_transformation(request, provider)` for evaluating a transformation against an existing baseline.
- `decompose(request, provider, *, transformation_context, accounting_input)` for the complete two-step composition.

Added-work estimation supports `AI_INTERACTION` and `AI_VERIFICATION` rows with explicit causal REMOVE-subtask references and reference-class estimates. Baseline references are normalized by their estimated occurrences per parent execution; external references require a compatible quantitative per-occurrence anchor. Support selection defaults to host inputs and can be switched to `estimate` or `auto` through `SupportWorkMode`; canonical accounting remains deterministic and provider-independent.

## Repository ownership

This repository owns operational task decomposition, baseline effort allocation, transformation-specific RETAIN/REMOVE classification, added/support-work classification, deterministic transformation accounting, and provider adapters for decomposition.

This repository does not own workflow execution, workflow throughput or capacity computation, scenario orchestration, simulation, Monte Carlo, grid search, workforce planning, or alternative-scenario management. Hosts and downstream systems own those concerns.

## Task decomposition

`decompose_task(request, provider, *, effort_allocator=None, evaluator=None)` accepts a `TaskDecompositionRequest` containing a `TaskReference`, optional task context, and optional baseline effort or effort weights. It asks a `TaskDecompositionProvider` for operational subtasks, validates the untrusted response, and returns a frozen `TaskDecomposition`.

The reusable baseline invariant is central: transformation decomposition consumes an existing task decomposition and does not regenerate its subtasks or re-estimate its baseline effort.

## Transformation decomposition

`decompose_transformation(request, provider)` accepts a `TransformationDecompositionRequest` containing an existing `TaskDecomposition`, `transformation_context`, explicit `AbsoluteEffortInput` or `NormalizedAccountingInput`, and a `SupportWorkMode`. It asks a `TransformationDecompositionProvider` for RETAIN/REMOVE and added-work proposals, validates each stage, and returns a `TransformationDecompositionResult` containing the transformation facts and canonical impact.

Every added-work row must identify one or more original subtasks in `source_removed_subtask_ids`; each source must exist and be classified `REMOVE`. This causal attribution explains why the added work exists and is independent of the reference used to estimate its effort. The reference may be a `RETAIN` or `REMOVE` baseline subtask, or an external analogous workflow. Python validates the references and computes the estimate; providers do not provide authoritative accounting amounts. A valid transformation may contain no added-work rows.

There is no sibling application-level `account_transformation(...)` operation. The application invokes the deterministic accounting domain after transformation facts are validated; low-level accounting functions remain directly callable for deterministic use cases and tests.

## Deterministic accounting

`src/task_decomposition/domain/accounting.py` is the single mathematical authority. For baseline human work `W0`, the model is:

```text
W0 = retained_human_work + gross_removed_work
added_human_work = ai_interaction_work + ai_verification_work
W1 = retained_human_work + added_human_work
gross_removed_work_ratio = gross_removed_work / W0
net_remaining_work_ratio = W1 / W0
net_substitution_ratio = 1 - net_remaining_work_ratio
net_augmentation_multiplier = W0 / W1
```

Gross removed work is not net substitution. Added human work reduces net substitution and can produce negative net substitution when `W1 > W0`. Effect is derived from `W0` and `W1` as `GAIN`, `NEUTRAL`, or `DEGRADATION`; ratios are not clamped.

Accounting supports normalized mode with `W0 = 1.0` and absolute mode with explicit effort unit and time basis. Support inputs use an explicit `RatioBasis`: baseline ratio, gross-removed-work ratio, already-normalized contribution, or absolute effort. Zero baseline and zero post-transformation human effort are rejected because their required ratios or multiplier are undefined.

## Providers

The provider boundary is split by capability. Behavioral protocols live under `task_decomposition.interfaces`; data schemas live under `task_decomposition.contracts`:

```text
TaskDecompositionProvider
  → operational decomposition

TransformationDecompositionProvider
  → RETAIN / REMOVE
  → added human work

DecompositionProvider
  → composite capability for providers implementing both
```

OpenAI, Gemini, and DeepSeek adapters may implement both capabilities while sharing only narrow provider infrastructure. Provider output is untrusted: the application validates it before advancing to the next stage, and providers never calculate authoritative W0, W1, substitution, augmentation, or effect values. Import protocols from `task_decomposition.interfaces`, for example `from task_decomposition.interfaces import DecompositionProvider`.

Install the library and add provider-specific dependencies as needed:

```bash
uv pip install -e .
uv pip install -e '.[openai]'
uv pip install -e '.[gemini]'
uv pip install -e '.[deepseek]'
uv pip install -e '.[providers]'
```

The deterministic contracts and accounting functions are available without invoking an LLM. Configure `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `DEEPSEEK_API_KEY`, or inject credentials through the provider-specific configuration object. Bot0 is not required to use this package.

## Minimal provider-driven usage

The concrete live example is in [`examples/openai_decompose.py`](examples/openai_decompose.py). A custom or fake provider can use the same application contracts without installing an SDK.

Task decomposition only:

```python
from task_decomposition import (
    EffortQuantity,
    EffortUnit,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    decompose_task,
)
from task_decomposition.providers.openai import OpenAIDecompositionProvider

request = TaskDecompositionRequest(
    task=TaskReference(
        task_name="Review an invoice",
        task_description="Validate and approve an invoice.",
    ),
    baseline_effort=EffortQuantity(
        value=8,
        unit=EffortUnit.HOURS,
        time_basis=TimeBasis.PER_OPERATION,
    ),
)
baseline = decompose_task(request, OpenAIDecompositionProvider())
```

Transformation decomposition from that existing baseline:

```python
from task_decomposition import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    SupportWorkMode,
    TimeBasis,
    TransformationDecompositionRequest,
    decompose_transformation,
)
from task_decomposition.providers.openai import OpenAIDecompositionProvider

accounting_input = AbsoluteEffortInput(
    baseline_human_effort=EffortQuantity(
        value=8, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
    ),
    retained_human_work=EffortQuantity(
        value=4, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
    ),
    gross_removed_work=EffortQuantity(
        value=4, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
    ),
)
transformation_request = TransformationDecompositionRequest(
    task_decomposition=baseline,
    transformation_context={"goal": "Draft invoice checks while retaining approval"},
    accounting_input=accounting_input,
    support_work_mode=SupportWorkMode.ESTIMATE,
)
impact = decompose_transformation(
    transformation_request,
    OpenAIDecompositionProvider(),
)
```

Full convenience composition:

```python
from task_decomposition import (
    AbsoluteEffortInput,
    EffortQuantity,
    EffortUnit,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    decompose,
)
from task_decomposition.providers.openai import OpenAIDecompositionProvider

request = TaskDecompositionRequest(
    task=TaskReference(task_name="Review an invoice"),
    task_context={"domain": "accounts_payable"},
    baseline_effort=EffortQuantity(
        value=8, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
    ),
)
result = decompose(
    request,
    OpenAIDecompositionProvider(),
    transformation_context={"goal": "Draft invoice checks while retaining approval"},
    accounting_input=AbsoluteEffortInput(
        baseline_human_effort=EffortQuantity(
            value=8, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
        ),
        retained_human_work=EffortQuantity(
            value=4, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
        ),
        gross_removed_work=EffortQuantity(
            value=4, unit=EffortUnit.HOURS, time_basis=TimeBasis.PER_OPERATION
        ),
    ),
)
```

The absolute accounting values must reconcile with the provider's RETAIN/REMOVE classification. Use `NormalizedAccountingInput` when the host supplies baseline-relative values instead. The examples require an OpenAI API key; replace `OpenAIDecompositionProvider` with any implementation of the appropriate protocol for another provider or a credential-free test double.

### Support-work selection

`TransformationDecompositionRequest.support_work_mode` defaults to `SupportWorkMode.HOST`:

- `HOST` uses `accounting_input.support_work`, including explicit zero values, and fails if host support is absent.
- `ESTIMATE` derives `AI_INTERACTION` and `AI_VERIFICATION` support from validated `AddedWorkEstimate` rows and fails if an estimate is missing or noncomputable.
- `AUTO` uses explicit host support when present; otherwise it derives estimates. When both are available, the result includes reconciliation diagnostics and does not silently mix the values.

Reference-class estimates preserve low/typical/high ranges as metadata; typical values drive canonical support inputs. Baseline references are normalized by their reference occurrence frequency. External references need a compatible quantitative per-occurrence effort anchor. See [`docs/reference/ACCOUNTING_MODEL.md`](docs/reference/ACCOUNTING_MODEL.md) for effort units, bases, and equations.

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

## Opt-in LLM tracing

Provider tracing is disabled by default. To capture a redacted, machine-readable
JSONL lifecycle trace for the OpenAI example:

```bash
TASK_DECOMPOSITION_TRACE_ENABLED=true \
TASK_DECOMPOSITION_TRACE_CONSOLE=true \
python examples/openai_decompose.py \
  --task-name "Review an invoice" \
  --task-description "Validate the invoice and approve or reject it."
```

The detailed trace is written to a timestamped file such as
`logs/llm/task_decomposition_2026-10-09_143012.jsonl`; each
line is one event linked by the execution-level `correlation_id`. Console output
is a concise event summary. Tracing includes full prompts and structured responses,
which may contain sensitive business data. API keys, authorization values, and
common provider key formats are redacted, but the `logs/` directory must still
be protected. Set `TASK_DECOMPOSITION_TRACE_DIR` to override the directory;
relative overrides resolve from the repository root.
Each execution keeps its lifecycle in one file; if two executions start in the
same second, the later file receives a short unique suffix.

Useful filters include:

```bash
TRACE_FILE=$(ls -t logs/llm/task_decomposition_*.jsonl | head -1)
jq -c 'select(.correlation_id == "REQUEST_ID")' "$TRACE_FILE"
jq -c 'select(.stage == "retain_remove_classification" or .event == "llm.exception")' "$TRACE_FILE"
```

You can ask Codex: “Inspect the latest logs under `logs/llm/`, identify the
failed stage, examine the request and response events, and explain the root
cause.”

Provider SDK limitation: successful OpenAI, DeepSeek, and Gemini responses are
recorded before contract mapping. If OpenAI `responses.parse()` raises during
its internal Pydantic/JSON parsing, the SDK may not attach the underlying
Responses API payload to the exception. In that case the trace records the
complete request, exception attributes, cause/context, and explicitly marks the
raw response as unavailable; it cannot reconstruct bytes the SDK discarded.

## Further documentation

- [`docs/reference/DECOMPOSITION_MODEL.md`](docs/reference/DECOMPOSITION_MODEL.md) explains the two capabilities and their contracts.
- [`docs/reference/ACCOUNTING_MODEL.md`](docs/reference/ACCOUNTING_MODEL.md) explains quantities, equations, modes, units, ranges, and edge behavior.
- [`docs/README.md`](docs/README.md) indexes current reference, active topic, historical, and verification documentation.
- [`AGENTS.md`](AGENTS.md) gives concise maintenance rules for coding agents.
