# Provider adapters

This package is the vendor-integration boundary for `task-decomposition`. It contains the concrete adapters that turn provider-neutral stage requests into external model API calls, then turn model responses back into validated provider-stage envelopes.

The package owns transport and provider-specific concerns. It does not own decomposition orchestration, canonical effort allocation, transformation accounting, scenario management, or authoritative business metrics.

## Where this package sits

```text
public application API
  │  provider name or provider object, optional model override
  ▼
application.provider_factory
  │  constructs one configured adapter per selected run
  ▼
providers/<adapter>.py
  │  builds vendor request, invokes SDK, parses response
  ▼
ProviderStageResponse / SemanticEvaluation
  │
  ▼
application validation and orchestration
  │
  ▼
deterministic allocation and accounting domains
```

The application layer remains the authority for stage ordering and validation. Adapters propose semantic facts; they do not calculate `W0`, `W1`, reduction, substitution, augmentation, or effect metrics.

## Modules

### `openai.py`

`OpenAIDecompositionProvider` is the OpenAI adapter. It implements task decomposition, transformation classification, repair, and semantic evaluation through OpenAI structured-output APIs.

Responsibilities include:

- translating stage requests into OpenAI messages and structured-output schemas;
- handling OpenAI response parsing, refusals, schema details, and provider diagnostics;
- forwarding the configured model and output-token limits to every stage, with
  the transformation semantic evaluator's dedicated model routing;
- mapping SDK failures into the library's provider error taxonomy;
- emitting invocation, response, validation, and provenance metadata.

`OpenAIProviderConfig` is a frozen dataclass containing non-secret adapter settings and optionally injected credentials:

| Field | Purpose |
| --- | --- |
| `model` | Model ID used for generation stages and baseline evaluation. Default: `gpt-4o-mini`. An explicit value also overrides transformation evaluation unless the dedicated field is set. |
| `transformation_evaluator_model` | Optional model ID for transformation semantic evaluation. Default: `gpt-6-luna` when `model` is unchanged. |
| `api_key` | Optional injected API key; otherwise `OPENAI_API_KEY` is read when the client is built. |
| `organization` | Optional OpenAI organization. |
| `base_url` | Optional API-compatible endpoint override. |
| `timeout` | Optional SDK timeout. |
| `max_output_tokens` | Default output-token cap. |
| `stage_output_tokens` | Optional per-stage output-token caps; model selection is stage-aware only for transformation semantic evaluation. |

The OpenAI SDK is imported lazily by `_build_client()`. Importing the core package or using a fake provider therefore does not require a live SDK client.

### `gemini.py`

`GeminiDecompositionProvider` is the Google Gemini adapter. It implements the same provider capabilities while translating the shared contracts into Google GenAI request and structured JSON response shapes.

`GeminiProviderConfig` is a frozen dataclass with:

- `model`, defaulting to `gemini-2.5-flash`;
- optional injected `api_key`, otherwise `GEMINI_API_KEY`;
- global and stage-specific output-token settings.

The adapter owns Gemini-specific client construction, response parsing, and error normalization. The Google SDK is imported only when a client must be built.

### `deepseek.py`

`DeepSeekDecompositionProvider` is the DeepSeek adapter. It uses the OpenAI-compatible transport surface, but remains a distinct adapter because its endpoint, defaults, response behavior, and configuration semantics are provider-specific.

`DeepSeekProviderConfig` is a frozen dataclass with:

- `model`, defaulting to `deepseek-flash`, which DeepSeek currently routes to its V4.1 Flash model;
- optional injected `api_key`, otherwise `DEEPSEEK_API_KEY`;
- `base_url`, defaulting to `https://api.deepseek.com`;
- optional `timeout`, `max_tokens`, and stage-specific output-token settings.

Using an OpenAI-compatible SDK transport does not make DeepSeek an OpenAI provider. The adapter reports `provider_id = "deepseek"` and preserves DeepSeek-specific provenance and error identity. The notebook retains `deepseek-v4-pro` as an explicitly labeled legacy comparison option; it is not the repository default.

### `prompts.py`

This module contains provider-facing prompt templates for operational decomposition, operational repair, RETAIN/REMOVE classification, agentic task synthesis, human-agent activity modeling, activity-effort estimation, and semantic evaluation.

Prompts describe the semantic task and output expectations. They must not contain authoritative accounting formulas or replace the Pydantic contracts and application validation.

### `_shared.py`

This module contains vendor-neutral adapter helpers for stage-output-token validation and lookup, host-neutral request serialization, request metadata extraction, prompt-plus-JSON construction, `ProviderStageResponse` construction, model-output parsing, and common provider failure mapping.

It must remain free of vendor SDK imports.

### `_semantic.py`

This module contains shared semantic-evaluation helpers. It serializes the complete evaluation input, parses the `SemanticEvaluation` contract, enforces rubric-version and subtask-identity invariants, and attaches evaluator provenance including effective provider and model IDs.

### `__init__.py`

The package export surface re-exports built-in adapters, configuration dataclasses, and default constants for callers that explicitly want to construct a provider. The normal per-call application path should use the public application API and provider factory instead.

## Provider and model selection

Callers may select a built-in provider by name through the application API:

```python
from task_decomposition import TaskDecompositionRequest, decompose_task

result = decompose_task(
    request,
    provider="openai",
    model="your-model-id",
)
```

`application.provider_factory` maps the provider name to the corresponding adapter and creates its existing config dataclass with the selected model and optional output-token cap. If `model` or `max_output_tokens` is omitted, the adapter's existing default is preserved.

The model override is intentionally run-scoped, not part of `TaskDecompositionRequest` or `TransformationDecompositionRequest`. A caller may also pass an already-constructed provider object, but cannot combine that object with a model override. This prevents the application from mutating a shared provider instance or silently ignoring a requested model.

One provider instance is used across all stages of a run. Generation and baseline evaluation use `model`; transformation semantic evaluation can use `transformation_evaluator_model` and defaults to `gpt-6-luna` when the configured model remains the provider default. Stage-specific output-token limits are supported by provider config objects.

The effective provider and model are recorded through existing provenance and tracing facilities. Provider responses carry `ProviderProvenance.model_id`, and tracing records the model on each invocation.

## Configuration and client lifecycle

Provider constructors accept an optional config, injected client, and injected tracer:

```python
from task_decomposition.providers.openai import (
    OpenAIDecompositionProvider,
    OpenAIProviderConfig,
)

provider = OpenAIDecompositionProvider(
    OpenAIProviderConfig(model="your-model-id"),
    client=fake_client,
)
```

This supports credential-free tests and keeps SDK construction at the adapter boundary. API keys are not stored in request contracts, provenance, or normal trace metadata. Provider modules should not perform network calls at import time.

## Adapter contract

Concrete adapters implement the behavioral protocols in `task_decomposition.interfaces.provider`:

- `generate_operational_decomposition()` proposes operational subtasks and bottom-up effort inputs; the application derives relative effort weights;
- `repair_operational_decomposition()` optionally repairs rejected output;
- `classify_retain_remove()` proposes RETAIN/REMOVE labels for an existing baseline;
- `estimate_activity_effort()` estimates active human effort for the modeled human-agent activities; the application performs all products, unit conversion, and accounting.
- `evaluate()` supplies semantic evaluation when the adapter supports the default evaluator path.

Each generation method returns a `ProviderStageResponse` whose payload is untrusted until the application validates it. Providers must preserve stage, provider, model, request, and provenance identity in that envelope.

## Adding or changing an adapter

When adding a provider:

1. Define a frozen provider config dataclass with a provider-specific default model and non-secret transport settings.
2. Implement the narrow capability protocols required by the adapter.
3. Keep SDK imports lazy and credentials injectable.
4. Convert vendor output into existing contracts; do not create parallel accounting or decomposition schemas.
5. Return provider/model provenance for every stage.
6. Map authentication, execution, and malformed-output failures into the existing error taxonomy.
7. Add credential-free mock tests for every stage and verify provider parity against equivalent semantic outputs.
8. Export the adapter and config from this package only when they are intended as public construction options.

Do not add model catalogs, scenario orchestration, retries that bypass application policy, equal-effort fallbacks, or provider-side accounting.

## Testing expectations

Provider tests should inject fake SDK clients and assert request parameters, especially:

- the selected model is forwarded on every stage;
- omitted model selection uses the adapter default;
- stage output-token overrides use the correct provider parameter;
- malformed output is rejected through the provider error taxonomy;
- provenance identifies provider, model, stage, and request;
- importing deterministic core modules does not require optional provider SDKs.

Live provider tests are opt-in and must never be required for the ordinary test suite.
