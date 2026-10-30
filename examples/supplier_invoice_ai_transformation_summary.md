# AI Transformation Summary: Supplier Invoice Review and Approval

**Model:** OpenAI GPT-6 Luna  
**Status:** Transformation complete  
**Parent task:** Review and approve a supplier invoice  
**Output unit:** One supplier invoice review, completed through approval under company policy.

## 1. Executive Summary

AI takes over routine supplier screening, duplicate detection, purchase-order and receipt matching, arithmetic checks, and preparation of approval eligibility findings. A human AP approver remains the final authorization authority, and human discrepancy investigation remains part of the workflow.

| Metric | Result |
|---|---:|
| **Baseline human effort (W0)** | **20.50 min/invoice** |
| Baseline operational subtasks | 7 |
| Agentic tasks | 3 |
| Gross removed baseline effort | 78.05% |
| Retained baseline human effort | 4.50 min/invoice |
| Added human-agent verification | 3.00 min/invoice |
| **Post-AI human effort (W1)** | **7.50 min/invoice** |
| **Net human-effort reduction** | **63.41%** |
| Expected human effort saved | 13.00 min/invoice |
| Implied human-effort productivity multiplier | 2.73× |

These are **model-generated planning estimates**, not observed production measurements. The multiplier describes human effort per invoice, not end-to-end processing speed or payment throughput.

## 2. Baseline Human Workflow

| ID | Baseline subtask | Occurrences per invoice | Minutes per occurrence | Expected minutes per invoice | Share |
|---|---|---:|---:|---:|---:|
| SUB001 | Verify supplier identity and invoice authenticity | 1 | 3 | 3.00 | 14.63% |
| SUB002 | Check for duplicate invoice | 1 | 2 | 2.00 | 9.76% |
| SUB003 | Compare invoice with purchase order | 1 | 4 | 4.00 | 19.51% |
| SUB004 | Verify delivered quantities | 1 | 3 | 3.00 | 14.63% |
| SUB005 | Check invoice calculations and charges | 1 | 2 | 2.00 | 9.76% |
| SUB006 | Investigate and resolve invoice discrepancies | 0.25 | 18 | 4.50 | 21.95% |
| SUB007 | Determine approval eligibility and record approval | 1 | 2 | 2.00 | 9.76% |
| | **Total** | | | **20.50** | **100%** |

The baseline assumes accessible AP, supplier, purchase-order, and warehouse receipt records; a routine number of invoice lines; and discrepancy-resolution episodes on approximately **25% of invoices**. The 25% frequency and 18-minute exception effort are model assumptions, not supplied operational measurements. Passive waiting time is excluded.

## 3. AI Transformation: Agentic Tasks

| Agentic task | Responsibility | Replaces |
|---|---|---|
| **AGT001 — Screen invoice identity and duplication** | Compare invoice and supplier details with approved supplier and AP records; flag authenticity or duplicate concerns. | SUB001, SUB002 |
| **AGT002 — Validate invoice against order, receipt, and calculations** | Check purchase-order matching, delivered quantities, calculations, taxes, totals, and charges; report discrepancies. | SUB003, SUB004, SUB005 |
| **AGT003 — Assess approval eligibility and record authorized approval** | Assess policy eligibility using completed findings and resolution outcomes; record approval **only after human authorization**. | SUB007 |

**Retained baseline responsibility:** SUB006, *Investigate and resolve invoice discrepancies*, remains human-owned in this run. The model also preserves the requirement that the **human AP approver makes the final approval decision**.

## 4. Human-Agent Activities

### ACT001 — Review Agent Findings Before Invoice Authorization

**Category:** `AI_VERIFICATION`  
**Associated agentic tasks:** AGT001, AGT002, AGT003  
**Trigger:** Before the human approver relies on AI findings to make the required approval decision.

**Expected human action:** Review the consolidated authenticity, duplicate, matching, calculation, and approval-eligibility findings; identify material errors or unresolved uncertainty; request clarification or correction when needed.

| Effort parameter | Estimate |
|---|---:|
| Expected occurrences | 1 per invoice |
| Minutes per occurrence | 3.00 |
| **Expected incremental effort** | **3.00 min/invoice** |

The three-minute estimate assumes a concise, reviewable presentation of agent findings. It **does not separately quantify the retained human authorization decision**.

## 5. Before vs. After AI

| Responsibility | Before AI | After AI |
|---|---|---|
| Supplier identity/authenticity screening | Human | AI |
| Duplicate invoice detection | Human | AI |
| Purchase-order matching | Human | AI |
| Warehouse receipt matching | Human | AI |
| Arithmetic, tax, and charge checks | Human | AI |
| Investigate and resolve discrepancies | Human, conditional | **Human retained**, conditional |
| Assess approval eligibility | Human | AI |
| Final invoice authorization | Human | **Human approver** |
| Record authorized approval | Human | AI, after human authorization |
| Review AI findings | Not applicable | Human, every invoice |

### Human-Effort Accounting

**Baseline (W0):** 20.50 minutes per invoice.

**Retained baseline effort:** 0.25 × 18 = **4.50 minutes per invoice**.

**Added human-agent verification:** 1 × 3 = **3.00 minutes per invoice**.

**Post-AI effort (W1):**

\[
W1 = 4.50 + 3.00 = \boxed{7.50\text{ min/invoice}}
\]

**Net reduction:**

\[
\frac{20.50 - 7.50}{20.50} \times 100 = \boxed{63.41\%}
\]

**Implied human-effort productivity multiplier:**

\[
\frac{20.50}{7.50} = \boxed{2.73\times}
\]

The normalized accounting reports **W0 = 1**, **W1 = 0.36585**, **retained baseline ratio = 0.21951**, and **added human-effort ratio = 0.14634**.

## 6. Modeling Observations and Caveats

1. **Final approval must remain human-owned.** The post-AI operating model explicitly requires human AP authorization before payment. AGT003 may record an authorized approval but must not make the decision itself.
2. **Approval-effort accounting warrants review.** The baseline SUB007 combines eligibility assessment and recording approval (2 minutes). The transformed model assigns eligibility assessment and recording to AI while preserving human authorization, but the generated activity notes that the authorization decision is *not separately estimated*. Check that this does not undercount retained human effort.
3. **Discrepancy handling is retained.** The 4.50-minute expected effort for SUB006 is conditional on the model's assumed 25% discrepancy-resolution frequency; it should not be interpreted as AI resolving those issues.
4. **Verification is a separate incremental activity.** ACT001 adds three minutes per invoice to assess AI outputs; avoid counting the same approval review twice when clarifying the authorization boundary.
5. **Workload varies by invoice complexity.** Line-item count, record quality, missing purchase orders, and discrepancy frequency can materially change effort. “One supplier invoice review” is a suitable output unit, but it is not a fixed-complexity workload standard.
6. **Scope excludes payment execution.** Scheduling, settlement, and reconciliation occur downstream and are not included in these estimates.

## 7. Overall Assessment

| Dimension | Assessment |
|---|---|
| Output unit | Appropriate: one completed supplier invoice review |
| Baseline decomposition | Seven subtasks; 20.50 expected minutes |
| Agentic task grouping | Three coherent AI responsibilities |
| Retained human work | Discrepancy resolution and final authorization |
| Human-agent modeling | One routine verification activity |
| Deterministic W0/W1 accounting | Internally consistent with modeled components |
| Main issue to validate | Human approval decision effort may not be fully represented |
| Financial/throughput impact | Not evaluated |

### Key Takeaway

**The model estimates a 63.41% reduction in active human effort per supplier invoice—from 20.50 to 7.50 minutes—while preserving human discrepancy resolution and final approval authority.** The result is mathematically consistent, but the approval-effort boundary and assumed exception frequency should be validated before treating the estimate as operationally reliable.

---
*Source: User-provided GPT-6 Luna transformation output, October 2026. All quantities are per parent-task output.*
