"""Shared semantic instructions for concrete provider adapters."""

from task_decomposition.evaluation.rubric import (
    SEMANTIC_EVALUATION_RUBRIC,
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
)

OPERATIONAL_DECOMPOSITION_PROMPT = """
Objective:
Decompose the supplied business task into distinct, concrete human activities suitable for independent automation evaluation. Represent baseline work without assuming or favoring any automation outcome.

Decomposition Rules:
- Each subtask must represent meaningful human work: physical activity, system interaction, communication, investigation, analysis, evaluation, or decision-making.
- Describe what is performed, reviewed, evaluated, or determined—not goals, outcomes, or completion states.
- Use distinct operational responsibilities as the decomposition basis, with independent automation evaluation as a granularity check.
- Avoid overlapping responsibilities, repeated checks, trivial microsteps, and unnecessary fragmentation. Combine duplicate work unless it involves genuinely different actions or decisions.
- Preserve distinct assessments or decisions even when they reuse information from other subtasks.
- Distinguish routine checks for a condition from additional work triggered when that condition is present.
- Include substantive checks and decision criteria required by the task without creating a separate subtask for every criterion.
- Do not assess automation feasibility or assign RETAIN/REMOVE classifications.
- Include only necessary or reasonably implied activities. Do not invent documentation, monitoring, feedback, or follow-up work.
- Include recording or communication when necessary to deliver the output or hand it off. Specify what is communicated and to whom.
- Ensure each subtask name accurately describes its activity.

Subtask Structure:
- Use stable short subtask IDs and a contiguous 1-based sequence.
- Dependencies may reference only earlier subtasks. Sequence alone does not imply dependency.
- Copy dependency IDs exactly (e.g., SUB004, not SUB4). Use an empty list when no dependency exists.
- Keep names and descriptions concise, identifying the activity and its object or decision.
- Omit unnecessary metadata; use empty dependency and provenance arrays unless needed.

Parent Output Contract:
- Define one parent output unit, its completion boundary, and excluded downstream work.
- Infer the contract from the task description when not supplied.
- Do not include downstream adjudication, approval, settlement, or other work beyond the parent-task completion boundary.

Bottom-Up Baseline Effort:
- Provide exactly one `baseline_effort_estimate` per operational subtask, using the supplied schema.
- Estimate expected occurrences per parent output and active human effort per occurrence under the pre-AI operating model.
- Use explicit compatible time units with `per_operation` time basis.
- Estimate expected effort per parent output as occurrences × effort per occurrence. Do not independently invent the calculated product; the application computes and validates it.
- Exclude passive waiting, queueing, unattended machine execution, staffing, capacity, and external workflow volume.
- Do not use transformation classifications, agentic tasks, human-agent activities, productivity targets, or W0/W1 outcomes.

Effort Estimation Principles:
- Use the same parent output denominator for every subtask, even when subtasks have different native work units.
- Expected occurrences may be zero, fractional, one, or greater than one. Account for conditional work, repetition, and active rework without assuming every subtask occurs once.
- Distinguish routine assessments performed for every output from conditional follow-up work. Apply conditional frequencies only to work actually triggered by the condition.
- Estimate each subtask's marginal active effort within the complete parent-task workflow, not the time required to perform it independently from scratch.
- Treat the workflow as a continuous work session. Assume previously gathered information, completed analysis, and intermediate findings remain available to subsequent subtasks.
- For assessments and decisions based on existing findings, estimate only the additional reasoning, verification, or action required. Do not allocate another full review duration.
- For routing, recording, and handoff activities, estimate actual preparation, interaction, and execution time using available information and systems. Do not assume substantial effort merely because an activity is a separate subtask.
- Estimate effort per occurrence considering actual complexity, coordination, information availability, and internal workload.
- Attribute shared information gathering, observations, and reasoning only once. Preserve genuinely additional analysis, verification, documentation, or decision-making effort.
- Do not double-count workload across occurrence frequency, effort per occurrence, or related subtasks.
- Splitting an activity into multiple subtasks must not increase total estimated effort unless the split reveals genuinely additional work. Granularity alone does not justify more effort.
- Use supplied operational facts when available; otherwise generate reasonable occupational planning estimates informed by general knowledge and relevant industry practices.
- Do not require users to supply measured durations or workload volumes.
- Do not present model estimates as measured facts, industry benchmarks, or precise empirical observations.
- Do not use business importance, risk, or decision authority as proxies for effort.

Relative Effort:
- The application derives `relative_effort_weight` from each subtask's expected effort per parent output divided by total baseline effort.
- Do not independently estimate, assign, or optimize relative weights.
- Relative weights are normalized, dimensionless comparisons—not time, FTE, capacity, or measured precision.

Effort Rationale:
- Provide a concise rationale for each subtask's occurrence frequency and active effort per occurrence, typically 1–2 sentences.
- Explain relevant assumptions about complexity, coordination, information availability, conditional frequency, and incremental effort.
- Distinguish supplied facts from model-generated planning assumptions.
- For conditional work, state an approximate expected frequency when not supplied and label it as an assumption.
- Ensure estimates reflect only work attributable to the subtask, without double-counting shared activities.
- Do not fabricate measured data, benchmarks, citations, or claims of source consultation.
- Do not justify effort using vague statements such as "important," "integral," or "frequency varies."

Validation:
- Cover the complete parent task without adding downstream responsibilities.
- Preserve distinct operational activities while avoiding duplicated work and effort.
- Ensure every subtask has a corresponding baseline effort estimate with compatible units and consistent occurrence assumptions.
- Review the complete decomposition as a continuous human work session. Check whether the sum of subtask effort estimates is plausible for the actual work performed, without imposing a predetermined total or overriding bottom-up estimates.
- Check that splitting or separating activities has not artificially increased total effort through repeated reviews, assessments, or handoffs.
- Ensure rationales support estimated frequencies and durations rather than arbitrary relative weights.
- If operational information is incomplete, make explicit, reasonable planning assumptions. Do not invent missing operational facts or claim unsupported precision.

Output:
- Return only the JSON object conforming to the supplied schema.
- Include the parent output contract and bottom-up baseline effort estimates for every subtask.
- The application derives `relative_effort_weight`; any provider-supplied value is non-authoritative.
- Do not include automation readiness analysis, transformation recommendations, implementation plans, scoring, or accounting commentary.
""".strip()

OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT = """
Objective:
Repair the supplied JSON operational decomposition using semantic validation feedback and the original task context. Make only the corrections necessary to restore consistency with the canonical decomposition and baseline effort methodology.

Repair Scope:
- Return the same JSON schema without extra metadata.
- Apply the smallest correction that resolves the validation findings.
- Preserve task identity, valid parent output contracts, subtasks, IDs, ordering, dependencies, baseline effort estimates, rationales, and other unaffected fields.
- Change related fields only when necessary for consistency. Do not modify unrelated work, invent activities, or over-decompose.
- Preserve existing IDs where possible. If structural changes are required, keep IDs unique, sequence contiguous and 1-based, and dependencies referencing exact IDs of earlier subtasks.
- Follow the original operational decomposition rules without favoring automation outcomes.

Activity Requirements:
- Each subtask must describe meaningful, concrete human work: physical activity, system interaction, communication, investigation, analysis, evaluation, or decision-making.
- Describe activities and decisions, not goals, outcomes, states, or vague completion labels.
- Keep names and descriptions concise, accurate, and aligned.
- Preserve distinct operational responsibilities, including assessments or decisions that reuse information from other subtasks.
- Remove duplicated responsibilities and unnecessary fragmentation. Do not merge distinct activities solely because they share inputs.
- Distinguish routine checks from conditional follow-up work triggered by their findings.
- Do not assess automation feasibility or assign RETAIN/REMOVE classifications.

Baseline Effort Requirements:
- Maintain exactly one baseline effort estimate per subtask, using expected occurrences per parent output and active human effort per occurrence.
- Use explicit compatible time units with `per_operation` time basis and pre-AI scope only.
- Allow zero, fractional, one, or multiple expected occurrences. Distinguish routine work from conditional work and active rework.
- Estimate incremental active human effort. Attribute shared information gathering, observations, and reasoning only once across related subtasks.
- Preserve genuinely additional analysis, verification, documentation, and decision-making effort even when activities reuse information.
- Account for complexity, coordination, information availability, and internal workload without double-counting across frequency, effort per occurrence, or subtasks.
- Exclude passive waiting, queueing, unattended processing, staffing, capacity, and external workflow volume.
- Do not use business importance, risk, decision authority, automation outcomes, or productivity targets as proxies for baseline effort.
- Preserve valid estimates. When a correction changes scope, occurrence frequency, or incremental effort, update affected estimates and rationales consistently.
- Do not independently invent `expected_effort_per_parent_output`; the application calculates occurrences × effort per occurrence.
- Do not independently assign or adjust `relative_effort_weight`; the application derives it deterministically.

Effort Rationale:
- Maintain a concise rationale for each subtask's occurrence frequency and active effort per occurrence, typically 1–2 sentences.
- Explain relevant assumptions about complexity, coordination, information availability, conditional frequency, and incremental effort.
- Distinguish supplied operational facts from model-generated planning estimates.
- Use reasonable planning assumptions when measured durations are unavailable; do not require users to supply measurements.
- Do not fabricate measured data, benchmarks, citations, or claims of source consultation.
- Update rationales only when necessary to support corrected estimates or resolve validation findings.

Output:
Return only the repaired JSON object conforming to the supplied schema.
Preserve the parent output contract and one bottom-up baseline effort estimate per subtask.
Do not include automation analysis, recommendations, implementation plans, scoring, or accounting commentary.
""".strip()

RETAIN_REMOVE_PROMPT = """
Classify each operational subtask as RETAIN or REMOVE based on automation potential using current AI-enabled technology, including software integrations, workflow automation, and optimization tools.

The supplied operational decomposition is frozen. Copy the task object exactly, and
reference each subtask by its exact supplied subtask_id. Do not invent, rename,
renumber, omit, duplicate, or reorder subtask references. Do not modify the
decomposition; the application restores canonical names and sequence metadata.

Classification Rules:
- For each subtask, identify the core operational activity and assess it independently without inventing additional responsibilities.
- Assess whether current technology can execute most of that core activity under realistic conditions, using existing AI, software integrations, workflow automation, optimization algorithms, conventional automation, and transferable capabilities from other domains.
- REMOVE: Current technology can execute most of the core operational activity with limited recurring human execution.
- RETAIN: Current technology cannot execute most of the core operational activity, leaving substantial recurring execution to humans.
- Assess technological capability, not deployment, industry adoption, or authorization. Empty transformation context does not imply RETAIN.
- Distinguish feasible adaptation of existing technology from speculative advances requiring fundamental breakthroughs.
- Do not classify RETAIN merely because the activity involves judgment, interpretation, coordination, decisions, oversight, approval, accountability, or occasional exceptions; assess whether technology can perform those core functions.
- Treat oversight, approval, accountability, escalation, and occasional exception handling separately from substantial recurring execution of the core activity.
- Classify each subtask independently. Use transformation context when relevant. Do not assign percentages or additional categories.

JSON Output Rules:
- Include only subtask_id, classification, and rationale for each row.
- Set rationale to one concise sentence grounded in the core activity and recurring human execution; do not include hidden reasoning or calculations.
- Set subtask_name, sequence_index, effort, baseline_effort_ratio, and optional task fields to null.
- Set provenance_refs to [].

Return only the requested JSON. No explanations, calculations, or fabricated effort data.
""".strip()

AGENTIC_TASK_SYNTHESIS_PROMPT = """
Group the frozen baseline subtasks classified REMOVE into coherent agentic tasks that describe what AI is responsible for in the transformed workflow.

- Use only source subtask IDs from the supplied decomposition, and only IDs classified REMOVE.
- Assign every REMOVE subtask to exactly one agentic task. Assign no RETAIN subtask.
- Group subtasks when they share a coherent responsibility, required inputs, and expected deliverables; keep meaningfully distinct responsibilities separate.
- Preserve the required work and deliverables of every replaced subtask across the combined agentic tasks. Do not invent responsibilities unrelated to the transformation.
- Preserve the original parent-task boundary. Treat downstream roles, handoffs, or later decisions mentioned in the task description as context unless the supplied baseline explicitly assigns their execution to this parent task.
- Do not claim ownership of RETAIN work; human-owned approval, escalation, accountability, or exception responsibilities remain outside the agentic task.
- Describe semantic responsibility and expected deliverables only. Do not describe tools, execution graphs, orchestration, staffing, time, savings, capacity, or human added work.
- Do not estimate human interaction time, verification time, agent execution time, human-effort reduction, throughput, capacity, or financial impact.
- Each agentic task must have a stable ID, nonempty name and description, at least one required input, and at least one expected output.
- Return zero agentic tasks when there are no REMOVE subtasks.

Return only the requested JSON object. Do not calculate accounting or added human effort.
""".strip()

HUMAN_AGENT_ACTIVITY_MODELING_PROMPT = """
Model the new human activities required to operate, supervise, verify, and handle exceptions around the supplied agentic tasks.

- Reference only supplied agentic task IDs. Do not reconstruct or regroup baseline subtasks.
- Model a human activity only when a plausible human action is required; autonomous agent operation is not a human activity.
- Use categories AI_INTERACTION, AI_VERIFICATION, or EXCEPTION_HANDLING.
- One activity may reference multiple agentic tasks when it is a shared human action. Do not create one activity per task automatically.
- Preserve the original parent-task boundary. A downstream recipient may be mentioned as context for a handoff, but downstream adjudication, final decisions, settlement, or later-process execution must not become a human activity unless the parent task explicitly owns it.
- Do not recreate REMOVE work, duplicate RETAIN responsibilities, or invent unrelated responsibilities. Retained approval, escalation, accountability, and exception responsibilities remain human-owned.
- Preserve meaningful differences in triggers and human responsibilities, and avoid duplicate shared coordination, verification, or exception activities.
- Define semantic activities only. Do not estimate occurrences, minutes, hours, effort, savings, capacity, throughput, or financial impact. Do not create added-work estimates.
- Return zero activities when the synthesis contains zero agentic tasks or no additional human activity is plausibly required.

Return only the requested JSON object.
""".strip()

ACTIVITY_EFFORT_ESTIMATION_PROMPT = """
Estimate active human effort for the supplied human-agent activities. Return numerical inputs only; Python performs the arithmetic and accounting.

- Use one parent task output as the common denominator for expected occurrences.
- Estimate expected occurrences across all parent outputs. For conditional work, include the probability/frequency once; do not multiply it again.
- Estimate active human effort per occurrence, excluding passive waiting, autonomous agent execution, and machine processing time.
- Consider the associated agentic responsibilities, inputs, outputs, retained human work, and shared activities. Do not estimate separately per removed baseline subtask.
- Estimate only the human action needed to complete the original parent-task output. Exclude downstream adjudication, final decisions, settlement, or later-process execution mentioned as context but outside that output.
- Estimate each modeled activity exactly once, including EXCEPTION_HANDLING when applicable. Shared activities remain one estimate.
- Set expected_effort_per_parent_output to the exact product of expected_occurrences_per_parent_output and active_effort_per_occurrence. Do not round or substitute a conditional value; for example, 0.2 occurrences × 5 minutes per occurrence = 1.0 minute per parent output.
- Provide an explicit effort unit and per-operation time basis. Do not present assumptions as measured observations.
- Estimate only the post-AI activity inputs. Baseline calibration is supplied by the application from caller input or bottom-up decomposition and is never generated in this stage.
- Estimate the pre-AI baseline independently from post-AI activity effort and any desired reduction. Do not choose either baseline calibration or activity estimates to target a W1/W0 percentage; the resulting ratio is computed by Python.
- For the estimated baseline calibration, use the original parent-task description, operational decomposition, and baseline relative weights as pre-AI evidence. Do not infer the calibration from agentic-task scope, human-agent activity effort, added effort, or a desired productivity result, even though those fields are present for context.
- Do not estimate capacity, throughput, staffing, savings, or financial impact.

Return only the requested JSON object.
""".strip()

SEMANTIC_EVALUATION_PROMPT = f"""
Evaluate the complete operational decomposition in the supplied input JSON against the rubric below. Return only the structured evaluation object.

Decision Rules:
- Apply RUBRIC VERSION: {SEMANTIC_EVALUATION_RUBRIC_VERSION}.
- Treat the rubric as the authority for scope, coverage, severity, and decision criteria.
- Apply the rubric's accept, repair, and reject guidance exactly; do not add stricter domain expectations or procedural requirements.
- Output Rules: No hidden reasoning, narrative outside JSON, or numerical quality scores. Set evaluator provenance to null.
- Finding Format: Findings must be concise and actionable. Include subtask_id (if applicable), a short message, and evidence only when it clarifies a defect.

RUBRIC:
{SEMANTIC_EVALUATION_RUBRIC}
""".strip()

__all__ = [
    "ACTIVITY_EFFORT_ESTIMATION_PROMPT",
    "AGENTIC_TASK_SYNTHESIS_PROMPT",
    "HUMAN_AGENT_ACTIVITY_MODELING_PROMPT",
    "OPERATIONAL_DECOMPOSITION_PROMPT",
    "OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT",
    "RETAIN_REMOVE_PROMPT",
    "SEMANTIC_EVALUATION_PROMPT",
]
