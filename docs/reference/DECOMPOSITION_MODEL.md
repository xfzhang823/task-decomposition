# Decomposition Model

## Task decomposition

### Canonical task definition

A task is a bounded unit of work performed to produce a defined output. `TaskReference` establishes task identity; `ParentOutputContract` establishes the output unit, completion boundary, and scope exclusions; and `TaskDecomposition` describes the operational work and expected baseline human effort required per completed parent-task output. A task does not inherently require one executor, sequential execution, or a particular staffing arrangement.

Task decomposition answers “What work exists?” Its canonical input is `TaskDecompositionRequest`, which contains a host-neutral `TaskReference`, `task_context`, and optional measured baseline effort. It does not contain transformation context.

`decompose_task(request, provider, evaluator=None)` asks a `TaskDecompositionProvider` to propose operational subtasks and one bottom-up effort estimate per subtask. The application validates the provider response for contract shape, identity, ordering, dependencies, and complete bottom-up effort coverage, then uses the configured LLM semantic evaluator for contextual operational judgment. After evaluator acceptance, expected effort products determine relative allocation weights, which are normalized deterministically to `W0 = 1.0`; an optional measured baseline materializes absolute allocations using those same derived weights.

Baseline decomposition providers supply bottom-up effort estimates for each subtask: expected occurrences per parent output and active human effort per occurrence. The application calculates the expected-effort product and derives relative effort shares deterministically; provider-supplied relative weights are not authoritative. Estimates carry rationale and assumptions and are not measurements of capacity or workflow volume.

Baseline decomposition also returns a `ParentOutputContract` and one bottom-up `BaselineSubtaskEffortEstimate` per operational subtask. Each estimate uses the same parent-output denominator and follows `expected occurrences × active effort per occurrence`; the application calculates and validates the product, converts compatible duration units, sums total baseline effort per output, and derives relative weights from those absolute estimates. These values are model-generated planning estimates unless marked supplied, not measured observations. Provider-supplied relative weights are retained only as non-authoritative response data; canonical validation requires the bottom-up estimates and canonical allocation is derived from their products.

### Effort estimation semantics

One parent-task execution represents one defined parent output unit, such as one claim triaged, one ticket resolved, or one invoice reviewed. Every subtask estimates its contribution per that same parent output unit, even when subtasks use different native work units such as documents, messages, requests, or escalations.

For each subtask, the intended semantic relationship is:

```text
expected_subtask_effort_per_parent_output
    = expected_occurrences_per_parent_output
      × active_human_effort_per_occurrence
```

Expected occurrences may be zero, fractional, one, or greater than one. They represent the average number of executions per parent output and include conditional work, repetition, and active rework; they are not necessarily probabilities. Expected parent effort is the sum of expected subtask effort, and `relative_effort_weight` is derived from those absolute products. Python performs the product and normalization deterministically.

The baseline includes active human effort such as analysis, review, communication, coordination, execution, and active rework. It excludes passive waiting, queueing, and unattended processing. Internal workload, such as documents per claim, belongs inside the per-parent estimate and must not be multiplied again. External workload volume, such as claims per month, belongs to downstream workload and capacity systems, not relative task decomposition.

Expected effort is active human effort per completed parent-task output, not elapsed cycle time. Clarification, verification, exception handling, and handoff work are included when they occur within the completion boundary. Expected effort is summed across contributing activities independently of staffing, sequencing, or concurrency; supplied facts and model-generated assumptions remain distinct.

Baseline relative effort is dimensionless. When a measured parent effort per output is supplied, the existing `EffortQuantity` and `allocate_effort()` utility materialize compatible absolute subtask allocations using the normalized shares. Without measured or externally supplied absolute effort, normalized weights must not be interpreted as hours, FTE, capacity, or staffing requirements.

The conceptual downstream work requirement is compatible with a representation such as `work_unit`, `effort_per_unit`, and `effort_time_unit`, for example one claim requiring 1.5 hours of active human effort. Resource identity, FTE allocation, labor calendars, availability, throughput, and capacity conversion remain outside this package. `EffortQuantity.time_basis` preserves the existing period/execution semantics for absolute quantities and is not reinterpreted as external workload volume.

Assumptions about parent output basis, typical internal workload, conditional or repeated occurrences, effort per occurrence, complexity, information availability, and unknowns should be stated in `effort_rationale`. Supplied facts and model-inferred assumptions remain distinguishable through the rationale and available provenance; no additional assumption schema is required by the current contract.

The result is a frozen `TaskDecomposition` containing `OperationalDecomposition`, `OperationalSubtask` rows, and `BaselineEffortAllocation` rows when supplied or allocated. Each baseline allocation is attached to a subtask by stable `subtask_id` and contains explicit absolute effort, normalized weight, or both as allowed by the contract.

The key invariant is that transformation decomposition consumes an existing `TaskDecomposition`; it does not perform task decomposition itself. A reviewed baseline can therefore be retained and reused by a host for later transformation evaluations without regeneration in this library.

## Transformation decomposition

Transformation decomposition answers “What happens to that existing work under this transformation?” Its canonical input is `TransformationDecompositionRequest`, which contains the reusable `TaskDecomposition`, `transformation_context`, and explicit `AbsoluteEffortInput` or `NormalizedAccountingInput`.

`decompose_transformation(request, provider)` asks a `TransformationDecompositionProvider` to classify the supplied operational subtasks as `RETAIN` or `REMOVE`, validates identity and coverage, then asks the provider to propose new added/support human work. Added work is separate from baseline rows and uses the explicit Wave 1 support basis contract.

When the provider implements the optional `AgenticTaskSynthesisProvider` capability, the application inserts an Agentic Task Synthesis stage between classification and added-work proposal. The built-in OpenAI, Gemini, and DeepSeek adapters implement this capability; external providers may omit it. An `AgenticTask` is a semantic transformation artifact describing one coherent AI responsibility, with its source `REMOVE` subtasks, required inputs, and expected outputs. Deterministic validation requires every `REMOVE` subtask to be assigned exactly once, rejects `RETAIN` or unknown sources, and permits zero tasks when there are no `REMOVE` subtasks. A non-null `agentic_task_synthesis` result means synthesis completed, including the valid zero-task case; `None` means the provider lacks the optional capability, while invalid supported output fails the transformation.

The distinction is intentional: a baseline subtask is original human work; a `REMOVE` subtask is original execution delegated to AI; an agentic task is the coherent AI responsibility replacing one or more removed subtasks; and added human work is new interaction or verification, including work triggered by exceptions. Agentic tasks are not workflow execution nodes, tool plans, resource requirements, time estimates, or additional human-effort entries, and added-work estimation does not yet depend on them.

When agentic synthesis completes, the optional Human–Agent Interaction Modeling stage may define semantic `HumanAgentActivity` records. Each record identifies a human action around one or more agentic tasks, its trigger, category, and expected deliverable. Activities are not occurrence estimates or effort-bearing rows: they do not directly contribute to W1. The existing added-work proposal remains the sole input to the current resolver; migration from proposal rows to modeled activities is deferred to a later phase.

All transformation stages preserve the original parent-task boundary. A downstream role, handoff, or later decision mentioned in the task description is context unless the parent task explicitly owns that work. For example, preparing a claim for an adjuster does not include the adjuster's later coverage or liability adjudication. Semantic prompts reinforce this boundary; structural validation cannot determine every form of scope leakage.

When the provider supports the complete activity-based path, the application then estimates each modeled activity as active human effort per parent output:

```text
expected activity effort = expected occurrences per parent output
                            × active effort per occurrence
```

The activity estimate uses the same parent-output denominator and completion boundary as the baseline decomposition. Retained human responsibilities remain part of retained baseline effort; newly introduced interaction or verification is added once, without counting retained work or AI execution time again.

Occurrences include conditional frequency and repetition once; parent workload volume is not multiplied again. Passive waiting, autonomous agent execution, and machine processing are excluded. The provider supplies occurrence and per-occurrence assumptions and rationale; Python derives and validates the product and units deterministically. Only `AI_INTERACTION` and `AI_VERIFICATION` contribute, with exceptions represented as triggers for one of those categories.

Transformation calibration follows one explicit precedence order: caller-supplied absolute `baseline_human_effort`, then the Phase 1 bottom-up `BaselineEffortEstimation` total. These sources are not averaged or combined. The result exposes `baseline_calibration_source` as `supplied` or `baseline_bottom_up`. Normalized weights alone are never treated as minutes or hours.

When an absolute calibration is authoritative, the application preserves the frozen bottom-up subtask proportions and scales retained and removed baseline effort to that calibration before the accounting handoff. Thus a 27-minute bottom-up estimate can be consistently represented as a 30-minute supplied baseline without rounding intermediate proportions. Activity-based added effort still follows expected occurrences multiplied by active effort per occurrence, and the resulting retained-plus-added effort is passed to the existing canonical accounting authority.

Activity-based estimates are the only supported post-transformation support-work method. The result records the selected baseline calibration source as caller-supplied or bottom-up. Providers that cannot implement the required transformation stages fail explicitly; incomplete supported output is not converted to a legacy fallback.

When normalized accounting has neither a supplied baseline nor a bottom-up baseline, activity-based transformation fails explicitly rather than fabricating a calibration. The activity provider receives the application-owned calibration context and estimates only post-AI human activity effort. The prompt prohibits targeting a desired W1/W0 ratio; variation between model runs remains an explicit planning-estimate limitation.

After stage validation, the application applies the frozen baseline allocations to the classification rows and performs the internal validated accounting handoff. Added-work ranges are retained for traceability, but canonical point accounting uses their typical values. That handoff delegates all W0/W1 and derived metrics to `domain/accounting.py`. The public result is a `TransformationDecompositionResult` containing the original baseline, classification, added work, canonical impact, and portable provenance.

The accounting identities remain `W0 = retained baseline effort + gross removed work` and `W1 = retained baseline effort + resolved added human effort`. Activity estimates are converted to the existing support-work inputs before this handoff; they do not create a second accounting implementation or an additional baseline component. Resource capacity, FTEs, calendars, demand, and throughput remain downstream concerns.

## Provider capability boundary

`TaskDecompositionProvider` owns only the operational decomposition proposal. `TransformationDecompositionProvider` owns only transformation-specific classification and added-work proposals. `DecompositionProvider` is the composite protocol for concrete providers that implement both capabilities. OpenAI, Gemini, and DeepSeek may each implement both without creating separate semantic models.

Provider output is untrusted. Structured output from a provider is mapped into the existing contracts and passed through contract and structural validation before semantic evaluation. No provider-supplied accounting metrics are authoritative.

## Concrete example

For a process such as “Review an invoice,” task decomposition may produce subtasks for receiving the invoice, checking required fields, matching it to purchase records, resolving exceptions, and approving payment, with explicit baseline weights. A specified transformation might draft checks and retrieve purchase records while retaining human exception resolution and approval. Transformation decomposition consumes those already-frozen subtasks, marks automated checking candidates `REMOVE`, keeps exception handling and approval `RETAIN`, adds support work if implied, and produces the deterministic canonical impact.

## Boundary with downstream systems

This package evaluates one task decomposition and one transformation request at a time. It does not own scenarios, simulation, Monte Carlo, grid search, workflow execution, capacity computation, or management of alternative transformations. A host may compose repeated evaluations externally while reusing the same `TaskDecomposition`.
