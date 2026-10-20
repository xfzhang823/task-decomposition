# Interfaces

Host-neutral behavioral protocols. Concrete hosts and provider adapters implement these interfaces outside the contract and accounting layers.

Dependency direction: `application/` → `interfaces/` (behavioral protocols) ← `providers/` (concrete adapters).

`contracts/` owns the frozen data schemas passed through the pipeline. `interfaces/` owns only Python `Protocol` definitions:

- `provider.py` — `TaskDecompositionProvider`, `TransformationDecompositionProvider`, and their combined `DecompositionProvider` capability.
- `effort_allocator.py` — `EffortAllocator`, which consumes and returns allocation schemas from `contracts.allocation`.
- `semantic_evaluator.py` — `SemanticEvaluator`, which consumes and returns schemas from `evaluation.contracts`.

Provider output remains untrusted. The application validates every provider response before using it, and no interface computes W0, W1, or derived accounting metrics.
