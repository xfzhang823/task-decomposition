# Task Decomposition

A reusable Python package for decomposing roles, work descriptions, and business context into structured tasks.

## Purpose

`task-decomposition` provides a standalone task decomposition capability that can be used by workflow, workforce, agent, and simulation systems.

The package is responsible for:

- Accepting role, work, or process context
- Decomposing work into structured tasks
- Normalizing decomposition results into canonical task models
- Preserving decomposition metadata and provenance
- Providing stable contracts for downstream consumers

It does **not** own downstream automation analysis, workforce transformation, workflow simulation, or capacity computation.

## Wave 1 canonical accounting

Wave 1 provides the host-neutral deterministic accounting foundation. For baseline human work `W0`:

```text
W0 = retained_human_work + gross_removed_work
added_human_work = governance_work + operational_support_work + lifecycle_support_work
W1 = retained_human_work + added_human_work
```

The public result keeps gross removal distinct from net substitution:

```text
gross_removed_work_ratio = gross_removed_work / W0
net_remaining_work_ratio = W1 / W0
net_substitution_ratio = 1 - net_remaining_work_ratio
net_augmentation_multiplier = W0 / W1
```

Accounting is available in `NORMALIZED` mode (`W0 = 1.0`) and `ABSOLUTE` mode with an explicit effort unit and time basis. Both modes use the same formulas. Support values must use `RatioBasis`: baseline ratio, gross-removed ratio, already-normalized contribution, or absolute effort. Historical Path B support values with unknown basis are not interpreted.

Effect is derived from `W1` and `W0`: `GAIN`, `NEUTRAL`, or `DEGRADATION`. Canonical values are unclamped, so degradation can produce a negative net substitution ratio and an augmentation multiplier below one. A zero baseline raises `ZeroBaselineError`; a zero net effort raises an explicit invalid-denominator error because the multiplier is undefined.

Wave 1 deliberately does not implement LLM/provider generation, staged Path B decomposition, persistence, APIs, Bot0 adapters, workflow computation, or compatibility projections.

## Wave 2 staged decomposition

Wave 2 adds a provider-independent staged pipeline:

```text
operational decomposition
  -> RETAIN / REMOVE classification
  -> added human-work classification
  -> explicit effort/support handoff
  -> Wave 1 canonical accounting
```

Stage contracts preserve a host-neutral task reference and stable subtask IDs. Operational subtasks may declare dependencies; validators reject duplicate IDs, missing or extra classifications, unknown references, invalid dependency order, and non-contiguous stage indexes. Added work is separate from baseline RETAIN/REMOVE work and uses only the explicit Wave 1 support bases.

Provider output is untrusted. The standalone validators reject readiness/scoring/meta language and require operational decomposition text to describe concrete activities. `run_staged_pipeline` accepts already-typed stage outputs and an explicit `AbsoluteEffortInput` or `NormalizedAccountingInput`; it does not call a provider or infer missing effort. It then delegates all W0/W1, gross-removal, net-substitution, augmentation, and effect calculations to Wave 1.

Wave 2 does not include prompts, LLM/provider clients, API keys, persistence, review authority, Bot0 adapters, workflow computation, or historical Path B ratio conversion. Those remain later-wave or host responsibilities.

## Wave 3 host integration

Hosts implement the provider port outside this package:

```text
host provider infrastructure
        │ implements
        ▼
DecompositionProvider
        │
        ▼
task_decomposition.decompose_task(...)
        │
        ▼
task_decomposition.decompose_transformation(...)
        │
        ▼
validated transformation result + canonical accounting
```

`TaskDecompositionRequest` carries task/process context only. `TransformationDecompositionRequest` consumes the resulting reusable task decomposition and carries transformation context plus explicit Wave 1 accounting input. The provider returns untrusted stage payloads wrapped with generic provider/stage provenance. The application validates each stage before requesting the next one and never accepts provider-supplied W0, W1, substitution, augmentation, or effect values.

Provider SDKs, prompts, credentials, retries, tracing, persistence, and Bot0 adapters belong to the host/provider implementation. The standalone core requires no API key or `.env` file. `EffortAllocator` and `BenchmarkProvider` are optional interfaces only; no concrete allocator or benchmark integration is bundled.

## Optional concrete providers

Wave 3B and Wave 3C provide three interchangeable adapters without making any
vendor SDK a core dependency:

```bash
uv pip install -e '.[openai]'
uv pip install -e '.[gemini]'
uv pip install -e '.[deepseek]'
# or install the currently supported provider set:
uv pip install -e '.[providers]'
```

Configure the corresponding key in the host environment or inject it through
the provider config: `OPENAI_API_KEY`, `GEMINI_API_KEY`, or
`DEEPSEEK_API_KEY`. Defaults are centralized per adapter: `gpt-4o-mini`,
`gemini-2.5-flash`, and `deepseek-chat`. Models and non-secret transport
settings can be overridden in code.

Minimal usage is available in [`examples/openai_decompose.py`](examples/openai_decompose.py):

```python
from task_decomposition import TaskDecompositionRequest, decompose
from task_decomposition.providers.openai import OpenAIDecompositionProvider

result = decompose(request, OpenAIDecompositionProvider(), transformation_context={"goal": "Automate verification"}, accounting_input=accounting_input)
```

Replace the provider import and constructor with
`GeminiDecompositionProvider(GeminiProviderConfig(...))` or
`DeepSeekDecompositionProvider(DeepSeekProviderConfig(...))` to select another
provider. All three adapters use the same prompts and stage contracts. Their
outputs are untrusted and pass through the same validators before Wave 1
deterministic accounting runs. The request must supply explicit accounting /
effort input; no provider is allowed to invent authoritative effort or final
metrics. Bot0 is not required to run the standalone providers.

The core remains usable with fake or custom providers without installing any
LLM SDK. A future provider only needs to implement the existing
`DecompositionProvider` protocol; provider-specific transport and schema
handling belong in its adapter.

## Architecture

```text
Role / Work Context
        │
        ▼
Task Decomposition
        │
        ▼
Canonical Task Structure
        │
        ▼
Downstream Consumers
