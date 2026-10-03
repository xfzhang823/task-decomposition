# S4B Semantic and Process Validation

## Benchmark corpus

`benchmarks/processes.json` contains 11 realistic processes: customer support ticket handling, insurance claims, invoice/AP processing, software bug triage, sales lead qualification, employee onboarding, commercial contract review, medical appointment scheduling, manufacturing quality inspection, wealth-management onboarding, purchase-order exception handling, and IT access fulfillment.

The cases cover routine, judgment-heavy, mixed human/system, sequential, dependent, compliance-sensitive, approval, and exception-heavy work. Each case defines process context, a concrete transformation description, a broad task-count range, required work signals, normally retained human-work signals, and a broad expected net-substitution range.

The definitions are evaluation assets only. They do not introduce scenarios, simulations, Monte Carlo, grid search, or alternative-management architecture.

## Evaluation criteria

Hard validity and semantic quality are separate.

Hard validity checks machine-verifiable conditions: stage contract validity, task identity, classification coverage, duplicate identities, dependency integrity, baseline allocation coverage, weight normalization, positive W0, nonnegative W1, accounting identities, and effect consistency.

Semantic review signals cover task count, required work-term coverage, duplicate task names, effort-weight visibility, normally retained work, added-work count, and broad impact-range comparison. These signals identify items for human review and are not treated as exact decomposition truth.

The review artifact renderer produces process and transformation context, task descriptions, effort weights, dependencies, RETAIN/REMOVE rationales, added work, and all canonical impact metrics in a concise Markdown artifact.

## Hard-validity results

The credential-free fixture result passes the complete hard-validity framework. A deliberately incomplete classification is rejected and reported as a stage-validation failure. The framework therefore distinguishes structurally invalid output from semantically questionable output.

## Task-decomposition findings

The framework evaluates task count, required work coverage, duplicate names, dependency information, and explicit baseline weights. It does not require exact task wording or one decomposition as uniquely correct. The fixture demonstrates a five-task operational decomposition with explicit normalized weights summing to one.

## Effort-weight findings

The framework reports whether baseline weights are present, normalized, and attached to known subtasks. S4A allocation tests independently cover one, multiple, zero, and all removed rows. Semantic plausibility remains a reviewer decision against each process description rather than a hard-coded exact weight target.

## Transformation-classification findings

The framework reports retained and removed counts, missing normally-retained signals, and the resulting broad net-substitution range. It uses the fixed `TaskDecomposition` as the transformation input and never regenerates the baseline in the review helpers.

## Added/support-work findings

Added work is rendered separately by canonical category. The framework exposes the number and descriptions of added rows for review. S4A and staged-pipeline tests verify category aggregation and deterministic accounting; S4B does not assert that every transformation must have governance, review, or lifecycle work.

## Resulting impact ranges

Each benchmark case supplies broad expected net-substitution bounds intended to flag clearly unreasonable results. They are not exact-answer assertions. Canonical ratios, augmentation, and effect remain deterministic Wave 1 outputs after semantic inputs are validated.

## Provider comparisons

No live OpenAI, Gemini, or DeepSeek benchmark run was performed in this wave because no explicit live benchmark execution was enabled. `tests/test_semantic_benchmark_live.py` provides an opt-in path requiring both `RUN_SEMANTIC_BENCHMARKS=1` and the corresponding provider API key. It runs the same benchmark case through the normal provider-driven pipeline, checks hard validity, and verifies provider provenance before rendering the review artifact.

The ordinary test suite remains credential-free and does not make network calls. Existing mocked provider parity tests continue to verify that provider choice does not change canonical accounting semantics.

## Repeated-run stability

No repeated live-provider runs were performed. Stability measurements remain an explicit follow-up for the opt-in benchmark runner: task-count variation, major-work coverage, weight variation, RETAIN/REMOVE agreement, and net-substitution variation should be recorded for a small representative subset.

## Failure modes

The framework can expose missing work terms, duplicate task names, out-of-range task counts, missing normally-retained work signals, invalid stage identities, invalid dependencies, invalid effort weights, and impact values outside broad case expectations. No provider-generated failure was observed because live execution was not enabled.

No prompt, contract, provider, or accounting changes were made in S4B. The fixture initially exposed that the semantic validator correctly rejects an abstract task name without an operational verb; the fixture was adjusted to use an operational review activity while retaining the process meaning. This was a test-fixture correction, not a production behavior change.

## Tests added

- `tests/test_semantic_benchmarks.py` validates the 11-case corpus, expectation ranges, hard-validity reporting, semantic review separation, invalid-stage detection, and Markdown rendering.
- `tests/test_semantic_benchmark_live.py` provides opt-in OpenAI, Gemini, and DeepSeek execution without making credentials or network access mandatory.
- `tests/benchmark_support.py` contains benchmark contracts, hard-validity checks, semantic review signals, and artifact rendering.

## Verification

- `pytest -q`: `101 passed, 6 skipped`.
- `ruff check src tests`: passed.
- `ruff format --check src tests`: passed.
- `python -m compileall -q src`: passed using a temporary bytecode cache.
- `git diff --check`: passed.
- No live provider calls were made.

## Unresolved semantic concerns

Actual provider quality remains unmeasured until the opt-in live runner is executed with configured credentials and the rendered artifacts receive human review. The corpus expectations are intentionally broad and should be refined only after observing real cross-provider outputs; they must not be tightened to force a preferred decomposition.

SEMANTIC VALIDATION PASSED WITH DOCUMENTED LIMITATIONS — PROCEED TO S4C
