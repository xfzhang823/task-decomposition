# Task Decomposition — End-to-End Semantic & Decision-Flow Audit

**Status:** Requirements for a documentation-first, audit-only Codex assignment  
**Date:** 2026-10-19  
**Project:** `task_decomposition`  
**Purpose:** Portable handoff to a new ChatGPT/Codex context window

## 1. Why this audit is needed

The library models AI-driven transformation of a parent task through baseline operational decomposition, semantic evaluation, RETAIN/REMOVE classification, newly introduced AI_INTERACTION/AI_VERIFICATION activities, and deterministic W0/W1 accounting.

A recent live Production Scheduling run returned a baseline decomposition of ten subtasks, and the preceding conversation's review of its classification trace reported that all ten were RETAIN. The added-work provider stage was nevertheless invoked and returned an incomplete structured-output response (`max_output_tokens`). Under the current strict causal rule, if no subtasks are REMOVE, no new added-work rows can have valid removed-subtask sources. This makes the unnecessary added-work invocation a pipeline concern, but the more fundamental question is whether binary RETAIN/REMOVE can accurately model **partially automatable** subtasks.

**Important evidence boundary:** The supplied console trace does not print the actual per-subtask RETAIN/REMOVE decisions or rationales. Codex must verify the all-RETAIN conclusion against the complete JSONL trace or reproduced outputs rather than assume it. The previously discussed token-usage and schema hypotheses must likewise be verified from actual trace fields; do not treat them as established architectural causes.

This audit must determine whether the pipeline is semantically coherent end to end, which issues are already documented or intentionally deferred, and whether partial/soft automation now warrants implementation. It must not implement changes.

## 2. Existing conceptual boundaries to preserve

1. **Parent task:** The unit being transformed and accounted for.
2. **Baseline subtasks:** Operational components of the original task; their effort allocations are shares of the parent task's W0, not estimates of new AI work.
3. **RETAIN/REMOVE:** Currently binary classification of baseline subtasks based on technological automation potential; review the actual prompt to establish precisely what REMOVE means. Do not silently redefine it.
4. **Added work:** Genuinely new execution-time human activities, classified as AI_INTERACTION or AI_VERIFICATION. Existing retained work must not be counted again. Zero added work is valid.
5. **Causal attribution:** Current design requires added-work rows to identify one or more removed baseline subtasks. Investigate whether this becomes too restrictive if partial automation is represented.
6. **Reference-class estimation:** The LLM selects comparable human work and estimates frequency and relative effort; the comparator may be RETAIN, REMOVE, or an external analogous activity. Causal source and estimation reference are separate concepts.
7. **Effort normalization:** Baseline subtask effort is aggregate effort per parent-task execution, not automatically effort per subtask occurrence. Reference frequency is needed before calculating per-occurrence effort.
8. **Deterministic accounting:** Python owns validation, reference resolution, aggregation, units, and W0/W1 calculations; LLMs do not author authoritative accounting totals. Keep `domain/accounting.py` separate from semantic judgments.
9. **Support-work precedence:** Current design includes `host`, `estimate`, and `auto` selection, with host default and explicit zero preserved. Audit the actual implementation against this intention.
10. **Scope:** Distinguish technological potential from deployment/adoption/authorization and from actual realized automation.

These are **previously discussed design intentions**, not independently verified facts about the current checkout. Compare them with docs and code.

## 3. Recent implementation and verification context

A recent implementation report stated that the repository now contains:

- `EstimateRange`, `AddedWorkEstimate`, `ExternalReference`, `SupportWorkMode`, and support-resolution diagnostics.
- `AddedWorkItem.source_removed_subtask_ids` and optional structured estimates.
- Strict/legacy causal validation.
- Deterministic reference-class estimation in `src/task_decomposition/application/added_work_estimation.py`.
- Host/estimate/auto support resolution in the transformation handoff.
- Updated added-work prompt and README.
- Unchanged `domain/accounting.py` and baseline effort allocation semantics.

Reported checks: 269 passed/6 skipped after estimation implementation; later tracing changes reported 272 passed/6 skipped. These are developer-reported test outcomes, not a substitute for code inspection.

The live example used:

```bash
TASK_DECOMPOSITION_TRACE_ENABLED=true \
TASK_DECOMPOSITION_TRACE_CONSOLE=true \
python examples/openai_decompose.py \
  --task-name "Production Scheduling" \
  --task-description "Plan and coordinate manufacturing production to fulfill customer orders within available resources, operational constraints, and delivery deadlines."
```

Recent trace showed the added-work request using `gpt-4o-mini`, an 8,000-token configured output budget, and an API response marked `incomplete` with reason `max_output_tokens`. The console trace displayed `output_tokens=0` and `structured_content_produced=False`; investigate trace semantics if relevant, but do not let this provider failure displace the primary semantic audit.

## 4. Audit scope and priority

**Phase 0 — Documentation and decision history (mandatory first):** Read relevant `docs/` material, especially `docs/automation-classification/`, `docs/added-work-taxonomy/`, README files, audits, design decisions, implementation plans, and verification reports. Inventory prior decisions, settled questions, explicitly deferred capabilities (especially partial/soft RETAIN/REMOVE), implemented/verified work, and remaining gaps. Cite exact paths and sections. Documentation is historical evidence, not automatically implementation truth. Where docs conflict, establish chronology. Do not repeat a completed audit without new evidence.

**Phase 1 — Trace the current end-to-end chain:** Map stages, prompts, contracts, validators, application orchestration, estimation, support resolution, and accounting. Identify what each stage owns and which invariants its output must satisfy before the next stage.

**Phase 2 — Baseline decomposition and granularity:** Determine whether baseline subtasks combine automatable and nonautomatable work, how effort weights are derived, and whether granularity biases downstream classification. Distinguish subtask effort allocation from new-work estimation.

**Phase 3 — RETAIN/REMOVE semantics:** Read the actual classification prompt, contracts, and validations. Establish whether REMOVE means fully automatable, mostly automatable, or another criterion; how mixed subtasks are handled; and whether the all-RETAIN result is justified by actual rationales. Do not assume binary classification is defective without evidence.

**Phase 4 — Partial automation:** Assess the need to represent fully retained, fully removed, and partially automated baseline work. Compare minimally invasive options: soft classification, automation ratio, or a separate quantitative transformation-effort dimension. Distinguish technological feasibility, eliminated baseline effort, residual human execution, and new AI-related effort. Avoid proposing a new mechanism unless the limitation it solves is demonstrated.

**Phase 5 — Added-work causality and duplication:** Audit whether requiring REMOVE sources excludes new AI interaction/verification caused by partial automation of a RETAIN subtask. Verify exclusion of already-retained reviews, approvals, coordination, and other work. Check whether the added-work LLM stage is called when no eligible automated baseline work exists; determine correct deterministic empty-result behavior without silently overriding explicit host support values.

**Phase 6 — Reference-class estimation and accounting:** Trace reference selection, reference frequency, per-occurrence normalization, low/typical/high metadata, quantitative external anchors, noncomputable outcomes, source attribution, host/estimate/auto precedence, units, W0/W1 calculations, and diagnostics. Check for double counting, wrong denominators, unsupported assumptions, and silent zero substitutions. Preserve deterministic accounting ownership.

**Phase 7 — Evidence-based Production Scheduling case:** Reconstruct the actual baseline rows, classifications, rationales, and added-work stage behavior from available trace data. Determine whether any questionable result arises from task decomposition, classification prompt, model judgment, stage orchestration, or another cause. Clearly separate confirmed findings from hypotheses.

## 5. Required deliverable

Produce **one focused audit report**, preferably in the existing audit documentation area rather than duplicating prior documents. Start with:

### A. Prior decisions and audit coverage

Table: topic | documentation path/section | prior conclusion | current implementation status | reason to re-audit (if any).

Then provide:

1. End-to-end reasoning chain and code ownership map.
2. Explicit semantic assumptions and invariants.
3. Confirmed inconsistencies and implementation defects.
4. Known/deferred architectural limitations versus genuinely new findings.
5. Evaluation of whether partial automation is necessary, with alternatives and tradeoffs.
6. Prioritized **minimal** design changes, with evidence and impact on existing contracts.
7. Focused tests that would validate each recommended change.
8. Remaining unresolved questions and any blocked conclusions.

For every significant claim, cite concrete `docs/` references and relevant code paths; cite trace evidence where available. Do not invent prior decisions, implementation status, model rationales, or measured numbers.

**Constraints:** Audit only. No code modifications, refactors, new pipeline stages, accounting redesign, or automatic creation of duplicate audit docs. Update documentation only after findings are agreed upon in a later implementation step.

---

# Copy/Paste Codex Prompt — Complete Assignment

Perform a **documentation-first, end-to-end semantic and decision-flow audit** of the `task_decomposition` repository. **Audit only: do not modify code.**

## Context

The pipeline decomposes a parent task into baseline subtasks with W0 effort shares, evaluates decomposition quality, classifies baseline subtasks as RETAIN/REMOVE, identifies genuinely new AI_INTERACTION and AI_VERIFICATION human work, estimates that work using reference-class comparisons, and performs deterministic W0/W1 accounting.

Recent Production Scheduling testing reportedly classified all baseline subtasks RETAIN. The added-work LLM stage was still invoked and failed with an incomplete structured-output response. The current design requires added-work causal sources to be REMOVE subtasks. More importantly, partial/soft RETAIN/REMOVE has not yet been implemented, raising the question whether binary classification can represent mixed automatable/nonautomatable subtasks without distorting transformation outcomes.

Do not assume the all-RETAIN interpretation is proven by the console trace alone: verify it using the full JSONL trace or reproducible evidence. Separate provider-output failure from semantic design issues.

## Phase 0 — Review existing `docs/` before inspecting or redesigning code

Read relevant documentation, especially:

- `docs/automation-classification/`
- `docs/added-work-taxonomy/`
- Related README files, previous audits, design decisions, implementation plans, and verification reports under `docs/`.

Build a concise decision-history inventory:

1. Previously investigated architectural/semantic questions.
2. Decisions and conclusions already reached.
3. Decisions implemented and verified.
4. Deliberately deferred capabilities, especially partial/soft RETAIN/REMOVE.
5. Unresolved questions and contradictions between documentation and current code.
6. New changes introduced since the earlier audits.

Cite exact documentation paths and sections. Treat docs as historical evidence rather than current code truth. Reconcile conflicting documents chronologically. **Do not repeat settled audits unless new evidence invalidates their conclusions.**

## Phase 1 — Audit the end-to-end reasoning chain

Map actual code ownership and data flow for:

1. Operational decomposition and baseline effort allocation.
2. Semantic evaluation.
3. RETAIN/REMOVE classification.
4. Added-work identification, causal attribution, and reference-class estimation.
5. Host/estimate/auto support-work resolution.
6. Deterministic W0/W1 accounting and result diagnostics.

Document assumptions and invariants at each boundary; identify where the next stage depends on judgments made upstream.

## Phase 2 — Baseline decomposition and classification

Determine whether baseline subtasks contain both automatable and nonautomatable work, and whether decomposition granularity influences RETAIN/REMOVE outcomes.

Inspect the actual classification prompt, contracts, and validators. Determine precisely whether REMOVE means fully automatable, mostly automatable, or technologically replaceable under defined assumptions. Assess how mixed subtasks are handled and whether that produces excessive RETAIN classifications.

Use the Production Scheduling example and actual model rationales to distinguish decomposition problems, prompt semantics, model judgment, and orchestration problems. Do not infer causes without evidence.

## Phase 3 — Evaluate partial automation explicitly

Determine whether the current architecture can faithfully represent:

- Fully retained baseline work.
- Fully removed baseline work.
- Partially automated baseline work with residual human execution.
- Newly introduced AI interaction and verification work.

Evaluate minimal alternatives: soft RETAIN/REMOVE, an automation ratio, or a separate transformation-effort dimension. Distinguish technological potential from actual deployment and from quantitative removed/residual effort. Do not propose implementation until a concrete limitation is demonstrated.

## Phase 4 — Audit added-work causality and double-counting

Examine the rule requiring every added-work row to cite one or more REMOVE subtasks. Determine whether it would exclude legitimate new AI work arising from partial automation of a baseline subtask classified RETAIN.

Check whether retained review, approval, monitoring, troubleshooting, or coordination is being counted again as new work. Estimate only incremental AI-specific activity, not the entire retained subtask.

Determine whether the pipeline should deterministically skip added-work LLM classification when no eligible automation source exists, returning an empty added-work classification. Account for host mode's explicit caller-provided support values; do not silently discard or rewrite them.

## Phase 5 — Audit estimation and accounting

Trace baseline W0 shares, retained/removed effort, causal sources, estimation references, reference occurrences per parent execution, per-occurrence normalization, external quantitative anchors, uncertainty metadata, and category aggregation.

Verify:

- The reference activity may be RETAIN, REMOVE, or external, independently of causal source.
- Baseline effort allocations are aggregate parent-task shares, not automatically per-occurrence values.
- Reference frequency is not implicitly assumed to be one.
- Unsupported estimates do not silently become zero.
- Host/estimate/auto selection respects explicit host zeros and provenance.
- The LLM supplies semantic judgments and assumptions; Python owns deterministic arithmetic.
- `domain/accounting.py` remains the canonical accounting authority.

Identify any wrong denominators, unit mismatches, duplicated effort, or contradictions between docs and implementation.

## Phase 6 — Ground conclusions in evidence

Reconstruct the recent Production Scheduling case from the available JSONL trace and code. Verify which subtasks were classified RETAIN/REMOVE and why. Distinguish actual classifications and rationales from assumptions in earlier discussion.

Treat the added-work API `max_output_tokens` response as a separate provider issue unless evidence shows a direct semantic connection. Do not redesign schemas or token budgets as part of this audit.

## Deliverable

Produce one focused report beginning with:

**A. Prior decisions and audit coverage** — a table of topic, source documentation, prior conclusion, current implementation status, and whether re-audit is justified.

Then include:

1. Current end-to-end reasoning chain and ownership.
2. Semantic assumptions and invariants.
3. Confirmed inconsistencies and defects.
4. Previously documented limitations versus new findings.
5. Whether partial automation is necessary, with alternatives and tradeoffs.
6. Minimal recommended changes ranked by priority.
7. Focused verification tests for each recommendation.
8. Remaining unknowns or evidence gaps.

Cite documentation paths/sections, code paths, and trace evidence for significant findings. Do not fabricate evidence or reopen settled decisions without a demonstrated contradiction.

**Constraints:** Do not implement fixes, refactor code, change accounting formulas, introduce new stages, or create duplicate audit documents. Reuse existing documentation and terminology. This is an evidence-based semantic audit, not a broad code-quality review.
