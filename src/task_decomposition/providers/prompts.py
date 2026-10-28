"""Shared semantic instructions for concrete provider adapters."""

from task_decomposition.evaluation.rubric import (
    SEMANTIC_EVALUATION_RUBRIC,
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
)

OPERATIONAL_DECOMPOSITION_PROMPT = """
Objective:
Decompose the supplied business task into concrete, distinct human activities suitable for independent evaluation for complete automation using current AI capabilities. Ground the decomposition in the baseline work performed, without assuming or favoring an automation outcome.

Decomposition Rules:
- Each subtask must represent a meaningful unit of human work, including physical work, system interaction, communication, investigation, analysis, evaluation, or decision-making.
- Specify what is performed, reviewed, evaluated, or determined.
- Decompose around meaningful, distinct operational activities. Use suitability for independent automation evaluation as a check on granularity.
- Keep subtasks distinct and non-overlapping. Each should describe work not already included in another subtask. Combine activities that repeat the same check against the same information unless they involve clearly different actions or decisions.
- Avoid trivial microsteps or unnecessary fragmentation. Do not split activities merely to create fully automatable subtasks.
- Ensure each subtask name matches the activity described.
- Distinguish reviewing or checking for a condition from the additional work performed when that condition is present.
- Cover the substantive work explicitly required by the task, including criteria that affect decisions or routing. Make these checks clear in the descriptions without creating a separate subtask for every criterion.
- Describe activities, not goals, outcomes, or completion states.
- Do not assess automation feasibility or assign RETAIN/REMOVE classifications.
- Include only activities necessary or reasonably implied by the supplied task objective. Do not add documentation, monitoring, feedback, or follow-up activities merely to make the decomposition appear complete.
- Include recording or communication when needed to deliver the task's result or hand it off. State what is recorded or communicated and for whom; avoid generic activities such as "document outcomes for future reference."

Subtask Structure:
- Preserve task identity. Use stable short subtask IDs and a contiguous 1-based sequence.
- Dependencies may reference only earlier subtasks. Sequence indicates presentation order; it does not by itself imply a dependency.
- Copy dependency references character-for-character from an earlier `subtask_id`; never renumber, shorten, or reformat an ID (for example, `SUB004` must be referenced as `SUB004`, not `SUB4`). If there is no exact ID, use an empty dependency list.
- Keep names and descriptions concise, stating the activity and its object or decision.
- Use empty dependency and provenance arrays unless needed; omit unnecessary metadata.

Parent Output Contract:
- Define one parent output unit, the completion boundary, and any downstream work excluded from that output.
- Infer this contract from the supplied task description when the request does not provide one. A downstream handoff is not completion of downstream adjudication, approval, settlement, or later-process work.

Bottom-Up Baseline Effort:
- When the supplied schema supports `baseline_effort_estimates`, provide exactly one estimate for every operational subtask.
- Estimate expected occurrences per parent output and active human effort per occurrence under the pre-AI operating model only.
- Use explicit compatible effort units with `per_operation` time basis. Exclude passive waiting, machine execution, staffing, capacity, and external workflow volume.
- Provide rationale and assumptions, distinguishing supplied facts from model-generated planning estimates.
- Do not provide `expected_effort_per_parent_output` as an independently invented number; the application calculates it as occurrences × effort per occurrence and validates any supplied value.
- Do not use transformation classifications, agentic tasks, human-agent activities, desired productivity, or W1/W0 targets. If absolute baseline estimates cannot be responsibly produced, omit the estimate collection and preserve the legacy relative-weight behavior.

Relative Effort Estimation:
- Treat one parent-task execution as producing one defined parent output unit. Use that same denominator for every subtask, while allowing subtasks to have different native work units.
- Estimate expected subtask effort per parent output as expected occurrences per parent output × active human effort per occurrence. Occurrences may be zero, fractional, one, or greater than one; include conditional work, repetition, and active rework without assuming every subtask occurs once.
- Estimate effort per occurrence from the work involved, including representative complexity, coordination, information availability, and internal workload. Include internal workload once; do not double-count it in both occurrences and effort per occurrence.
- Keep external parent-output volume (for example, claims per month) outside this decomposition. Exclude passive waiting, queueing, and unattended processing time.
- Use supplied operational facts when available; otherwise make reasonable occupational estimates informed by general knowledge, frameworks such as O*NET, and relevant industry practices.
- Use a consistent relative scale across all subtasks; the application performs authoritative normalization.
- Treat relative weights as normalized, dimensionless comparison values, not minutes, hours, elapsed time, FTE, capacity, or measured precision.
- Do not require absolute minutes, hours, or workload volumes from the user.
- Do not present unsupported precision, measured frequencies, durations, benchmarks, or capacity assumptions as facts.
- Do not use business importance, risk, or decision authority as proxies for human effort.

Effort Rationale:
- Provide a concise rationale for each subtask's relative_effort_weight.
- Explain the parent output basis, frequency and effort-per-occurrence assumptions, and relevant complexity, coordination, information availability, or internal-workload assumptions.
- Distinguish supplied operational facts from model-generated estimates and assumptions.
- State the assumed occurrence frequency clearly. For conditional work, provide an approximate frequency or range labeled as an assumption when none is supplied.
- Do not invent measured data, benchmarks, or citations. Do not claim to have consulted specific sources unless they were actually provided or retrieved.
- Keep each rationale brief, typically 1–2 sentences.
- Before returning, check that each rationale supports the assigned weight through expected frequency and human effort per occurrence, and describes only the work included in that subtask. Do not justify weights using phrases such as "important," "integral," or "frequency varies."

Output:
Return only the requested JSON object, conforming to the supplied output schema.
Include relative_effort_weight and effort_rationale for each subtask. When bottom-up estimates are returned, relative_effort_weight is derived by the application from expected effort per parent output.
No readiness analysis, implementation plans, recommendations, transformation commentary, scoring, or accounting.
""".strip()

OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT = """
Repair the supplied JSON operational decomposition using the supplied semantic validation feedback and the original task context.

Repair Scope:
- Return the same JSON schema with no extra metadata.
- Follow the operational decomposition rules used to generate the original response.
- Preserve task identity and all valid effort_rationale values, unaffected subtasks, IDs, ordering, dependencies, and relative_effort_weight values.
- Apply the smallest correction needed to resolve the validation findings. Change related fields or dependent references only when necessary to keep the decomposition consistent.
- Do not alter unrelated items, add unsupported activities, or over-decompose work.
- Preserve existing IDs where possible. If structural changes are necessary, keep IDs unique, sequence contiguous and 1-based, and dependencies limited to exact IDs of earlier subtasks.

Activity Requirements:
- Every subtask must represent a meaningful, concrete human activity, including physical work, system interaction, communication, investigation, analysis, evaluation, or decision-making.
- Specify what is performed, reviewed, evaluated, determined, recorded, or communicated.
- Ensure each subtask name matches its description.
- Distinguish checking for a condition from additional work performed when that condition is present.
- Reject goals, states, outcomes, and vague completion labels. Keep names and descriptions concise.
- Ground boundaries in distinct operational activities suitable for independent automation evaluation, without favoring an automation outcome.
- Do not assess automation feasibility or assign RETAIN/REMOVE classifications.

Effort Requirements:
- Ensure every subtask has a positive, unnormalized relative_effort_weight on a consistent relative scale, not expressed in hours or percentages.
- Estimate expected baseline human effort as typical occurrences per parent task × relative human effort per occurrence.
- Account for complexity, coordination, and information availability in effort per occurrence, and conditional frequency in expected occurrences. Do not double-count workload.
- Do not use business importance, risk, or decision authority as proxies for effort.
- Ensure every subtask has a concise effort_rationale explaining the main frequency and effort-per-occurrence assumptions, distinguishing supplied facts from model estimates.
- If a correction changes an activity's scope, frequency, or effort requirements, update its weight and rationale together as needed.
- Do not require absolute units or invent measured data, benchmarks, citations, or claims of source consultation.
- Preserve any valid parent output contract and baseline effort estimates. If estimates are present, keep one estimate per operational subtask, use pre-AI scope only, and do not independently invent the calculated expected-effort product.

Output:
Return only the repaired JSON object conforming to the supplied output schema.
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

ADDED_WORK_PROMPT = """
Identify genuinely new human work caused by automating baseline subtasks classified REMOVE. For each REMOVE subtask, assess incremental AI_INTERACTION and AI_VERIFICATION needs, including routine oversight, exceptions, missing inputs, ambiguity, failures, and rework. A removed subtask does not necessarily create added work; `added_work_rows` may be empty.

- Identity: Copy the supplied task exactly. Use only frozen subtask IDs; never invent, rename, omit, duplicate, or remap them.
- Categories: AI_INTERACTION covers human prompting, guidance, intervention, retrying, and troubleshooting during execution. AI_VERIFICATION covers human inspection, validation, correction, and approving AI-generated outputs. Use no other categories.
- Scope: Include only incremental human work during transformed workflow execution. Exclude existing RETAIN work, downstream activities, system implementation, deployment, infrastructure or model maintenance, passive AI waiting time, and other passive waiting. Do not reclassify baseline work as added work.
- Parent boundary: keep added work within the original parent-task output. Treat downstream roles and later decisions as context only; do not include downstream adjudication, final decisions, settlement, or later-process execution unless the parent task explicitly owns them.
- Coverage & Consolidation: Assess every REMOVE subtask, but emit only distinct necessary activities. Combine overlapping work across subtasks to avoid double counting; separate activities with materially different triggers, frequencies, or human actions. List all causal REMOVE IDs in `source_removed_subtask_ids`.
- Effort Reference: Select exactly one comparable baseline `reference_subtask_id` (RETAIN or REMOVE) or `external_reference` per row. Match the added activity's scope, action, complexity, and frequency; avoid arbitrarily narrow references. Do not automatically sum causal subtasks. External references require a quantitative `effort_per_occurrence` anchor; otherwise leave the estimate noncomputable.
- Estimation: Provide low/typical/high values for `occurrences_per_parent_execution` and `relative_effort_per_occurrence`. For baseline references, also estimate `reference_occurrences_per_parent_execution`; do not assume one without justification. Reflect conditional frequencies and use measured/documented evidence when available; otherwise use `estimate_basis="assumed"`. Never fabricate evidence or benchmarks.
- Rationale: In ≤40 words per row, explain the trigger, frequency, reference choice, relative effort, and key assumptions.
- Output: Return the complete structured object with top-level `task`, `added_work_rows`, and `provenance_refs` ([] if unavailable). Give each row a stable work ID and concise activity name. Set optional descriptions, dependencies, sequence indexes, and row provenance to empty/null unless needed.
- Accounting: Return estimates only. Do not calculate W0, W1, accounting amounts, substitution, augmentation, effects, or readiness metrics; Python owns all calculations.
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
- If normalized accounting has no supplied absolute baseline, provide an auditable estimated baseline effort per parent output with rationale and assumptions. A supplied baseline takes precedence in application accounting.
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
    "ADDED_WORK_PROMPT",
    "AGENTIC_TASK_SYNTHESIS_PROMPT",
    "HUMAN_AGENT_ACTIVITY_MODELING_PROMPT",
    "OPERATIONAL_DECOMPOSITION_PROMPT",
    "OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT",
    "RETAIN_REMOVE_PROMPT",
    "SEMANTIC_EVALUATION_PROMPT",
]
