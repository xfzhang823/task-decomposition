# Accounting Migration

## Local contract change

`SupportWorkInputs` now contains exactly `ai_interaction` and `ai_verification`. `CanonicalTransformationImpact` now exposes `ai_interaction_work` and `ai_verification_work`. The old governance, operational-support, and lifecycle-support fields were removed from active task-decomposition contracts and fixtures; no aliases were added.

The staged pipeline groups each added-work row by its canonical category, preserves the row's basis/unit/time basis, and injects the two resulting inputs into deterministic accounting. Explicit support inputs still take precedence over inferred rows. Total added human effort remains the exact sum of the two categories, so W0/W1 formulas and effort scaling are unchanged. Passive waiting and implementation, deployment, and maintenance costs remain outside this recurring execution-effort contract.

## Cross-repository migration status

The `AgenticAICompass` checkout is present but read-only in this workspace. Its API schemas, assumption-trail models, validators, reasoning/calculation code, frontend TypeScript models/components, fixtures, and tests still consume `governance_effort`, `operational_support_effort`, and `lifecycle_support_effort`. Therefore this deliverable does not claim a completed cross-repository migration.

The required external migration is a breaking contract update: replace those request, response, summary, validation, frontend, and fixture fields with `ai_interaction` and `ai_verification`, then derive labor cost from their summed effort. Historical persisted records containing legacy fields must be rejected or migrated by an explicit data migration owned by AgenticAICompass; no value-to-category mapping is defined here because the old buckets had broader meanings.

No local persistence layer exists, so no database migration was added in `task_decomposition`. Until the external consumer is migrated, its integration boundary is an intentional incompatibility and must not be hidden with aliases.
