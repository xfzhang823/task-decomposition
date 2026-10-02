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
