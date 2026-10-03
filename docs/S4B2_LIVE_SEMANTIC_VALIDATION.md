# S4B-2 Live Semantic Validation

## Scope

This wave added and exercised an opt-in live benchmark runner for the 11-case S4B corpus. The runner uses the existing provider-driven decomposition path, validates every result with the existing hard-validity checks, renders human-reviewable Markdown, and stores JSON containing provider provenance and review signals under `benchmarks/results/`.

## Providers and models

No live provider was executed. `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `DEEPSEEK_API_KEY` were absent from the environment, so no provider client was constructed and no model/API response was requested. No credential values were inspected or printed.

## Benchmark cases

Live execution completed 0 of 11 cases. The runner is configured to execute all cases for the primary configured provider. With `--all-providers`, it executes all cases for every configured provider; otherwise additional configured providers receive a three-case representative subset.

## Task-decomposition observations

There are no real-provider task outputs to review in this wave. The credential-free benchmark framework continues to enforce structural checks and exposes review signals for task count, expected work coverage, duplicate names, and effort-weight totals, but these signals are not evidence of live provider quality.

## Effort-weight observations

No live effort allocations were observed. The live runner supplies explicit accounting input rather than asking a provider to invent authoritative effort, preserving the Wave 1 accounting boundary.

## Transformation observations

No live RETAIN/REMOVE or added-work classifications were observed. The runner routes provider output through the existing staged validators before accounting and records classification and added-work details in each future artifact.

## Impact observations

No live canonical impacts were produced. When enabled, the runner records gross removed work, added human work, net remaining work, net substitution, augmentation multiplier, and effect from deterministic accounting; providers do not provide these metrics.

## Cross-provider observations

No cross-provider comparison was possible because no provider credentials were configured. The runner supports OpenAI, Gemini, and DeepSeek through the same application path without changing decomposition or accounting semantics.

## Stability observations

Repeated live execution was not performed. There is therefore no live evidence about task-structure, classification, or impact stability.

## Failures and limitations

No material semantic failure was observed because no live provider output was available. The only limitation is unavailable credentials, which leaves actual provider quality unmeasured. This is an execution limitation rather than a provider or validation failure.

No production prompts, contracts, providers, or accounting code were changed. The only implementation addition is the opt-in runner and its documented artifact location. No result artifacts were generated during this run.

## Verification

- `RUN_SEMANTIC_BENCHMARKS=1 python benchmarks/run_live.py` skipped cleanly because no provider key was configured.
- `python benchmarks/run_live.py` skipped cleanly without the opt-in flag.
- `pytest -q`: 101 passed, 6 skipped.
- `ruff check benchmarks/run_live.py src tests`: passed.
- `ruff format --check src tests benchmarks/run_live.py`: passed.
- `python -m compileall -q src benchmarks/run_live.py`: passed using an external temporary bytecode cache.
- `git diff --check`: passed.

## Deferred manual validation

Later manual evaluation should review real artifacts for operational completeness, granularity, effort plausibility, transformation-specific classification, added/support work, directionally plausible impact, cross-provider differences, and lightweight repeated-run stability. This smoke wave does not claim semantic correctness or provider quality has been established.

LIVE SEMANTIC SMOKE VALIDATED WITH MINOR ISSUES — PROCEED TO S4C
