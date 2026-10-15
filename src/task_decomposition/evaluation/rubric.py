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
5. Distinguish material execution defects from optional improvements. Wording,
   specificity, and presentation improvements are suggestions and must not
   prevent acceptance.

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

Do not use keyword matching, an operational-verb allowlist, a numerical
quality score, or a requirement that every subtask produce a physical or
externally visible action. Use contextual judgment and return only concise,
observable findings.
""".strip()


__all__ = [
    "SEMANTIC_EVALUATION_RUBRIC",
    "SEMANTIC_EVALUATION_RUBRIC_VERSION",
]
