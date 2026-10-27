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

Relative Effort Estimation:
- Assign each subtask a positive relative_effort_weight proportional to its expected baseline human effort per parent task.
- Estimate expected effort as typical occurrences per parent task × relative human effort per occurrence.
- Estimate effort per occurrence from the work involved, including complexity, coordination, and information availability. Account for exception frequency in expected occurrences.
- Use a consistent parent-task workload basis; do not double-count volume or effort across subtasks, or assume conditional activities occur every time.
- Use supplied operational facts when available; otherwise make reasonable occupational estimates informed by general knowledge, frameworks such as O*NET, and relevant industry practices.
- Use a consistent relative scale across all subtasks; the application performs authoritative normalization.
- Do not require absolute minutes, hours, or workload volumes from the user.
- Do not use business importance, risk, or decision authority as proxies for human effort.

Effort Rationale:
- Provide a concise rationale for each subtask's relative_effort_weight.
- Explain the main frequency and effort-per-occurrence assumptions, including relevant complexity, coordination, or information availability factors.
- Distinguish supplied operational facts from model-generated estimates and assumptions.
- State the assumed occurrence frequency clearly. For conditional work, provide an approximate frequency or range labeled as an assumption when none is supplied.
- Do not invent measured data, benchmarks, or citations. Do not claim to have consulted specific sources unless they were actually provided or retrieved.
- Keep each rationale brief, typically 1–2 sentences.
- Before returning, check that each rationale supports the assigned weight through expected frequency and human effort per occurrence, and describes only the work included in that subtask. Do not justify weights using phrases such as "important," "integral," or "frequency varies."

Output:
Return only the requested JSON object, conforming to the supplied output schema.
Include relative_effort_weight and effort_rationale for each subtask.
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
- Categories: AI_INTERACTION covers human prompting, guidance, intervention, retries, and troubleshooting during execution. AI_VERIFICATION covers human inspection, validation, correction, and approval of AI outputs. Use no other categories.
- Scope: Include only incremental human work during transformed workflow execution. Exclude existing RETAIN work, downstream activities, system development, deployment, maintenance, and passive waiting. Do not reclassify baseline work as added work.
- Coverage & Consolidation: Assess every REMOVE subtask, but emit only distinct necessary activities. Combine overlapping work across subtasks to avoid double counting; separate activities with materially different triggers, frequencies, or human actions. List all causal REMOVE IDs in `source_removed_subtask_ids`.
- Effort Reference: Select exactly one comparable baseline `reference_subtask_id` (RETAIN or REMOVE) or `external_reference` per row. Match the added activity's scope, action, complexity, and frequency; avoid arbitrarily narrow references. Do not automatically sum causal subtasks. External references require a quantitative `effort_per_occurrence` anchor; otherwise leave the estimate noncomputable.
- Estimation: Provide low/typical/high values for `occurrences_per_parent_execution` and `relative_effort_per_occurrence`. For baseline references, also estimate `reference_occurrences_per_parent_execution`; do not assume one without justification. Reflect conditional frequencies and use measured/documented evidence when available; otherwise use `estimate_basis="assumed"`. Never fabricate evidence or benchmarks.
- Rationale: In ≤40 words per row, explain the trigger, frequency, reference choice, relative effort, and key assumptions.
- Output: Return the complete structured object with `task`, `added_work_rows`, and `provenance_refs` ([] if unavailable). Give each row a stable work ID and concise activity name. Leave optional descriptions, dependencies, sequence indexes, and row provenance empty/null unless needed.
- Accounting: Return estimates only. Do not calculate W0, W1, accounting amounts, substitution, augmentation, effects, or readiness metrics; Python owns all calculations.
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
    "ADDED_WORK_PROMPT",
    "OPERATIONAL_DECOMPOSITION_PROMPT",
    "OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT",
    "RETAIN_REMOVE_PROMPT",
    "SEMANTIC_EVALUATION_PROMPT",
]
