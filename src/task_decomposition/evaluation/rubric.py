"""Versioned, provider-neutral semantic evaluation rubric."""

SEMANTIC_EVALUATION_RUBRIC_VERSION = "1.0"

SEMANTIC_EVALUATION_RUBRIC = """
Evaluate the complete operational decomposition in the context of the
original task, task description, and supplied context.

A valid decomposition describes a reasonable set of distinct units of
operational work that a person can perform and that consume non-zero human
time. Work may be physical, system-based, communicative, informational,
analytical, evaluative, judgment-based, or decision-making. Planning,
scheduling, drafting, outlining, researching, and creating a deliverable are
legitimate cognitive or creative work when the decomposition makes the work
understandable in context.

Consider the decomposition as a whole:

1. Each subtask should describe meaningful work rather than only a goal,
   state, status, or outcome.
2. Subtasks should be distinct, collectively relevant to the original task,
   and at an appropriate granularity. Do not require further decomposition
   merely because a broad subtask could be split further.
3. Identify material overlap, duplication, missing work, or fragmentation.
4. Internal decomposition, meta-analysis, rationale-generation, or evaluator
   activities are not business work unless the original task explicitly makes
   that activity the business task.
5. Evaluate the completeness and quality of the activity decomposition, not
   whether each activity contains an executable procedure. Do not require
   exception handling, procedural methods, decision criteria, prioritization
   rules, algorithms, or other optional specificity unless the original task
   explicitly requires them as distinct activities.
6. Distinguish material decomposition defects from optional improvements.
   Wording,
   specificity, and presentation improvements are suggestions and must not
   prevent acceptance. Procedural detail is also optional unless explicitly
   required by the original task.
7. Judge completeness against activities explicitly required or directly
   implied by the supplied task, not against generic domain expectations.
   A subtask covers a requirement when its core operational action and object
   are identifiable.
   Before reporting a missing activity, check every existing subtask for the
   same operational action and object using semantic equivalence, not exact
   wording or a predefined workflow.
8. Do not require additional feedback, monitoring, follow-up, exception
   handling, or procedural activities unless the supplied task requires them.
   Treat a materially unsupported responsibility as a blocking scope defect,
   not automatically as an internal meta-task. Operational documentation is
   legitimate when the supplied task requires recording a business result,
   decision, or record; documentation of methodologies or work merely for
   future reference is out of scope unless explicitly required.
   Do not issue a repair finding merely to add progress reporting, feedback,
   adjustment criteria, or procedural detail when the core operational action
   and object are already identifiable.

Severity boundary:
- Blocking findings are limited to missing required operational activities,
  non-operational subtasks, materially ambiguous activity boundaries, or
  overlapping/fragmented activities that prevent meaningful independent
  automation assessment. A materially out-of-scope responsibility that
  expands the supplied task boundary is also blocking and must be rejected.
- Missing exception handling, methods, criteria, prioritization rules,
  algorithms, or edge-case procedures is non-blocking unless the original
  task explicitly identifies that work as a required distinct activity.
- Count a required activity as covered when a subtask names its core action
  and object. Do not report an activity as missing merely because the subtask
  omits stakeholder lists, qualifiers, communication channels, or downstream
  decision consequences.
- Before reporting a missing activity, check whether an existing subtask
  already performs that action on that object, even if it uses different
  wording or combines the action with an adjacent operational phrase.
- Do not infer a missing feedback, monitoring, follow-up, or issue-resolution
  activity from a communication, scheduling, or execution activity unless the
  original task requires that additional responsibility.

Decision guidance:

- accept: the decomposition is operationally complete and executable;
  suggestions are permitted.
- repair: a material, actionable defect prevents reliable execution but can be
  corrected while preserving the useful decomposition; include repairable
  findings and no blocking findings.
- reject: a fundamental blocking defect makes the decomposition unsuitable;
  include at least one blocking finding.

Severity precedence is mandatory: suggestions alone produce accept; one or
more repairable findings without blocking findings produce repair; any
blocking finding produces reject. Do not use repair for optional wording,
specificity, or presentation improvements, and do not require additional
decomposition merely to improve them.

Examples:

- Invoice review: reviewing an invoice against a purchase order, determining
  whether it meets approval criteria, recording the decision, and notifying a
  requester can each be legitimate work when relevant to the task.
- Customer onboarding: collecting required customer information, validating
  submitted details, configuring the account, and communicating next steps
  can be distinct operational units when the task requires them.
- Pure outcome: "Invoice approved" describes a result, not the work of
  evaluating or recording that result, and is a material defect.
- Internal meta-task: "Generate decomposition rationale" describes internal
  analysis rather than business work and is a policy defect unless that is
  explicitly the original task.
- Overlap: two subtasks that perform the same review should be identified as
  overlapping; missing work should be identified when the decomposition does
  not cover a material part of the original task.
- Production scheduling: "Create a feasible production schedule based on
  reviewed orders, inventory, machine capacity, and workforce availability"
  is a sufficient activity description without specifying shortage procedures.
- Production scheduling: "Identify and address conflicts in the proposed
  production schedule" is a sufficient activity description without naming a
  resolution algorithm or decision criteria.
- Production scheduling: "Inform production teams of the finalized production
  schedule" covers the required communication activity; do not report it as
  missing because the row does not enumerate every stakeholder.
- Production scheduling: gathering feedback from production teams is a valid
  distinct activity; do not require the decomposition to state how that
  feedback changes later scheduling decisions.
- Production scheduling: if the supplied task does not mention monitoring
  schedule execution, a separate "monitor execution" activity is out of
  scope; do not invent it as a missing requirement or demand its procedures.
- Production scheduling: an existing activity to monitor production, adjust a
  schedule, or communicate a schedule is sufficient at the activity level;
  do not repair it solely to add progress reporting, feedback, adjustment
  criteria, or execution procedures.
- Genuine blocking omission: if a task explicitly requires communicating the
  finalized schedule and no communication activity appears, that missing activity
  is blocking; the existing scheduling activities do not need to enumerate
  communication procedures.

Do not use keyword matching, an operational-verb allowlist, a numerical
quality score, or a requirement that every subtask produce a physical or
externally visible action. Use contextual judgment and return only concise,
observable findings.
""".strip()


__all__ = [
    "SEMANTIC_EVALUATION_RUBRIC",
    "SEMANTIC_EVALUATION_RUBRIC_VERSION",
]
