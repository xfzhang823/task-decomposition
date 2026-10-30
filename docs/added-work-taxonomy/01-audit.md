# Added-Work Taxonomy Audit

## Scope

This audit covers the task-decomposition repository at the requested change boundary. No AgenticAICompass checkout, persistence adapter, frontend, API service, or reporting consumer is present in this workspace, so those direct consumers could not be inspected here.

## Current ownership and flow

The canonical added-work category is `AddedWorkCategory` in `src/task_transmorph/contracts/stages.py`. It is used by `AddedWorkItem`, then validated by `validate_added_work_classification()` in `src/task_transmorph/validation/stages.py`, and produced by the provider stage in `application/transformation_decomposition.py` through `classify_added_work()`.

The OpenAI, Gemini, and DeepSeek adapters share the `ADDED_WORK_PROMPT` in `providers/prompts.py` and the `AddedWorkClassification` response model. The OpenAI adapter also rewrites the provider-facing `SupportWorkInput.value` schema to a numeric representation and canonicalizes returned values to `Decimal`.

## Affected consumers

The current category names occur in:

- `contracts/stages.py` and `contracts/__init__.py` (canonical model/export);
- `application/staged_pipeline.py` (category aggregation into accounting);
- provider prompts and provider tests;
- staged-pipeline, mathematical-validation, boundary, benchmark, and provider parity fixtures;
- accounting documentation and historical audit documents.

The accounting contract itself uses `SupportWorkInputs` with the independent fields `governance`, `operational_support`, and `lifecycle_support`. These are accounting buckets, not the added-work classification enum. No formulas or numeric contracts need to change. Both new execution-level categories will be aggregated into `operational_support` when the pipeline derives accounting support from added-work rows; explicit `accounting_input.support_work` remains authoritative and unchanged.

## Compatibility and migration risk

No database, persistence model, serialized-record migration, or external API consumer exists in this repository. Existing enum values are Pydantic enum inputs and will therefore be rejected after the enum replacement; this is intentional because the task explicitly prohibits silently reinterpreting historical values or adding speculative aliases. Any AgenticAICompass consumer or persisted record outside this checkout must migrate explicitly at its own boundary.

The change is low risk within this repository: category aggregation preserves the total added human work and all W0/W1/accounting formulas remain untouched.

## Structured-output finding

`AddedWorkClassification` requires the complete top-level object with `task`, `added_work_rows`, and `provenance_refs`. The existing prompt said “Return only added-work rows in a JSON object,” which conflicts with that contract and was observed in a trace where the model emitted rows, omitted the root `provenance_refs`, and then generated whitespace until the 2,000-token limit. The implementation will make the complete root shape explicit without raising the token budget.

## Intended changes

1. Replace the three `AddedWorkCategory` values with `AI_INTERACTION` and `AI_VERIFICATION`.
2. Update all in-repository fixtures, prompts, and focused tests.
3. Define the classification boundary around genuinely new execution-time human activities, including interaction/retry/intervention and output verification/correction/approval.
4. Permit and test an empty `added_work_rows` result.
5. Keep canonical effort/accounting contracts and provider numeric handling unchanged.

The taxonomy is an operational design informed by the METR study's activity-based measurement approach; it is not presented as a taxonomy defined by METR. Reference: <https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf>.
