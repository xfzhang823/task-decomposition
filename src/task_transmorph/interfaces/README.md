# Interfaces

Host-neutral behavioral protocols. This package contains only `typing.Protocol` definitions — no implementations, no vendor types, no transport, no persistence. Concrete adapters satisfy these protocols structurally; the application checks capabilities at its boundary with `isinstance`.

Dependency direction: `interfaces/` → `contracts.provider` (stage requests and envelopes) and `evaluation.contracts` (evaluation request/result). It is imported by `application/` and the top-level package. Concrete providers do **not** import it — they satisfy the protocols implicitly.

The companion guide for the data exchanged is `contracts/`; the behavioral side lives here.

## Module overview

Two kinds of protocol live in this package:

- **Provider capabilities** — what a provider object must be able to do for a given pipeline stage. They are split so an adapter can advertise exactly the capabilities it implements.
- **Evaluator capability** — what a semantic evaluator must expose, independent of the provider that implements it.

Every provider method accepts a stage-specific request envelope and returns a `ProviderStageResponse`. That envelope carries `stage`, an untyped `payload`, and `ProviderProvenance`. The payload is untrusted: validation, identity checks, allocation, and accounting remain application/domain responsibilities.

Protocols are `@runtime_checkable`, which enables `isinstance` checks. That check is shallow by design: it verifies attribute presence, not signatures or return types.

## Directory structure

```text
 interfaces/
 ├── __init__.py            re-exports the seven protocols
 ├── provider.py            stage-capability protocols for decomposition
 └── semantic_evaluator.py  the semantic-evaluation protocol
```

There are no subpackages. `provider.py` imports request/envelope models from `contracts.provider`; `semantic_evaluator.py` imports the evaluation request and result.

## Core interfaces/types

All seven protocols are runtime-checkable and re-exported by `task_transmorph`.

### `TaskDecompositionProvider`

- `provider_id: str`
- `generate_operational_decomposition(request: OperationalDecompositionRequest) -> ProviderStageResponse`

Proposes operational subtasks and bottom-up effort inputs. The application derives authoritative weights; this method returns no allocation or accounting.

### `TransformationDecompositionProvider`

- `provider_id: str`
- `classify_retain_remove(request: RetainRemoveClassificationRequest) -> ProviderStageResponse`
- `synthesize_agentic_tasks(request: AgenticTaskSynthesisRequest) -> ProviderStageResponse`
- `model_human_agent_activities(request: HumanAgentActivityModelingRequest) -> ProviderStageResponse`
- `estimate_activity_effort(request: ActivityEffortEstimationRequest) -> ProviderStageResponse`

The complete canonical transformation pipeline. An adapter that omits any of the four methods does not satisfy this protocol, and `decompose_transformation` fails explicitly.

### `DecompositionProvider`

Inherits both protocols above and adds nothing. It is the capability required by the one-call `decompose()` composition.

### Granular capability protocols

Each covers exactly one transformation stage:

- `AgenticTaskSynthesisProvider` — `synthesize_agentic_tasks`
- `HumanAgentActivityModelingProvider` — `model_human_agent_activities`
- `ActivityEffortEstimationProvider` — `estimate_activity_effort`

They are declared for custom composition and granular capability checks. The canonical application paths check `TaskDecompositionProvider`, `TransformationDecompositionProvider`, and `DecompositionProvider`, not these three.

### `SemanticEvaluator`

- `evaluate(request: SemanticEvaluationRequest | TransformationSemanticEvaluationRequest) -> SemanticEvaluation`

One entry point serves both evaluation checkpoints; the request type selects the rubric. The application also accepts a bare callable with the same shape when resolving a baseline evaluator, so the protocol describes the object form rather than the only accepted form.

## Usage examples

### Satisfy a provider protocol structurally

```python
from task_transmorph import (
    ProviderProvenance,
    ProviderStage,
    ProviderStageResponse,
    TaskDecompositionProvider,
    TransformationDecompositionProvider,
)


class StubProvider:
    provider_id = "stub"

    def generate_operational_decomposition(self, request):
        return ProviderStageResponse(
            stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            payload={},
            provenance=ProviderProvenance(
                provider_id=self.provider_id,
                stage=ProviderStage.OPERATIONAL_DECOMPOSITION,
            ),
        )

    def classify_retain_remove(self, request): ...

    def synthesize_agentic_tasks(self, request): ...

    def model_human_agent_activities(self, request): ...

    def estimate_activity_effort(self, request): ...


assert isinstance(StubProvider(), TaskDecompositionProvider)
assert isinstance(StubProvider(), TransformationDecompositionProvider)
```

No inheritance is involved. The class satisfies the protocols because the attributes exist.

### Guard a capability before running a pipeline

```python
from task_transmorph import TransformationDecompositionProvider
from task_transmorph.errors import ProviderOutputError


def require_transformation_provider(provider):
    if not isinstance(provider, TransformationDecompositionProvider):
        raise ProviderOutputError(
            "provider does not implement the TransformationDecompositionProvider capability"
        )
    return provider
```

This is the pattern used by `decompose_transformation` and `decompose`; a provider missing one of the four stage methods is rejected before any call is made.

### Implement an evaluator

```python
from task_transmorph import SemanticEvaluation, SemanticEvaluator


class AlwaysAccept:
    def evaluate(self, request):
        return SemanticEvaluation(
            decision="accept", rubric_version=request.rubric_version
        )


assert isinstance(AlwaysAccept(), SemanticEvaluator)
```

## Dependency relationships

```text
  contracts.provider ──────► interfaces/provider.py
  evaluation.contracts ────► interfaces/semantic_evaluator.py
                                │
                                ▼
                  application (guards) · task_transmorph (exports)

  providers/*.py ── satisfy the protocols structurally, without importing them
```

- `application/task_decomposition.py` and `application/transformation_decomposition.py` guard with `isinstance` and read `provider_id`.
- `application/provider_service.py` guards with `DecompositionProvider` for the combined flow.
- `providers/openai.py`, `gemini.py`, and `deepseek.py` implement the methods and set `provider_id` but do not import this package.
- `tests/test_import_boundary.py` asserts the canonical protocol names exist and legacy modules stay absent.

Boundary notes:

- A passing `isinstance` check proves a method *exists*, not that it behaves. Shape is checked here; semantics are validated downstream.
- Protocols never compute weights, effort products, or W0/W1.
- `provider_id` must be a non-empty string; the application enforces that separately when it builds provenance.

## Verification

- `tests/test_import_boundary.py` — canonical protocol attributes, absence of legacy `ports` modules, host-neutral imports.
- `tests/test_semantic_evaluator_providers.py` — evaluator protocol use through provider adapters and mocks.
- `tests/test_task_transformation_boundaries.py` and `tests/test_staged_pipeline.py` — fake providers that satisfy the protocols in staged flows.

Run `pytest`, `ruff check src tests`, `ruff format --check src tests`, and `python -m compileall -q src`.

## Changing this module

1. Adding, removing, or renaming a method changes runtime capability. Every adapter, fake provider, and test double must follow.
2. Keep signatures aligned with the request types in `contracts/provider.py` and `evaluation/contracts.py`; do not introduce vendor or transport types.
3. Do not add implementations, default behavior, or accounting logic here.
4. Update `interfaces/__init__.py` and the top-level `task_transmorph` exports when the public set changes.
5. Prefer a new granular protocol over widening an existing one when a capability is genuinely optional.
