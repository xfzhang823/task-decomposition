# Ports

Host-neutral extension seams. The core **defines** the abstract ports here — the plugs a host fills in — while hosts and concrete providers **implement** them outside this package, keeping the core independent of any vendor SDK, transport, persistence layer, or host framework.

Dependency direction: `application/` → `ports/` (abstract) ← `providers/` (concrete adapters).

## How to read this folder

**The name.** "Port" here is hexagonal-architecture vocabulary — a socket the outside world plugs into — not a hardware or networking port.

Each module is one **port**: a Python `Protocol` that a host implements. Everything else in the file — the `BaseModel` classes — is just the frozen data the port sends or returns (its request/result types). The models are not the point; the `Protocol` is.

**Ports vs. `contracts/`** — both hold data models, so the split can look arbitrary. The rule:

- `contracts/` = canonical models the whole core agrees on and passes through the pipeline: stage results, effort, provenance, and the provider request/response envelopes. Shared vocabulary.
- `ports/` = the interfaces. A port ships its own request/result models only when they belong to an optional extension that is actively consumed by the core. When the models are part of the canonical pipeline (`provider.py`), they live in `contracts/` and the port simply imports them.

Rule of thumb: a data class the pipeline reads or produces lives in `contracts/`; a `Protocol` a host implements lives here.

## Modules

| Module | Interface (a host implements) | Data models it ships | Required? |
| --- | --- | --- | --- |
| `provider.py` | `TaskDecompositionProvider`, `TransformationDecompositionProvider`, `DecompositionProvider` | none (imported from `contracts/`) | Yes |
| `effort_allocator.py` | `EffortAllocator` | `EffortAllocationRequest`, `EffortAllocation`, `EffortAllocationResult` | No |

### `provider.py` — the required port

The staged decomposition capabilities that `application/provider_service.decompose` drives. Interfaces only; every request/response model comes from `contracts/provider.py`.

- `TaskDecompositionProvider` — `provider_id: str`; `generate_operational_decomposition(OperationalDecompositionRequest) -> ProviderStageResponse`.
- `TransformationDecompositionProvider` — `provider_id: str`; `classify_retain_remove(RetainRemoveClassificationRequest) -> ProviderStageResponse`; `classify_added_work(AddedWorkClassificationRequest) -> ProviderStageResponse`.
- `DecompositionProvider` — composite of the two; the port `decompose()` accepts.

Every stage method returns an **untrusted** `ProviderStageResponse`; the application validates the payload and never trusts it directly.

### `effort_allocator.py` — optional extension

Lets a host split a parent effort across operational subtasks. Supplies per-row effort only; it never computes impact — that stays in canonical accounting.

- Interface: `EffortAllocator.allocate(EffortAllocationRequest) -> EffortAllocationResult`.
- Data: `EffortAllocationRequest` (`task`, `operational_subtasks`, `parent_effort`), `EffortAllocation` (`subtask_id`, `effort`, optional `weight_ratio`, `provenance_refs`), `EffortAllocationResult` (`allocations`, `provenance_refs`).

## Invariants

- Provider output is untrusted. The application validates every `ProviderStageResponse` payload and provenance; a provider is never asked for, and never trusted with, `W0`/`W1` or derived metrics.
- `EffortAllocator` supplies row effort but never computes `W0`/`W1`/impact — that stays in canonical accounting.
- All models here are frozen with `extra="forbid"`.
- Import boundary: this package must not pull in `openai`, `google.genai`, `anthropic`, `sqlalchemy`, `fastapi`, or host frameworks. Enforced by `tests/test_import_boundary.py` and `tests/test_provider_import_isolation.py`.

## Usage

```python
from task_decomposition import decompose                    # application entry point
from task_decomposition.ports import DecompositionProvider  # the port to implement

class MyProvider:                                           # host-side adapter
    provider_id = "my-provider"
    def generate_operational_decomposition(self, request): ...
    def classify_retain_remove(self, request): ...
    def classify_added_work(self, request): ...

result = decompose(request, MyProvider())                   # validated staged result + accounting
```
