# Downstream Consumer Audit

Audit date: 2026-10-20

## Scope and method

This audit checks accessible sibling repositories for consumers affected by the Phase 3 public API consolidation. Searches covered the exact removed symbols and imports, the removed `AddedWorkItem.amount` field, removed validation `compatibility` arguments, and general `task_decomposition` imports. Vendored environments, caches, `.git` directories, and `node_modules` were excluded.

The accessible downstream checkout is:

- `/home/xzhang/dev/AgenticAICompass`, HEAD `bb4f534d1` (`fix(dev): mount task decomposition package in compose`)

No other accessible sibling repository contained a `task_decomposition` consumer or one of the exact removed symbols. This is a filesystem audit, not a check of remote repositories, deployed images, installed wheels, or CI-only consumers.

## Findings

### AgenticAICompass uses the canonical public API

The adapter imports current root-level contracts and capabilities from `task_decomposition`, including `DecompositionProvider`, `TransformationDecompositionRequest`, and `TransformationDecompositionResult`:

- `app/services/assumption_trail/task_decomposition_adapter.py:16-35`
- `app/services/assumption_trail/task_decomposition_adapter.py:389-398`
- `app/services/assumption_trail/standalone_provider_factory.py:7-17`
- `app/services/assumption_trail/service.py:90`

The adapter composes `decompose_task()` and `decompose_transformation()`. There are no downstream imports or references to `run_staged_pipeline`, `StagedDecompositionResult`, `task_decomposition.ports`, or `task_decomposition.evaluation.ports`.

### One actual contract migration is required

The deterministic demo provider constructs an `AddedWorkItem` with the removed `amount` field and no causal or reference-class estimate:

- `app/services/assumption_trail/transformation_decomposition_demo.py:142-149`

This is an actual downstream use of the pre-Phase-1 added-work contract. The consumer must instead either return no added-work row, or provide a valid row with:

1. at least one `source_removed_subtask_ids` value that names a baseline subtask classified `REMOVE`; and
2. an `AddedWorkEstimate` with exactly one baseline or external reference and the required quantitative ranges when estimate-mode accounting is intended.

The existing `amount` local at lines 134-138 is therefore also obsolete for this provider. The correct migration depends on whether the demo is intended to demonstrate added work or an empty category; it cannot be inferred by this audit and must not be replaced with a fabricated source ID or estimate.

### No use of removed validation compatibility arguments

No calls to the removed added-work validation `compatibility` argument were found. AgenticAICompass does contain unrelated uses of the word `compatibility`, including `definition.compatibility_notes` in `app/services/transformations/domain/contracts/parameter_registry_docs.py:136` and historical/export compatibility terminology in its own adapter. Those are not calls to `task_decomposition` validation and require no migration for this API change.

### Dependency version and lock state

AgenticAICompass declares `task-decomposition` without a version constraint and resolves it as an editable local source:

- `pyproject.toml:50`
- `pyproject.toml:61`
- `uv.lock:3925-3928`

The locked package reports version `0.1.0`, matching the current checkout, but the version does not distinguish pre-Phase-3 from post-Phase-3 API shape. No outdated published dependency version was found. The editable path means the consumer is source-coupled to `../task_decomposition`; a packaged deployment would need an independently verified build/release selection, which is outside the accessible evidence.

## Migration matrix

- `run_staged_pipeline`: no matches. No migration is required; use `decompose_transformation()` for the public transformation API.
- `StagedDecompositionResult`: no matches. No migration is required; consume `TransformationDecompositionResult`.
- `task_decomposition.ports` / `evaluation.ports`: no matches. No migration is required; current interfaces are not imported by this consumer.
- `AddedWorkItem.amount`: the demo constructor at `transformation_decomposition_demo.py:142-149` is an actual use. Remove `amount` and add valid causal attribution and an estimate, or emit no row. Status: action required.
- Added-work validation `compatibility=`: no matches. No migration is required.

## Verification

The exact-symbol search was run across `/home/xzhang/dev` sibling repositories, excluding this repository and generated/vendor directories. The broader package-import search found AgenticAICompass as the only accessible downstream consumer. No dependent repository was modified.

## Remaining uncertainty and recommended action

The demo provider's intended behavior is ambiguous: its `Governance review` row may be illustrative support work rather than a real AI interaction or verification activity. Before the next AgenticAICompass change, its owner should choose explicitly between an empty added-work result and a fully attributed, quantitatively estimable row. Do not add a compatibility shim in `task-decomposition`.

Remote consumers, deployment artifacts, and external repositories were not accessible and remain unverified. The first implementation step is therefore to update the AgenticAICompass demo fixture/provider and its tests at the consumer boundary, then run that repository's adapter and generation tests.
