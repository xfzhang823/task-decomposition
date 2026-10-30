# Added-Work Taxonomy

Status: implemented in `task_transmorph`; the coordinated `AgenticAICompass` migration is pending because that checkout is read-only in this workspace.

This change replaces the added-work classification values `GOVERNANCE`, `OPERATIONAL_SUPPORT`, and `LIFECYCLE_SUPPORT` with the execution-level values `AI_INTERACTION` and `AI_VERIFICATION`.

The taxonomy identifies genuinely new human activities introduced by AI during workflow execution. Financial accounting now uses the same two categories as explicit support-work inputs and derived effort outputs. Labor cost remains derived from human effort by downstream consumers; RETAIN/REMOVE semantics and W0/W1 formulas are unchanged.

- [Audit](01-audit.md)
- [Design](02-design.md)
- [Verification](03-verification.md)
