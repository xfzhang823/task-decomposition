# Production Scheduling RETAIN/REMOVE Classification Audit

## Scope

This audit covers trace correlation ID `td-684ad5702e3b4773a71f4f04463be66c` from:

`logs/llm/task_decomposition_2026-10-16_144606.jsonl`

No code or prompt changes were made for this audit.

## Executive finding

The classifier returned `RETAIN` for all seven subtasks. The response was structurally valid, but the trace contains no classification reasoning. The prompt explicitly required only `subtask_id` and `classification` and set `rationale` to `null`, so the model's basis for the labels cannot be confirmed.

The all-RETAIN result is inconsistent with the stated threshold when realistic ERP, MES, WMS, HR, workflow, monitoring, reporting, and optimization integrations are considered. The most likely cause is conservative interpretation of broad activities involving review, judgment, approval, accountability, or exception handling as “substantial human execution.” This is an inference; the trace does not prove it.

## Actual request and response

The classifier used `gpt-4o-mini` with no tools. The effective system prompt stated:

- `REMOVE` applies when current AI technology can fully or substantially perform the activity with limited recurring human involvement.
- Realistic software integrations and automation tools should be considered.
- Existing deployment and explicit authorization are irrelevant.
- Empty transformation context is not evidence for `RETAIN`.
- Combined work is `RETAIN` if it still contains substantial human execution.

The request contained:

```json
"transformation_context": {}
```

The original operational task context, including `{"domain": "production_scheduling"}`, was not forwarded to this stage. The transformation payload includes the task, empty transformation context, and operational decomposition.

The response classified every row as `retain`:

| Subtask | Classification |
|---|---|
| `subtask-1` Gather Production Demand | RETAIN |
| `subtask-2` Assess Resource Availability | RETAIN |
| `subtask-3` Create Production Schedule | RETAIN |
| `subtask-4` Communicate Schedule to Teams | RETAIN |
| `subtask-5` Monitor and Report Production Progress | RETAIN |
| `subtask-6` Adjust Schedule Based on Production Status | RETAIN |
| `subtask-7` Document Production Results | RETAIN |

No rationale or explanation was returned. The model response was accepted by structural validation and then passed through orchestration.

## Capability assessment

| Subtask | Current-capability assessment |
|---|---|
| Gather Production Demand | Likely `REMOVE`: ERP/order-system extraction and normalization can be automated, with humans handling exceptions. |
| Assess Resource Availability | Likely `REMOVE`: ERP/MES/WMS/HR integrations can calculate material, labor, and equipment availability. |
| Create Production Schedule | Likely `REMOVE`: constraint-programming, mixed-integer, and scheduling optimization tools can generate feasible schedules; humans may approve exceptions. |
| Communicate Schedule to Teams | Likely `REMOVE`: ERP, workflow, email, and messaging integrations can distribute schedules automatically. |
| Monitor and Report Production Progress | Likely `REMOVE`: MES, IoT, event, dashboard, and reporting integrations can monitor status and produce reports. |
| Adjust Schedule Based on Production Status | Likely `REMOVE`: event-driven rescheduling and optimization tools can revise schedules, escalating exceptional cases. |
| Document Production Results | Likely `REMOVE`: production systems can capture results and generate variance reports automatically. |

These assessments use the supplied semantics: substantial automation with limited recurring human oversight qualifies as `REMOVE`. They do not require full autonomy, elimination of accountability, or an already-deployed integration.

## Root causes

### Confirmed defects

1. **No diagnostic reasoning is available.** The prompt requires only binary labels and null rationale fields.
2. **Validation is structural only.** It checks task identity, unique and complete IDs, count, ordering, and enum values. It does not assess whether a label follows the automation-potential rule.
3. **Orchestration performs no semantic label review.** It calls classification once, validates the structure, applies effort allocation, and continues.
4. **Capability context is sparse.** The classifier received empty transformation context and no concrete capability catalog or integration examples.
5. **Original task context is dropped.** The transformation-stage payload does not carry the earlier `task_context` domain value.

### Likely interpretation issue

The prompt does not define whether approval, accountability, exception review, or occasional escalation count as “substantial human execution.” It also says that a combined subtask is `RETAIN` when it contains substantial human execution, but does not distinguish core execution from limited oversight.

That creates a conservative boundary for broad descriptions such as “evaluate,” “develop,” “monitor,” and “analyze.” There is no evidence that the model was explicitly instructed to require full autonomy, and no evidence of hidden reasoning contradicting its labels.

## Schema, validation, and orchestration

The classification schema permits only `retain` or `remove` and preserves subtask identity. Optional rationale fields exist in the contract, but the provider prompt explicitly nulls them. The validator rejects missing, extra, duplicate, or reordered IDs, but it does not reject an overly conservative classification.

The transformation orchestration invokes `classify_retain_remove`, validates the returned classification, applies baseline allocations, then proceeds to added-work classification and accounting. There is no second evaluator or consistency check against current AI capability.

## Minimal recommended corrections

1. Clarify the classifier instructions that human oversight, approval, accountability, and exception escalation do not by themselves imply `RETAIN`.
2. Clarify that missing or undeployed integrations do not imply `RETAIN`; realistic ERP/MES/WMS/workflow/optimization capabilities must be considered.
3. Add a concise Production Scheduling calibration example covering resource assessment, schedule generation, monitoring, rescheduling, communication, and reporting.
4. Preserve the binary schema and existing orchestration.
5. Consider forwarding the original task context into transformation classification, although this is secondary because empty transformation context is explicitly permitted.
6. If future diagnosis requires explanation, capture rationale through a separate diagnostic mechanism rather than changing the binary classification contract.

## Conclusion

The seven `RETAIN` labels were structurally valid but semantically over-conservative under the stated current-technology standard. The trace cannot establish whether the model required full autonomy, treated oversight as substantial execution, or assumed unavailable integrations because reasoning was intentionally suppressed. The smallest correction is sharper calibration around limited oversight and realistic integrations, supported by Production Scheduling examples; structural validation and orchestration do not need to change.

## Calibration implementation update

The RETAIN/REMOVE prompt was refined with domain-neutral instructions to:

- treat substantial automation with limited recurring oversight as `REMOVE`;
- avoid treating approval, accountability, exception handling, or escalation alone as `RETAIN`;
- distinguish execution of the core activity from review or approval of automated output;
- consider realistic data access, integrations, workflow automation, optimization algorithms, and AI tools whether deployed or not;
- evaluate each subtask independently; and
- preserve the empty-transformation-context rule.

Focused provider tests now cover automated activities with human oversight, genuinely human-intensive activities, binary identity preservation, and empty transformation context. Schemas, orchestration, validation, and other decomposition stages were unchanged.
