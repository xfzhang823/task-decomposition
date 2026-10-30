# AI Transformation Summary — SaaS Customer Support Ticket Triage

**Model:** OpenAI GPT-6 Luna  
**Status:** Transformation completed  
**Unit of analysis:** One triaged customer support ticket  
**Post-AI operating model:** A support agent owns the customer response; technical escalation is outside this parent-task boundary.

## 1. Executive Summary

The model assigns the core work of ticket evidence gathering, issue classification, impact assessment, routing, and customer notification to four AI agentic tasks. It also models one routine human verification activity.

| Key metric | Result |
|---|---:|
| Baseline human effort (W0) | **28.0 min/ticket** |
| Baseline operational subtasks | 8 |
| Agentic tasks | 4 |
| Baseline effort classified REMOVE | 100% |
| Human-agent activities | 1 |
| Post-AI human effort (W1) | **5.0 min/ticket** |
| **Net human effort reduction** | **82.14%** |
| Human effort saved | 23.0 min/ticket |
| Implied human-effort productivity multiplier | 5.60× |

**Interpretation:** Under the model's assumptions, expected active human effort falls from 28 to 5 minutes per triaged ticket. These are planning estimates, not measured productivity results.

## 2. Baseline Human Workflow

| # | Baseline subtask | Expected occurrences | Minutes per occurrence | Expected minutes per ticket | Share |
|---|---|---:|---:|---:|---:|
| SUB001 | Review the reported symptoms and evidence | 1.0 | 5 | 5.0 | 17.86% |
| SUB002 | Review account and ticket history | 1.0 | 4 | 4.0 | 14.29% |
| SUB003 | Check product guidance and known incidents | 1.0 | 6 | 6.0 | 21.43% |
| SUB004 | Seek clarification when material details are missing | 0.2 | 5 | 1.0 | 3.57% |
| SUB005 | Determine the issue category | 1.0 | 3 | 3.0 | 10.71% |
| SUB006 | Assess seriousness and customer impact | 1.0 | 4 | 4.0 | 14.29% |
| SUB007 | Select the handling team and route the ticket | 1.0 | 3 | 3.0 | 10.71% |
| SUB008 | Tell the customer what happens next | 1.0 | 2 | 2.0 | 7.14% |
| | **Total** | | | **28.0** | **100%** |

The conditional clarification step assumes that **20% of tickets** require one focused clarification, taking five minutes of active work. This frequency is a model-generated assumption; passive waiting time is excluded.

## 3. AI Transformation

| Agentic task | Responsibility | Replaces |
|---|---|---|
| **AGT001 — Gather and clarify ticket evidence** | Review reported symptoms, screenshots, account and ticket history, product documentation, and known incidents; seek focused clarification when needed. | SUB001–SUB004 |
| **AGT002 — Assess issue category and customer impact** | Determine likely issue category, uncertainty, seriousness, scope, and business impact. | SUB005–SUB006 |
| **AGT003 — Select handling team and route the ticket** | Choose the appropriate support team or specialist and route the ticket with relevant findings. | SUB007 |
| **AGT004 — Update the customer on next steps** | Communicate the triage disposition, handling team, and next step without implying resolution. | SUB008 |

All eight baseline subtasks are classified as technologically automatable. This does not, by itself, establish that the intended operating model requires no human involvement.

## 4. Human-Agent Activities

### HA001 — Review and validate the agent's triage disposition

**Category:** `AI_VERIFICATION`  
**Associated agentic tasks:** AGT001, AGT002, AGT003, AGT004  
**Trigger:** Every triaged ticket, after the agent has produced findings, routing, and a customer update and before these outputs are accepted as completing triage.

**Human action:** Review the evidence summary, classification, business-impact assessment, routing choice, and customer messaging for consistency and support; correct or request revision of material problems. This is intended as one integrated review, not a repetition of the underlying research.

| Effort parameter | Estimate |
|---|---:|
| Expected occurrences per ticket | 1.0 |
| Minutes per occurrence | 5.0 |
| **Expected human effort per ticket** | **5.0 min** |

The five-minute duration is a planning assumption. The model assumes the agent presents a consolidated, reviewable package and that most tickets need no extensive correction.

## 5. Before vs. After AI

| Dimension | Before AI | After AI |
|---|---|---|
| Review symptoms, screenshots, and context | Human | AI |
| Search history, documentation, and incidents | Human | AI |
| Clarify missing material details | Human, conditionally | AI, conditionally |
| Classify issue and assess business impact | Human | AI |
| Select handling team and route | Human | AI |
| Notify customer of next steps | Human | AI; human reviews modeled outputs |
| Validate triage disposition | Part of original human execution | Dedicated human-agent verification |
| **Expected active human effort** | **28.0 min** | **5.0 min** |

### Effort calculation

- **W0:** 28.0 minutes per ticket
- **Retained baseline human effort:** 0 minutes per ticket
- **Added human-agent effort:** 5.0 minutes per ticket
- **W1:** 5.0 minutes per ticket
- **Human effort saved:** 28.0 − 5.0 = **23.0 minutes per ticket**
- **Net effort reduction:** (28.0 − 5.0) / 28.0 = **82.14%**
- **Human-effort productivity multiplier:** 28.0 / 5.0 = **5.60×**

Canonical normalized accounting: **W0 = 1**, **W1 = 0.178571**, **net effort reduction = 0.821429**. These normalized values are ratios, not minutes.

## 6. Modeling Observations

1. **Routine review is inferred, not expressly mandated.** The supplied post-AI operating model says a support agent owns the customer response, but does not explicitly require human review of every ticket. The model nevertheless assumes one five-minute verification for each ticket. This is a reasonable scenario to test, but should be treated as an operating-model assumption rather than an established requirement.
2. **Customer-response ownership deserves clarification.** AGT004 is described as sending the customer update, while the operating model assigns customer-response ownership to a support agent. It may be necessary to distinguish drafting, approval, and sending authority so the AI and human responsibilities are internally consistent.
3. **Clarification is modeled as agent work.** AGT001 may ask the customer questions. Whether the agent can send these questions directly or needs human authorization depends on the intended operating model.
4. **No troubleshooting or resolution is included.** The task ends after classification, prioritization/impact assessment, routing, and the triage update. Downstream investigation, remediation, and follow-up are excluded.
5. **Effort estimates are assumptions.** The 20% baseline clarification frequency and five-minute post-AI review time were generated by the model; operational data would be needed to validate them.

## 7. Overall Assessment

| Area | Assessment |
|---|---|
| Parent-task boundary | Clear and limited to triage |
| Baseline decomposition | Coherent, with conditional clarification |
| Agentic task synthesis | Four coherent responsibilities covering all eight subtasks |
| Human-agent activity | One integrated verification activity |
| Accounting | Internally consistent |
| Primary modeling question | Whether every ticket needs human verification, and who authorizes/sends the customer response |
| Throughput or financial impact | Not calculated |

**Key takeaway:** The model estimates an **82.14% reduction in active human effort per triaged support ticket**, contingent on a routine five-minute human verification step. The principal next check is whether that review frequency and the customer-response ownership accurately reflect the intended post-AI operating model.

---
*Source: supplied GPT-6 Luna transformation output, October 2026. Figures are model estimates, not observed measurements.*
