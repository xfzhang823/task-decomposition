# Documentation guide

This directory separates current reference material, active topic work, historical implementation records, and final verification.

## Start here

- [Decomposition model](reference/DECOMPOSITION_MODEL.md) — task and transformation capabilities, contracts, and ownership boundaries.
- [Accounting model](reference/ACCOUNTING_MODEL.md) — W0/W1 equations, effort bases, units, tolerances, and edge behavior.
- [Final verification](verification/FINAL_VERIFICATION.md) — repository-wide verification status and accepted limitations.
- [Canonicalization final verification](verification/CANONICALIZATION_FINAL.md) — completion status for the interfaces migration and Phases 1–4 cleanup.

## Audits

- [Architecture audit](audits/architecture-audit.md) — historical package ownership, execution flow, boundaries, findings, and incremental roadmap.
- [Canonicalization audit](audits/canonicalization-audit.md) — historical legacy-path, duplication, ownership, and dependency-aware deletion findings.
- [Baseline effort weighting audit](audits/baseline-effort-weighting.md) — provider-generated baseline ratios, prompt semantics, validation, normalization, and interpretability limitations.
- [Downstream consumer audit](audits/downstream-consumer-audit.md) — accessible
  consumer usage and required public-API migrations after Phase 3.

## Active topic documentation

- [Added-work taxonomy](added-work-taxonomy/README.md) — AI interaction and verification taxonomy and its accounting alignment.
- [Automation classification](automation-classification/README.md) — RETAIN/REMOVE classification reliability work.
- [Semantic evaluation](reference/SEMANTIC_EVALUATION.md) — current evaluator responsibilities, routing, contracts, and verification boundaries.

## Historical records

- [Audits](audits/) contain repository and boundary audits that preserve implementation evidence.
- [History](history/) contains phase-specific migration, packaging, validation, and documentation reports.

Historical reports may contain references to superseded APIs or earlier repository states. They are evidence, not current API guidance; use the reference documents and repository `README.md` for the current design.
