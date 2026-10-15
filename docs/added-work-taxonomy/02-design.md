# Added-Work Taxonomy Design

## Categories

- `AI_INTERACTION`: new human effort to instruct, guide, clarify, intervene in, redirect, retry, or otherwise interact with AI during transformed workflow execution.
- `AI_VERIFICATION`: new human effort to inspect, validate, correct, or approve AI-generated outputs.

These are execution-level categories for this repository. They are informed by the METR study's activity-based measurement of how people spend time while working with AI, but they are not categories formally defined by METR. See the [METR study](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf).

## Boundaries

Classify only work genuinely introduced by AI. Existing baseline work remains in RETAIN/REMOVE classification even when AI participates in it. Do not invent rows to populate either category. AI-related retries and interventions are `AI_INTERACTION`; output checking, corrections, and approvals are `AI_VERIFICATION`.

Exclude AI system design, implementation, deployment, documentation development, guardrail construction, ongoing system maintenance, and passive AI waiting time. There is no separate exception-handling or governance category. `added_work_rows` may be empty.

## Contract and accounting boundary

The complete provider response contains `task`, `added_work_rows`, and `provenance_refs`; unavailable top-level provenance is `[]`. The canonical Pydantic models remain provider-independent.

The accounting contract uses `SupportWorkInputs.ai_interaction` and `SupportWorkInputs.ai_verification`. Derived rows aggregate independently into those fields, and `CanonicalTransformationImpact` exposes `ai_interaction_work` and `ai_verification_work`. Their sum is `added_human_work`; explicit inputs remain authoritative over inferred rows. The legacy governance, operational-support, and lifecycle-support fields are intentionally removed from this repository's active contracts.
