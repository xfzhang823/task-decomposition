"""Shared semantic instructions for concrete provider adapters."""

from task_decomposition.evaluation.rubric import (
    SEMANTIC_EVALUATION_RUBRIC,
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
    TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC,
    TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
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
- Treat the supplied or inferred parent-output contract as the authoritative scope boundary: one bounded task output, its completion boundary, and excluded downstream work.
- Infer the contract from the task description when not supplied.
- Do not include downstream adjudication, approval, settlement, or other work beyond the parent-task completion boundary.
- Do not assume one executor, a staffing arrangement, or sequential execution; decompose the operational work required to produce the output.

Bottom-Up Baseline Effort:
- Provide exactly one `baseline_effort_estimate` per operational subtask, using the supplied schema.
- Estimate expected occurrences per parent output and active human effort per occurrence under the pre-AI operating model.
- Use explicit compatible time units with `per_operation` time basis.
- Estimate expected effort per parent output as occurrences × effort per occurrence. Do not independently invent the calculated product; the application computes and validates it.
- Exclude passive waiting, queueing, unattended machine execution, staffing, capacity, and external workflow volume.
- Do not use transformation classifications, agentic tasks, human-agent activities, productivity targets, or W0/W1 outcomes.

Effort Estimation Principles:
- Use the same parent output denominator for every subtask, even when subtasks have different native work units. Include internal workload once and exclude external parent-output volume.
- Estimate expected active human effort per completed parent output, not elapsed cycle time. Sum contributing effort independently of staffing, sequencing, or concurrency.
- Expected occurrences may be zero, fractional, one, or greater than one. Account for conditional work, repetition, and active rework without assuming every subtask occurs once.
- Distinguish routine assessments performed for every output from conditional follow-up work. Apply conditional frequencies only to work actually triggered by the condition.
- Estimate each subtask's marginal active effort within the complete parent-task workflow, not the time required to perform it independently from scratch.
- Treat the workflow as a continuous work session. Assume previously gathered information, completed analysis, and intermediate findings remain available to subsequent subtasks.
- For assessments and decisions based on existing findings, estimate only the additional reasoning, verification, or action required. Do not allocate another full review duration.
- For routing, recording, and handoff activities, estimate actual preparation, interaction, and execution time using available information and systems. Do not assume substantial effort merely because an activity is a separate subtask.
- Estimate effort per occurrence considering actual complexity, coordination, information availability, and internal workload.
- Include active clarification, verification, exception handling, and handoff work when it is within the parent-output boundary.
- Attribute shared information gathering, observations, and reasoning only once. Preserve genuinely additional analysis, verification, documentation, or decision-making effort.
- Do not double-count workload across occurrence frequency, effort per occurrence, or related subtasks.
- Build a shared-work ledger before assigning durations: identify which facts, records, or analysis are gathered once, charge that work to the subtask that performs it, and estimate later subtasks as incremental use or decision-making over those findings.
- Separate routine case work from conditional complexity. If a complication affects only a subset of parent outputs, represent its expected frequency with fractional occurrences or conditional rework; do not apply the complex-case duration to every parent output unless the task states that every case is complex.
- Use a representative routine occurrence for recurring work and state any case-mix assumption. Do not use a worst-case duration as the default for all outputs.
- Splitting an activity into multiple subtasks must not increase total estimated effort unless the split reveals genuinely additional work. Granularity alone does not justify more effort.
- Use supplied operational facts when available; otherwise generate reasonable occupational planning estimates informed by general knowledge and relevant industry practices.
- Do not require users to supply measured durations or workload volumes.
- Do not present model estimates as measured facts, industry benchmarks, or precise empirical observations.
- Do not use business importance, risk, or decision authority as proxies for effort.

Relative Effort:
- The application derives `relative_effort_weight` from each subtask's expected effort per parent output divided by total baseline effort.
- Do not independently estimate, assign, or optimize relative weights.
- Relative weights are normalized, dimensionless comparison values—not time, FTE, capacity, or measured precision.

Effort Rationale:
- Provide a concise rationale for each subtask's occurrence frequency and active effort per occurrence, typically 1–2 sentences.
- Explain relevant assumptions about complexity, coordination, information availability, conditional frequency, and incremental effort.
- Distinguish supplied facts from model-generated planning assumptions.
- For conditional work, state an approximate expected frequency when not supplied and label it as an assumption.
- Ensure estimates reflect only work attributable to the subtask, without double-counting shared activities.
- Do not fabricate measured data, benchmarks, citations, or claims of source consultation or unsupported precision.
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

Use the supplied task reference and parent-output contract as authoritative. Classify
only the operational work required to produce that bounded output; downstream work
outside its completion boundary remains out of scope.

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
- Preserve the supplied task identity and parent-output contract; the transformed responsibility remains within the same bounded output.
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
Identify the human activities required to interact with agentic tasks and verify their outputs under the intended post-AI operating model.

Activity Identification:
- Reference only supplied agentic task IDs. Do not reconstruct or regroup baseline subtasks.
- Assess human interaction and verification independently of the technological automation potential used to classify baseline subtasks as RETAIN or REMOVE.
- Agent ownership of a responsibility does not imply that human interaction or verification is unnecessary.
- Identify meaningful human actions arising from the post-AI operating model, including routine interaction, verification, and conditional intervention.
- Consider the agentic responsibilities, expected outputs, information availability, uncertainty, reliability limitations, and requirements for accepting or acting on agent outputs.
- Use only AI_INTERACTION and AI_VERIFICATION. Classify activities by what the human does, not why the activity is triggered.
- One activity may reference multiple agentic tasks. Do not create separate activities merely because multiple agents are involved.
- Distinguish technical capability for autonomous execution from the human involvement required in the intended operating model.
- Do not invent human activities solely because AI is involved, and do not exclude them solely because agents can technically perform the underlying work autonomously.

AI_INTERACTION:
- Model human communication or collaboration with agents, including queries, explanations, clarifications, instructions, and additional context.
- Identify routine interaction when required or reasonably implied by the operating model.
- Identify conditional interaction when agents need human clarification, additional context, guidance, or assistance to complete their responsibilities.
- Do not assume every output requires a human query or conversation.
- Do not duplicate interaction already covered by another activity.

AI_VERIFICATION:
- Model human review, validation, correction, or approval of agent outputs and recommendations.
- Identify routine verification when explicitly required or reasonably implied by the operating model, output acceptance requirements, or agent responsibilities.
- Consider conditional verification when uncertainty, conflicting evidence, reliability limitations, or consequential errors make human assessment necessary.
- Consolidate shared verification into one activity when a single review covers multiple agentic tasks.
- Distinguish verification from formal approval. Do not assume mandatory human approval solely because an agent produces findings, recommendations, or decisions.
- Verification should assess agent outputs, not independently repeat the original human work.

Exceptions and Edge Cases:
- Treat exceptions, uncertainty, and agent failures as activity triggers, not separate categories.
- Distinguish unusual business conditions from situations requiring human intervention.
- An agent identifying, flagging, or appropriately routing an unusual case does not automatically require additional human work.
- Identify conditional human intervention when the agent cannot reliably complete its responsibility, requires human clarification, or produces an output that needs human evaluation before the parent task can be completed.
- Classify intervention as AI_INTERACTION when the human primarily clarifies or guides the agent, and AI_VERIFICATION when the human primarily evaluates, corrects, or authorizes its output.
- Group related exception triggers when they require substantially the same human action. Separate activities only when their human responsibilities or effort-driving work differ meaningfully.
- Do not duplicate intervention already covered by routine interaction or verification.

Operating Model Assumptions:
- Follow explicit operating-model requirements for human involvement, including mandatory verification, approval, conditional intervention, or fully autonomous execution.
- When human oversight requirements are unspecified, assess plausible human interaction and verification based on the agentic responsibilities, expected outputs, operational context, and realistic limitations of AI execution.
- Do not interpret unspecified oversight requirements as confirmation of fully autonomous operation.
- Do not invent mandatory human approval, organizational policies, or regulatory requirements that are not supplied.
- When human involvement is inferred rather than explicitly required, describe the operational assumption or trigger in the activity definition.
- Fully autonomous execution with no additional human activity remains valid when supported by the intended operating model and agentic responsibilities.

Scope and Boundaries:
- Preserve the original parent-task completion boundary. Exclude downstream decisions, adjudication, settlement, and later-process execution unless explicitly included in the parent task.
- Do not recreate REMOVE work, duplicate RETAIN responsibilities, or invent unrelated human work.
- Retained approval, escalation, and accountability remain human-owned and must not be counted again as added human-agent activities.
- Define each activity by its human action, trigger, and associated agentic tasks.
- Keep activities distinct but avoid overlapping reviews, repeated approvals, and unnecessary fragmentation.
- A single interaction may include reviewing findings, questioning the agent, and confirming a recommendation. Split it only when the human actions represent meaningfully different responsibilities.

Estimation Boundary:
- Define semantic activities only. Do not estimate occurrences, time, effort, savings, capacity, throughput, or financial impact.
- Return zero activities when there are no agentic tasks or when the intended operating model and agentic responsibilities support execution without additional human interaction or verification.
- Do not force activities to produce a positive post-AI human-effort estimate.

Return only the requested JSON object.
""".strip()

ACTIVITY_EFFORT_ESTIMATION_PROMPT = """
Estimate active human effort for the supplied human-agent activities under the post-AI operating model. Return estimation inputs only; Python performs arithmetic and accounting.

Estimation Rules:
- Use one parent-task output as the common denominator for all activities.
- Use the same parent-output denominator and completion boundary as the baseline decomposition when resolving post-AI human effort for W1.
- Estimate active human effort per completed parent output, not elapsed cycle time. Staffing, sequencing, concurrency, and AI execution time are not human effort.
- Estimate expected occurrences per parent output and active human effort per occurrence, including routine and conditional activities.
- For conditional activities, incorporate expected frequency once. Allow fractional occurrences and do not assume every activity occurs for every output.
- Estimate incremental human effort within the complete human-agent workflow. Reuse information, findings, and prior interactions rather than estimating each activity independently from scratch.
- Count shared review, clarification, verification, and correction work only once. Additional interaction or intervention must represent effort beyond work already counted.
- Keep retained human responsibilities separate from newly introduced human-agent activities; do not count retained verification, authorization, exception handling, or handoffs again as added work.
- Consider activity triggers, agentic responsibilities, available information, retained human work, and the intended operating model.
- Estimate shared activities once, even when they reference multiple agentic tasks. Do not estimate separately per replaced baseline subtask.
- Exclude passive waiting, autonomous agent execution, machine processing, and downstream work outside the parent-task boundary.
- Use reasonable planning assumptions when measured data is unavailable. Distinguish assumptions from supplied facts.

Calculation:
- Expected effort per parent output = expected occurrences × active effort per occurrence.
- Use compatible time units and a per-operation time basis.
- Do not independently adjust calculated effort or target a desired productivity improvement.

Example:
A human routinely verifies an agent's output and occasionally asks for clarification.
Model verification once per output and clarification at its expected conditional frequency.
Estimate clarification effort incrementally, excluding verification work already counted.
This example illustrates accounting principles, not default activity requirements.

Boundaries:
- Estimate post-AI human-agent activities only. Baseline calibration is supplied separately by the application.
- Do not estimate agent execution time, staffing, capacity, throughput, savings, or financial impact.
- Return only the requested JSON object.
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

TRANSFORMATION_SEMANTIC_EVALUATION_PROMPT = f"""
Evaluate only the cross-stage semantic consistency of the complete frozen AI
transformation in the supplied input JSON. Return only the structured evaluation
object.

Decision Rules:
- Apply RUBRIC VERSION: {TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION}.
- Treat the transformation rubric as the authority for criteria and severity.
- Evaluate the transformation relative to the frozen baseline; do not evaluate
  baseline decomposition quality or suggest additional automation.
- Do not redesign or modify the baseline decomposition.
- Reconcile responsibility and effort across the parent contract, baseline
  subtasks, classifications, agentic tasks, human activities, effort estimates,
  and accounting output. Decisions, authorizations, communication, and execution
  are separate responsibilities unless the artifact explicitly connects them.
- Do not recalculate W0/W1, duplicate deterministic validation, or propose repairs.
- Every finding must set a transformation criterion, identify a concrete
  inconsistency, include artifact evidence, and include affected IDs when the
  supplied input provides relevant IDs. Never invent references.
- Keep the decision and finding severities consistent with the contract: ACCEPT
  only with suggestions, REPAIR with repairable findings and no blocking findings,
  and REJECT with at least one blocking finding.

TRANSFORMATION RUBRIC:
{TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC}
""".strip()

__all__ = [
    "ACTIVITY_EFFORT_ESTIMATION_PROMPT",
    "AGENTIC_TASK_SYNTHESIS_PROMPT",
    "HUMAN_AGENT_ACTIVITY_MODELING_PROMPT",
    "OPERATIONAL_DECOMPOSITION_PROMPT",
    "OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT",
    "RETAIN_REMOVE_PROMPT",
    "SEMANTIC_EVALUATION_PROMPT",
    "TRANSFORMATION_SEMANTIC_EVALUATION_PROMPT",
]
