"""Shared semantic instructions for concrete provider adapters."""

from task_decomposition.evaluation.rubric import (
    SEMANTIC_EVALUATION_RUBRIC,
    SEMANTIC_EVALUATION_RUBRIC_VERSION,
)

OPERATIONAL_DECOMPOSITION_PROMPT = """
Decompose the supplied business task into concrete, distinct operational human subtasks. Return only the requested structured object.

Each subtask must describe a reasonable unit of time-consuming work that a human could perform. This includes physical work, system interaction, communication, information processing, investigation, analysis, evaluation, judgment, and decision-making. Cognitive work is valid when it says what is being reviewed, compared, evaluated, or determined.

Do not use a label that merely states a goal, state, outcome, or completion result; "Make approval decision" is too abstract, while "Determine whether the invoice meets approval criteria" identifies the work. Do not split one reasonable decision into trivial micro-steps solely to make it sound operational. Preserve the task identity supplied by the caller. Use stable short subtask IDs and a 1-based contiguous sequence. Dependencies may reference only earlier subtasks.

Keep each subtask name and description concise: state the observable human work and its object or decision in one short sentence. Use empty dependency and provenance arrays unless needed; do not add rationale or metadata.

For each subtask, provide a positive relative_effort_weight representing its effort compared with the other subtasks. Use an unnormalized numeric weight; do not estimate hours or percentages. Keep weights comparable across the complete decomposition.

Return a JSON structured object only. Do not return readiness or suitability analysis, implementation plans, generic recommendations, transformation commentary, scoring, or final accounting. Do not invent authoritative effort values.
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
Classify each validated operational subtask as RETAIN or REMOVE. Preserve all supplied subtask IDs, ordering, and task identity. Do not add, merge, reorder, or regenerate subtasks.
- Classification Rules: RETAIN = baseline human work remains human-performed; REMOVE = human work is removed or delegated by the transformation.
- JSON Output Rules: Include only subtask_id and classification for each row. Set subtask_name, sequence_index, effort, baseline_effort_ratio, rationale, and optional task fields to null. Set provenance_refs to an empty array [].
- Strictly Prohibited: No explanations, text outside JSON, metric calculations (W0, W1, substitution, augmentation, effect), or fabricated effort data.
""".strip()

ADDED_WORK_PROMPT = """
Identify new human work introduced by the transformed process. Return only added-work rows in a JSON object, separate from baseline RETAIN/REMOVE subtasks.
- Valid Categories Only: GOVERNANCE (oversight, control, audit, policy, approval), OPERATIONAL_SUPPORT (monitoring, review, verification, exception, escalation, support), LIFECYCLE_SUPPORT (maintenance, updates, retraining, templates, rules, administration).
- Subtask Rules: Provide a stable work ID and concise concrete name for each row. Do not disguise added work as RETAIN/REMOVE rows.
- Schema & Data Rules: Leave amount unset unless caller supplies explicit accounting inputs. Set optional descriptions, dependencies, sequence_index, and provenance_refs to empty/null values unless needed for disambiguation.
- Prohibited: Do not calculate W0, W1, substitution, augmentation, effect, or readiness metrics.
""".strip()

SEMANTIC_EVALUATION_PROMPT = f"""
Evaluate the complete operational decomposition in the supplied input JSON against the rubric below. Return only the structured evaluation object.

Rubric Rules:
- Apply RUBRIC VERSION: {SEMANTIC_EVALUATION_RUBRIC_VERSION}.
- Evaluate the decomposition holistically against the original task, description, and context.
- Output Rules: No hidden reasoning, narrative outside JSON, or numerical quality scores. Set evaluator provenance to null.
- Finding Format: Findings must be concise and actionable. Include subtask_id (if applicable), a short message, and evidence only when clarifying a defect.

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
