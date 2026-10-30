"""Versioned, provider-neutral semantic evaluation rubric."""

SEMANTIC_EVALUATION_RUBRIC_VERSION = "1.3"
TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION = "1.0"

SEMANTIC_EVALUATION_RUBRIC = """
Evaluate whether the supplied operational decomposition adequately represents the work required by the original task, at a granularity suitable for independent automation assessment.

Authority and scope:
- Evaluate the assigned operational responsibility in the supplied task, description, and context. Do not design an ideal workflow, infer a broader business objective, or prescribe a preferred sequence of activities.
- Accept reasonable alternative decompositions and levels of granularity. Subtasks may be physical, system-based, communicative, informational, analytical, evaluative, judgment-based, or decision-making work.
- A subtask is operational when it identifies meaningful work performed by a person or system and is not merely a goal, status, outcome, rationale, or evaluator instruction. Internal decomposition or methodology documentation is not business work unless the original task explicitly requires it. Documentation of a required business result, decision, or record is operational work.

Coverage and boundaries:
- Judge completeness against activities explicitly required by the assigned task or operationally necessary to perform that task. Do not infer additional responsibilities from generic domain expectations, broader business objectives, or optional upstream or downstream work.
- When a subtask plausibly represents work within the assigned responsibility, presume it is acceptable unless a demonstrable defect prevents independent automation assessment.
- A requirement is covered when an existing subtask identifies its core action and object. Check all subtasks for semantic equivalence before reporting an omission; do not require exact wording, a predefined workflow, or a particular granularity.
- Do not require procedures, exception handling, feedback, monitoring, follow-up, decision criteria, prioritization, algorithms, or stakeholder details unless the original task requires that work as a distinct activity.
- Flag an unsupported responsibility only when it materially expands the task boundary. Do not add activities merely to make the decomposition appear complete.
- Treat downstream roles, handoffs, or later decisions mentioned as context as outside the parent-task boundary unless the assigned task explicitly owns their execution. A handoff to an adjuster does not include the adjuster's later adjudication or final decision.
- Identify material overlap, duplication, fragmentation, or ambiguity only when the boundary prevents meaningful independent automation assessment.

Effort plausibility and transparency:
- Treat `relative_effort_weight` as a provider-generated estimate of each subtask's share of baseline human effort; Python performs the authoritative normalization.
- Assess whether all subtasks use one parent-output denominator and whether each rationale separates expected occurrences from active human effort per occurrence.
- Check that conditional, repeated, and rework activities are represented through expected occurrences rather than an assumption that every subtask runs once.
- Check that internal workload is represented once and that external parent-output volume, passive waiting, queueing, and unattended processing are not treated as subtask effort.
- Assess whether the relative weights are directionally plausible for the described work and whether each `effort_rationale` makes its frequency and effort-per-occurrence assumptions transparent, including the parent output, complexity, and information-availability assumptions.
- Flag language that treats normalized relative weights as minutes, hours, elapsed time, FTE, capacity, or measured absolute effort.
- Flag unsupported precision or assumptions presented as measured facts, while accepting approximate or qualitative estimates when their basis is clear.
- When a rationale gives frequency or occurrence assumptions and effort-per-occurrence comparisons, check that their implied ordering is consistent with the relative weights. Flag material contradictions, such as a frequently occurring and effort-intensive activity receiving a much smaller weight without an explanation.
- Accept qualitative or approximate assumptions. Do not require absolute minutes, hours, workload volumes, external benchmark retrieval, citations, formal calibration scales, or numeric frequency ranges.
- Distinguish supplied operational facts from model-generated estimates and assumptions. Do not treat an unverified benchmark claim or citation as required evidence.

Severity and decision boundary:
- Suggestions cover wording, specificity, presentation, and other optional improvements; they do not prevent acceptance.
- Repairable findings are material, actionable defects that can be corrected locally while preserving the useful decomposition. Examples include vague or non-operational descriptions whose intended activities are recoverable, or missing required activities that can be reliably added without substantial redesign.
- Blocking findings are material defects that prevent reliable independent automation assessment and cannot be resolved through local repair. A missing activity is blocking only when the task explicitly assigns it or the assigned task cannot be performed without it, and no existing subtask covers it. Other examples include non-operational subtasks, ambiguous boundaries, excessive overlap or fragmentation, or materially out-of-scope responsibilities. Classify a defect as blocking only when its correction cannot be reliably determined from the supplied task and decomposition without substantial redesign.
- Accept when the decomposition is operationally sufficient, even if it could be improved. Use repair only for repairable findings. Reserve reject for blocking findings. Do not make a finding blocking merely because more detail would be useful.

Return concise, observable findings. Do not use keyword matching, an operational-verb allowlist, numerical quality scores, or a requirement that every subtask produce a physical or externally visible action. Do not reject a decomposition solely because an effort estimate is approximate when its assumptions are transparent and directionally coherent.
""".strip()

TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC = """
Evaluate the complete transformation of the frozen baseline decomposition against
the original task and parent-output contract. Do not redesign the baseline, change
accounting, or require human involvement where the supplied context supports
autonomous execution.

Evaluate these criteria and report the criterion in every finding:
- HUMAN_RESPONSIBILITY_COMPLETENESS (high): retain necessary authorization,
  approval, management judgment, exception resolution, escalation decisions, and
  required oversight. Distinguish deciding from communicating or recording.
- DOUBLE_COUNTING (high): identify duplicated effort across retained subtasks,
  added human-agent activities, or multiple activities. Accept genuinely separate
  verification and incremental intervention.
- TASK_BOUNDARY (high): keep transformed responsibilities and human activities
  within the original parent-output contract, completion boundary, and exclusions.
  Exclude downstream work outside that boundary.
- ACTIVE_HUMAN_EFFORT (medium): effort must be active human work, excluding passive
  waiting, external delays, autonomous AI execution, and machine processing.
- OCCURRENCE_ASSUMPTIONS (medium): expected occurrences must fit activity triggers
  and stated assumptions. Accept reasonable model-generated planning assumptions
  without empirical evidence; flag contradictions, unsupported precision, or
  clearly implausible frequencies.

Use concise, observable findings. Include affected references using the supplied
IDs when applicable. Suggestions are nonblocking; repairable findings are material
local defects; blocking findings prevent reliable evaluation. Do not recalculate
W0 or W1, duplicate deterministic validation, or propose automatic repairs.
""".strip()


__all__ = [
    "SEMANTIC_EVALUATION_RUBRIC",
    "SEMANTIC_EVALUATION_RUBRIC_VERSION",
    "TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC",
    "TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION",
]
