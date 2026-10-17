"""Shared semantic instructions for concrete provider adapters."""

from task_decomposition.evaluation.rubric import (
    SEMANTIC_EVALUATION_RUBRIC,
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
)

OPERATIONAL_DECOMPOSITION_PROMPT = """
Objective:
Decompose the supplied business task into concrete, distinct human activities that can each be independently evaluated for complete automation using current AI capabilities.

Decomposition Rules:
- Each subtask must represent a meaningful unit of human work, including physical work, system interaction, communication, investigation, analysis, evaluation, or decision-making.
- Specify what is performed, reviewed, evaluated, or determined.
- Separate distinct operational activities without trivial microsteps or unnecessary fragmentation.
- Describe activities, not goals, outcomes, or completion states.
- Do not assess automation feasibility or assign RETAIN/REMOVE classifications.
- Include only activities necessary or reasonably implied by the supplied task objective. Do not add documentation, monitoring, feedback, or follow-up activities merely to make the decomposition appear complete.

Subtask Structure:
- Preserve task identity. Use stable short subtask IDs and a contiguous 1-based sequence.
- Dependencies may reference only earlier subtasks.
- Keep names and descriptions concise, stating the activity and its object or decision.
- Use empty dependency and provenance arrays unless needed; omit rationale and unnecessary metadata.

Relative Effort Estimation:
- Assign each subtask a positive relative_effort_weight based on its estimated share of baseline human working time.
- Consider typical duration, frequency, and workload volume.
- Use supplied operational data or empirical benchmarks when available; otherwise rely on reasonable occupational estimates.
- Relevant sources include O*NET, occupational time-use studies, and industry productivity benchmarks.

Output:
Return only the requested JSON object. No readiness analysis, implementation plans, recommendations, transformation commentary, scoring, or accounting.
""".strip()

OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT = """
Repair the supplied JSON operational decomposition following semantic validation.
- Return the identical JSON schema with no extra metadata or rationale.
- Preserve task identity, valid subtasks, IDs, sequence, dependencies, and valid existing relative_effort_weight values.
- Apply the minimal correction to rejected subtasks only; do not alter unrelated items or over-decompose work.
- Every subtask must be a concrete human-executable action (e.g., physical tasks, system interaction, analysis, specific decisions) specifying what is reviewed, determined, recorded, or communicated.
- Reject goals, states, outcomes, or vague completion labels. Keep names and descriptions concise.
- Ensure every subtask has a positive, unnormalized relative_effort_weight (no hours or percentages).
""".strip()

RETAIN_REMOVE_PROMPT = """
Classify each operational subtask as RETAIN or REMOVE based on automation potential using current AI-enabled technology, including software integrations, workflow automation, and optimization tools.

Preserve task identity, subtask IDs, and ordering. Do not modify the decomposition.

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
- Include only subtask_id and classification for each row.
- Set subtask_name, sequence_index, effort, baseline_effort_ratio, rationale, and optional task fields to null.
- Set provenance_refs to [].

Return only the requested JSON. No explanations, calculations, or fabricated effort data.
""".strip()

ADDED_WORK_PROMPT = """
Identify only genuinely new human activities introduced by AI during transformed workflow execution. Preserve the baseline RETAIN/REMOVE distinction: do not classify existing baseline work as added merely because AI is involved, and do not invent work to populate categories.
- Valid Categories Only: AI_INTERACTION (instructing, guiding, clarifying, intervening in, redirecting, retrying, or otherwise interacting with AI during execution); AI_VERIFICATION (inspecting, validating, correcting, or approving AI-generated outputs).
- Exclude AI system design, implementation, deployment, technical documentation development, guardrail construction, and infrastructure or model maintenance performed outside individual workflow executions. Include genuinely new human intervention, troubleshooting, or verification required during transformed workflow execution under AI_INTERACTION or AI_VERIFICATION, as appropriate. Exclude passive AI waiting time from human effort.
- Subtask Rules: Provide a stable work ID and concise concrete name for each genuinely new row. Do not create a separate exception-handling or governance category, and do not disguise added work as RETAIN/REMOVE rows. `added_work_rows` may be empty.
- Complete Response Rules: Return the complete structured object with top-level `task`, `added_work_rows`, and `provenance_refs`. Set top-level `provenance_refs` to [] when unavailable.
- Schema & Data Rules: Leave amount unset unless caller supplies explicit accounting inputs. Set optional descriptions, dependencies, sequence_index, and row provenance_refs to empty/null values unless needed for disambiguation.
- Prohibited: Do not calculate W0, W1, substitution, augmentation, effect, or readiness metrics.
""".strip()

SEMANTIC_EVALUATION_PROMPT = f"""
Evaluate the complete operational decomposition in the supplied input JSON against the rubric below. Return only the structured evaluation object.

Decision Rules:
- Apply RUBRIC VERSION: {SEMANTIC_EVALUATION_RUBRIC_VERSION}.
- Evaluate the decomposition holistically against the original task, description, and context.
- Accept an operationally complete and executable decomposition; optional wording or specificity improvements are suggestions only.
- Use repair only for a material actionable defect that prevents reliable execution and is correctable without redesigning the decomposition.
- Use reject whenever any finding is blocking; use repairable findings only when no blocking finding exists.
- Blocking findings are limited to missing required operational activities, non-operational subtasks, materially ambiguous activity boundaries, or overlapping/fragmented activities that prevent meaningful independent automation assessment.
- Do not treat missing exception handling, procedural methods, decision criteria, prioritization rules, algorithms, or optional specificity as blocking unless the original task explicitly requires them as distinct activities.
- Evaluate the completeness and quality of the activity decomposition, not whether each activity contains executable procedures.
- Judge completeness against activities explicitly required or directly implied by the supplied task, not generic domain expectations.
- Count a required activity as covered when a subtask names its core action and object. Do not report an activity as missing merely because the subtask omits stakeholder lists, qualifiers, communication channels, or downstream decision consequences.
- Before reporting a missing activity, check all existing subtasks for the same operational action and object using semantic equivalence, not exact wording or a predefined workflow.
- Do not require additional feedback, monitoring, follow-up, exception handling, or procedural activities unless the supplied task requires them.
- Treat a materially unsupported responsibility as a blocking scope defect, not automatically as an internal meta-task. Operational documentation is legitimate when the supplied task requires recording a business result, decision, or record; documentation of methodologies or work merely for future reference is out of scope unless explicitly required.
- Do not infer missing feedback, monitoring, follow-up, or issue-resolution activities from communication, scheduling, or execution activities unless the original task requires that additional responsibility.
- Do not issue a repair finding merely to add progress reporting, feedback, adjustment criteria, or procedural detail when the core operational action and object are already identifiable.
- For example, a production-scheduling activity may create a feasible schedule without specifying material-shortage procedures, a conflict-resolution activity may identify and address conflicts without specifying a resolution algorithm, and informing production teams of the finalized schedule covers the communication activity without enumerating every stakeholder; these remain acceptable activities.
- Gathering feedback from production teams is also a valid distinct activity without requiring the decomposition to state how that feedback changes later scheduling decisions.
- If the supplied task does not mention monitoring schedule execution, a separate monitoring activity is out of scope; do not invent it as a missing requirement or demand its procedures.
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
