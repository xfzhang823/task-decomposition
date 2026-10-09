# Decomposition Model

## Task decomposition

Task decomposition answers “What work exists?” Its canonical input is `TaskDecompositionRequest`, which contains a host-neutral `TaskReference`, `task_context`, and optional baseline effort and effort weights. It does not contain transformation context.

`decompose_task(request, provider, effort_allocator=None, evaluator=None)` asks a `TaskDecompositionProvider` to propose operational subtasks. The application validates the provider response for contract shape, identity, ordering, and dependencies, then uses the configured LLM semantic evaluator for contextual operational judgment. It establishes baseline effort allocations only after evaluator acceptance.

The result is a frozen `TaskDecomposition` containing `OperationalDecomposition`, `OperationalSubtask` rows, and `BaselineEffortAllocation` rows when supplied or allocated. Each baseline allocation is attached to a subtask by stable `subtask_id` and contains explicit absolute effort, normalized weight, or both as allowed by the contract.

The key invariant is that transformation decomposition consumes an existing `TaskDecomposition`; it does not perform task decomposition itself. A reviewed baseline can therefore be retained and reused by a host for later transformation evaluations without regeneration in this library.

## Transformation decomposition

Transformation decomposition answers “What happens to that existing work under this transformation?” Its canonical input is `TransformationDecompositionRequest`, which contains the reusable `TaskDecomposition`, `transformation_context`, and explicit `AbsoluteEffortInput` or `NormalizedAccountingInput`.

`decompose_transformation(request, provider)` asks a `TransformationDecompositionProvider` to classify the supplied operational subtasks as `RETAIN` or `REMOVE`, validates identity and coverage, then asks the provider to propose new added/support human work. Added work is separate from baseline rows and uses the explicit Wave 1 support basis contract.

After stage validation, the application applies the frozen baseline allocations to the classification rows and calls `run_staged_pipeline()`. That lower-level pipeline validates the handoff and delegates all W0/W1 and derived metrics to `domain/accounting.py`. The result is a `TransformationDecompositionResult` containing the original baseline, classification, added work, canonical impact, and portable provenance.

## Provider capability boundary

`TaskDecompositionProvider` owns only the operational decomposition proposal. `TransformationDecompositionProvider` owns only transformation-specific classification and added-work proposals. `DecompositionProvider` is the composite protocol for concrete providers that implement both capabilities. OpenAI, Gemini, and DeepSeek may each implement both without creating separate semantic models.

Provider output is untrusted. Structured output from a provider is mapped into the existing contracts and passed through contract and structural validation before semantic evaluation. No provider-supplied accounting metrics are authoritative.

## Concrete example

For a process such as “Review an invoice,” task decomposition may produce subtasks for receiving the invoice, checking required fields, matching it to purchase records, resolving exceptions, and approving payment, with explicit baseline weights. A specified transformation might draft checks and retrieve purchase records while retaining human exception resolution and approval. Transformation decomposition consumes those already-frozen subtasks, marks automated checking candidates `REMOVE`, keeps exception handling and approval `RETAIN`, adds support work if implied, and produces the deterministic canonical impact.

## Boundary with downstream systems

This package evaluates one task decomposition and one transformation request at a time. It does not own scenarios, simulation, Monte Carlo, grid search, workflow execution, capacity computation, or management of alternative transformations. A host may compose repeated evaluations externally while reusing the same `TaskDecomposition`.
