"""Shared semantic instructions for concrete provider adapters."""

OPERATIONAL_DECOMPOSITION_PROMPT = """
Decompose the supplied business task into concrete, distinct operational
human subtasks. Return only the requested structured object.

Each subtask must describe a reasonable unit of time-consuming work that a
human could perform. This includes physical work, system interaction,
communication, information processing, investigation, analysis, evaluation,
judgment, and decision-making. Cognitive work is valid when it says what is
being reviewed, compared, evaluated, or determined. Do not use a label that
merely states a goal, state, outcome, or completion result; "Make approval
decision" is too abstract, while "Determine whether the invoice meets approval
criteria" identifies the work. Do not split one reasonable decision into
trivial micro-steps solely to make it sound operational. Preserve the task
identity supplied by the caller. Use stable short subtask IDs and a 1-based
contiguous sequence. Dependencies may reference only earlier subtasks.

Return a JSON structured object only. Do not return readiness or suitability analysis, implementation plans, generic
recommendations, transformation commentary, scoring, or final accounting.
Do not invent authoritative effort values.
""".strip()

OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT = """
Repair the supplied structured operational decomposition after semantic
validation. Return the same JSON schema. Preserve the task identity and all
already-valid subtasks, IDs, ordering, and dependencies where practical. Make
the smallest necessary correction to each rejected subtask; do not regenerate
unrelated content or over-decompose a reasonable unit of work.

Every subtask must be a reasonable, distinct unit of time-consuming operational
work that a human could perform. Physical work, system interaction,
communication, information processing, investigation, analysis, evaluation,
judgment, and sufficiently specific decision-making are all valid. A state,
goal, outcome, completion label, or vague abstraction is not valid. Describe
what the worker actually reviews, determines, records, communicates, or does.
""".strip()

RETAIN_REMOVE_PROMPT = """
Classify each validated operational subtask exactly once as RETAIN or REMOVE.
Preserve every supplied subtask ID and do not add, merge, reorder, or
regenerate subtasks. RETAIN means the baseline human work remains performed;
REMOVE means that baseline human work is removed or delegated by the proposed
transformation.

Return only the requested JSON structured object. Do not calculate W0, W1,
substitution, augmentation, effect, or any other accounting metric. Leave
effort fields empty unless the caller explicitly supplies authoritative effort
data; never fabricate effort to make accounting reconcile.
""".strip()

ADDED_WORK_PROMPT = """
Identify new human work introduced by operating the transformed process.
Return only added-work rows in a JSON structured object, separate from baseline RETAIN/REMOVE subtasks.
Use only these categories: GOVERNANCE (oversight, control, audit, policy, or
approval), OPERATIONAL_SUPPORT (monitoring, review, verification, exception,
escalation, or day-to-day support), and LIFECYCLE_SUPPORT (maintenance,
updates, retraining, templates, rules, or recurring lifecycle administration).

Give each row a stable work ID and concrete work name. Amounts are not provider
authority: leave the amount unset unless explicit accounting inputs are supplied
by the caller. Do not calculate W0, W1, substitution, augmentation, effect, or
readiness. Added work must not be disguised as a RETAIN or REMOVE row.
""".strip()

__all__ = [
    "ADDED_WORK_PROMPT",
    "OPERATIONAL_DECOMPOSITION_PROMPT",
    "OPERATIONAL_DECOMPOSITION_REPAIR_PROMPT",
    "RETAIN_REMOVE_PROMPT",
]
