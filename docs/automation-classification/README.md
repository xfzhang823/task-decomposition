# Automation Classification Reliability Epic

## Objective

Audit and incrementally improve the reliability of the cross-stage automation classification flow: operational decomposition, binary RETAIN/REMOVE classification, added human work, and deterministic effort accounting. The epic preserves the repository boundary: providers propose semantic facts; `domain/accounting.py` remains authoritative for W0/W1 and derived metrics; added-work taxonomy remains owned by `docs/added-work-taxonomy/`.

## Scope

This epic covers classification context, binary-row semantics, mixed human/AI responsibility, diagnostic evidence, stage handoffs, and traceability. It does not redesign the decomposition evaluator, add scenario/simulation stages, replace deterministic calculations with LLM estimates, or change accounting formulas without an independently approved accounting change.

The production-scheduling evidence is `logs/llm/task_decomposition_2026-10-17_014615.jsonl`, correlation `td-bedf5a99240f40bebbbe6bd7dbcc7322`. Existing related findings are cross-referenced rather than repeated: [added-work taxonomy README](../added-work-taxonomy/README.md), [classification audit](../added-work-taxonomy/08-retain-remove-classification-audit.md), and [production-scheduling audit](../added-work-taxonomy/09-production-scheduling-retain-remove-audit.md).

## Phase plan and status

| Phase | Document | Status |
|---|---|---|
| 01 | [Architecture audit](01-architecture-audit.md) | Complete — audit-only; no production code changed |
| 02 | [Classification design decisions](02-classification-design-decisions.md) | Complete — rationale capture implemented; mixed-activity handling deferred |
| 03 | [RETAIN/REMOVE implementation verification](03-retain-remove-verification.md) | Complete — core implementation verified; no immediate changes recommended |
| 04 | [Added-work verification](04-added-work-verification.md) | Complete — taxonomy and accounting handoff verified; no implementation changes |
| 05 | [End-to-end verification](05-end-to-end-verification.md) | Planned |
| 06 | [Accounting-input origin audit](06-accounting-input-origin-audit.md) | Complete — host input sources and override risks documented; no implementation changes |

This README is the authoritative epic status. Subsequent phases must update it when completed. Phase 02 implementation is documented in the design-decision document, Phase 03 verifies the existing RETAIN/REMOVE implementation, Phase 04 verifies the added-work/accounting handoff, and Phase 06 audits the origin and precedence of host accounting inputs. Rationale capture reuses the existing optional public field and trace path; mixed-activity handling remains deferred pending concrete evidence and explicit approval. The Phase 05 end-to-end document remains reserved and uncreated.

Verification note: Phase 02 baseline repair changed tests and documentation only. The Phase 02 implementation adds only a concise RETAIN/REMOVE rationale request to the existing prompt; it does not change classification categories, thresholds, schemas, orchestration, accounting, or baseline decomposition. The focused rationale and provider-parity tests pass. Phase 03 RETAIN/REMOVE verification passed 121 tests; added-work/accounting verification passed 81 tests. The added-work verification found no implementation defect and records the remaining host-accounting traceability boundary. Phase 06 confirmed that host accounting quantities originate at callers, not providers, and that the canonical path intentionally gives explicit host support values precedence. Full credential-free verification and Ruff results are recorded in the design-decision document.

## Acceptance criteria

The epic is complete when:

- the future-state capability, data/tool access, authorization, autonomy, approval, and exception semantics used by classification are explicit and tested;
- binary RETAIN/REMOVE has an approved rule for whole-row removal and mixed-responsibility rows, without introducing partial percentages;
- added work remains limited to genuinely new execution-time human work and distinguishes interaction from verification without absorbing baseline work;
- every amount has an explicit basis and compatible unit/time basis, and omitted categories have documented zero semantics;
- diagnostic rationale/evidence is available through an approved diagnostic path without unintentionally changing the public result contract;
- classification, allocations, explicit accounting inputs, and final deterministic accounting are reconciled or explicitly marked unverified according to an approved policy;
- credential-free provider-parity, contract, handoff, known-answer accounting, trace, and regression tests pass; and
- no accounting formula, taxonomy ownership, optional-SDK isolation, or public export contract changes occur without their required downstream review.

