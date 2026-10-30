# AI Transformation Summary

## Personal Auto Collision Claim Triage

**Model:** OpenAI GPT-6 Luna  
**Status:** Transformation completed successfully  
**Unit of analysis:** One newly reported auto collision claim, prepared and routed to an adjuster.

## 1. Executive Summary

The model estimates that AI can automate the core activities involved in reviewing, assessing, and routing an auto insurance claim. Human involvement shifts from performing the entire triage process to conditionally verifying AI findings when additional human assessment is needed.

| Key metric | Result |
|---|---:|
| **Baseline human effort (W0)** | **29.4 min/claim** |
| Baseline operational subtasks | 5 |
| Agentic tasks | 4 |
| Baseline tasks classified REMOVE | 100% |
| Human-agent activities | 1 |
| **Post-AI human effort (W1)** | **1.6 min/claim** |
| **Net human effort reduction** | **94.56%** |
| Human effort saved | 27.8 min/claim |
| Implied human-effort productivity multiplier | 18.38× |

**Interpretation:** Under the modeled assumptions, AI reduces expected active human effort from 29.4 to 1.6 minutes per claim. These are model-generated planning estimates, not measured productivity results.

## 2. Baseline Human Workflow

| # | Human activity | Effort | Share |
|---|---|---:|---:|
| 1 | Review submitted claim materials | 9.0 min | 30.61% |
| 2 | Check policy and available records | 7.2 min | 24.49% |
| 3 | Assess information completeness and consistency | 6.0 min | 20.41% |
| 4 | Screen for specialist escalation | 3.0 min | 10.20% |
| 5 | Record triage findings and route claim | 4.2 min | 14.29% |
| | **Total baseline effort** | **29.4 min** | **100%** |

The estimate assumes a representative claim, accessible electronic records, and no extensive investigation. The parent task ends when the claim is routed to the appropriate team. Final coverage and liability decisions belong to the adjuster downstream.

## 3. AI Transformation

| Agentic task | AI responsibility | Replaces |
|---|---|---|
| **AT001 — Claim Review** | Extract collision facts, assess completeness, and identify missing or conflicting information. | SUB001, SUB003 |
| **AT002 — Policy Assessment** | Compare claim details against policy records and flag potential coverage issues. | SUB002 |
| **AT003 — Specialist Screening** | Identify injury, fraud, conflicting-account, and complex-coverage indicators; recommend the appropriate claims pathway. | SUB004 |
| **AT004 — Routing and Handoff** | Prepare triage findings and route the claim to the appropriate team. | SUB005 |

All five baseline subtasks are classified as technologically automatable. This means AI assumes responsibility for the core work; it does not necessarily imply a post-AI workflow without human involvement.

## 4. Human-Agent Activities

### HA001 — Verify Uncertain or Consequential Triage Findings

- **Category:** `AI_VERIFICATION`
- **Associated agentic tasks:** AT001, AT002, AT003, AT004
- **Trigger:** The agent reports uncertainty, conflicting information, a potential coverage concern, injury, possible fraud, or another issue that could materially affect claim readiness or routing.
- **Human action:** Evaluate relevant agent findings, correct material errors or clarify the handoff when needed, without performing downstream adjuster decisions.

| Effort parameter | Estimate |
|---|---:|
| Assumed intervention frequency | 20% of claims |
| Human effort per intervention | 8 minutes |
| **Expected human effort per claim** | **1.6 minutes** |

**Calculation:** `0.20 × 8 = 1.6 minutes per claim`.

The 20% trigger frequency and 8-minute intervention duration are model-generated planning assumptions, not measured operational values.

**Modeling caveat:** The trigger combines *business exceptions* (such as injuries or possible fraud) with *agent execution uncertainty*. These are not necessarily equivalent. If an agent correctly identifies and routes a specialist case, no additional human intervention may be needed within the triage task. The trigger and intervention frequency therefore need further validation.

## 5. Before vs. After AI

| Dimension | Before AI | After AI |
|---|---|---|
| Claim information review | Human | AI |
| Policy and record comparison | Human | AI |
| Information completeness assessment | Human | AI |
| Specialist screening | Human | AI |
| Claim routing and handoff | Human | AI |
| Uncertain findings | Human handles during triage | Conditional human verification |
| **Expected active human effort** | **29.4 min/claim** | **1.6 min/claim** |

### Human Effort Reduction

\[
\frac{29.4 - 1.6}{29.4} \times 100 = \boxed{94.56\%}
\]

### Implied Human-Effort Productivity Multiplier

\[
\frac{29.4}{1.6} = \boxed{18.38\times}
\]

This multiplier measures the reduction in human effort per completed claim. It does **not** necessarily imply an 18.38× increase in end-to-end throughput.

## 6. Overall Assessment

| Area | Assessment |
|---|---|
| Baseline estimation | Plausible planning estimate; not externally validated |
| Agentic task synthesis | Coherent and complete |
| RETAIN/REMOVE classification | Consistent with technological automation potential |
| Human-agent activity identification | Conditional verification identified |
| Human effort estimation | Mathematically consistent |
| Exception handling | Needs clearer separation between business exceptions and agent limitations |
| Financial or throughput impact | Not evaluated in this output |

### Key Takeaway

**The model estimates a 94.56% reduction in active human effort for auto insurance claim triage, with human involvement concentrated in conditional verification of AI-generated findings.**

The calculation is internally consistent, but its magnitude depends heavily on the assumed **20% human-intervention frequency** and **8-minute intervention duration**. The next priority is refining the activity trigger and validating these assumptions—not changing baseline decomposition or deterministic accounting.
