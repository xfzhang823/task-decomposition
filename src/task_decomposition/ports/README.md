# Ports

Host-neutral extension seams. The core **defines** abstract capabilities here; hosts and concrete providers **implement** them outside this package. Nothing in `ports/` imports a vendor SDK, transport, persistence layer, or host framework.

Dependency direction: `application/` → `ports/` (abstract) ← `providers/` (concrete adapters).

## Modules

| Module | Role | Required? |
| --- | --- | --- |
| `provider.py` | Staged decomposition capabilities | Yes |
| `benchmark.py` | Optional benchmark lookup | No |
| `effort_allocator.py` | Optional per-row effort allocation | No |

### `provider.py` — required

Three `@runtime_checkable` protocols. All stage methods return an **untrusted** `ProviderStageResponse` envelope (from `contracts/provider.py`).

- `TaskDecompositionProvider` — `provider_id: str`; `generate_operational_decomposition(OperationalDecompositionRequest) -> ProviderStageResponse`.
- `TransformationDecompositionProvider` — `provider_id: str`; `classify_retain_remove(RetainRemoveClassificationRequest) -> ProviderStageResponse`; `classify_added_work(AddedWorkClassificationRequest) -> ProviderStageResponse`.
- `DecompositionProvider` — composite of the two; the port `application/provider_service.decompose` accepts.

### `benchmark.py` — optional

- `BenchmarkQuery` — `task_name`, optional `task_description`, `context`.
- `BenchmarkReference` — `reference_id`, `label`, `provenance_refs`.
- `BenchmarkProvider.retrieve(BenchmarkQuery) -> tuple[BenchmarkReference, ...]`.

Never required for decomposition; no integration is bundled.

### `effort_allocator.py` — optional

- `EffortAllocationRequest` — `task`, `operational_subtasks`, `parent_effort`.
- `EffortAllocation` — `subtask_id`, `effort`, optional `weight_ratio`, `provenance_refs`.
- `EffortAllocationResult` — `allocations`, `provenance_refs`.
- `EffortAllocator.allocate(EffortAllocationRequest) -> EffortAllocationResult`.

Supplies per-row effort only; it never computes impact.

## Invariants

- Provider output is untrusted. The application validates every `ProviderStageResponse` payload and provenance; a provider is never asked for, and never trusted with, `W0`/`W1` or derived metrics.
- `EffortAllocator` supplies row effort but never computes `W0`/`W1`/impact — that stays in Wave 1 accounting.
- All result/request models are frozen with `extra="forbid"`.
- Import boundary: this package must not pull in `openai`, `google.genai`, `anthropic`, `sqlalchemy`, `fastapi`, or host frameworks. Enforced by `tests/test_import_boundary.py` and `tests/test_provider_import_isolation.py`.

## Usage

```python
from task_decomposition import decompose          # application entry point
from task_decomposition.ports import DecompositionProvider  # port to implement

class MyProvider:                                  # host-side adapter
    provider_id = "my-provider"
    def generate_operational_decomposition(self, request): ...
    def classify_retain_remove(self, request): ...
    def classify_added_work(self, request): ...

result = decompose(request, MyProvider())          # validated staged result + accounting
```
