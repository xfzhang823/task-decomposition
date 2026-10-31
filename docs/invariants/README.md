# Invariant Registry

## Purpose and scope

`registry.yaml` is the canonical, machine-readable index of Task Transmorph's architectural, structural, computational, semantic, and boundary invariants. It describes the contracts already established by the implementation, validation layer, deterministic accounting domain, provider boundary, and focused tests.

The registry does not add behavior. It does not own workflow execution, external workload volume, resource capacity, staffing, throughput, scenarios, simulation, or provider execution. Those concerns remain outside this package as described in [`AGENTS.md`](../../AGENTS.md) and the reference documentation.

The active registry contains 31 records: 28 established `STR-*`, `CMP-*`, `SEM-*`, and `BND-*` invariants plus proposed `PROP-001` through `PROP-003`. Historical `PROP-004` is retained in [`AUDIT.md`](AUDIT.md) as superseded by verified `CMP-010` and is not active in the YAML registry.

## Relationship to other documentation

- [`AUDIT.md`](AUDIT.md) records the investigation, evidence, gaps, conflicts, and rationale that established the provisional invariant inventory.
- [`registry.yaml`](registry.yaml) is the normalized canonical representation of that inventory for developers and coding agents.
- [`DECOMPOSITION_MODEL.md`](../reference/DECOMPOSITION_MODEL.md) explains task and transformation decomposition semantics in narrative form.
- [`ACCOUNTING_MODEL.md`](../reference/ACCOUNTING_MODEL.md) explains W0/W1 formulas, units, ratio bases, conversions, tolerances, and edge behavior.

The registry should preserve the audit's invariant IDs and resolved semantics without duplicating the detailed architecture or accounting references.

## Schema

The top-level document has this shape:

```yaml
version: 1
invariants:
  - id: CMP-001
    name: Baseline effort product
    category: computational
    domain: baseline_estimation
    description: >-
      Expected effort per parent output equals expected occurrences per parent
      output multiplied by active effort per occurrence.
    status: verified
    owner:
      - src/task_transmorph/validation/stages.py
    enforcement:
      type: deterministic_validation
      mechanism: Existing validation computes and checks the product.
      tests:
        - tests/test_effort_estimation.py
```

Fields:

- `version` is the registry format version, currently `1`.
- `invariants` is the list of stable invariant records.
- `id` is required and unique. Existing `STR-*`, `CMP-*`, `SEM-*`, `BND-*`, and `PROP-*` IDs must not be casually reused.
- `name`, `category`, `domain`, `description`, and `status` summarize the invariant.
- `owner` lists current repository source paths responsible for the behavior. It is evidence of ownership, not a new dependency.
- `enforcement.type` identifies the current mechanism, such as deterministic validation, deterministic accounting, semantic evaluation, capability validation, or architectural boundary.
- `enforcement.mechanism` briefly explains what the current implementation does. It must not imply stronger enforcement than exists.
- `enforcement.tests` lists existing test files or `file::test_name` references. An empty list is appropriate for proposed invariants.

## Status meanings

- `verified` means current implementation and focused tests establish the invariant, or the invariant is an explicit architectural boundary with current evidence.
- `partial` means meaningful implementation, prompt guidance, semantic evaluation, or tests exist, but the rule is not fully machine-checkable or cross-boundary enforced.
- `proposed` means the idea is useful but is not a current contract. Proposed records are non-authoritative and must not be treated as implemented behavior.

The registry does not use `conflicting` for the current baseline because STR-007 and CMP-010 were resolved. If a future audit finds a conflict, the registry should not silently choose a side; update the audit first and decide whether the record should remain partial or be withheld from the canonical registry until resolved.

## Locating relevant invariants

Start with the domain and public operation involved:

- Baseline decomposition and effort products: `STR-001`, `STR-002`, `STR-007`, `CMP-001`, `CMP-003`, and `CMP-010`.
- Transformation identity and stage coverage: `STR-003` through `STR-006` and `BND-003`.
- W0/W1 and derived accounting: `CMP-005` through `CMP-008` and `BND-002`/`BND-004`.
- Parent-output semantics, conditional frequency, assumptions, and scope: `SEM-001` through `SEM-005`.
- Provider/application ownership and capability checks: `BND-001`, `BND-005`, and `BND-006`.

Use the `owner` paths to find implementation, then the `enforcement.tests` paths to find focused verification. For detailed equations or semantic rationale, follow the links from `AUDIT.md` to the reference documents rather than expanding the registry description.

## Adding, modifying, or retiring an invariant

1. Start with an evidence-backed audit entry. Do not add a registry record only because a rule seems desirable.
2. Preserve the existing ID when refining wording or enforcement evidence. Add a new ID only for a genuinely distinct invariant.
3. Update the implementation or tests first when a verified invariant changes; then update `AUDIT.md` and this registry together.
4. Keep `owner` and `tests` paths current and existing. Use precise test names when available.
5. Downgrade a record to `partial` when enforcement becomes incomplete. Use `proposed` for future contracts and mark enforcement as non-authoritative.
6. Retire or supersede an invariant only with an audit note explaining why the contract was removed or superseded; do not silently delete its ID. Superseded historical IDs need not remain active in the registry.

STR-007 and CMP-010 illustrate the expected workflow: the audit identified conflicts, implementation and focused tests resolved them, current documentation was aligned, and the registry records the resulting verified contracts.

## Enforcement references

The registry points to existing mechanisms; it does not execute them:

- Deterministic validators in `src/task_transmorph/validation/` enforce identity, cardinality, products, units, and stage handoffs.
- Deterministic allocation and accounting in `src/task_transmorph/domain/` enforce normalization, reconciliation, W0/W1, ratios, and edge semantics.
- Application orchestration separates provider proposals from validation and accounting.
- Provider prompts and semantic evaluation protect parent-output scope, active-effort interpretation, conditional frequency, and assumptions, but those semantic rules are not equivalent to structural validation.
- Existing pytest tests provide known-answer and regression evidence. Live provider benchmarks remain opt-in and are not required for ordinary invariant verification.

The YAML registry itself is descriptive. It does not load at runtime, enforce rules, replace validators, or create a new public API.

## Registry metadata validation

`tests/test_invariant_registry.py` performs a small credential-free metadata check:

```bash
.venv/bin/python -m pytest tests/test_invariant_registry.py
```

It verifies YAML parsing, supported version and field values, unique ID format, owner and test references, test-name references written as `file::test_name`, and the non-authoritative shape of proposed records. This test checks registry consistency only; it does not prove mathematical correctness, semantic accuracy, or provider behavior. Use the existing behavioral invariant tests for those concerns.
