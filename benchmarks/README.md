# Semantic benchmark corpus

`processes.json` contains the initial S4B corpus of realistic process and transformation definitions. The cases are evaluation assets, not production domain objects and not scenario-management data.

Each case provides broad task-count, work-coverage, retained-human-work, and net-substitution expectations. These expectations are review signals rather than exact answers; multiple decompositions can be valid.

The credential-free framework lives in `tests/benchmark_support.py`. It validates hard structural/accounting validity, reports semantic review signals separately, and renders a human-reviewable artifact containing the task decomposition, transformation classifications, added work, and canonical result.

Optional live execution is disabled unless `RUN_SEMANTIC_BENCHMARKS=1` and the corresponding provider key are configured. Run `python benchmarks/run_live.py` to execute all cases for the primary configured provider and save Markdown and JSON review artifacts under `benchmarks/results/`. Use `--all-providers` for full coverage across every configured provider; without it, additional configured providers run a three-case representative subset. The normal test suite never requires network access or credentials.

This corpus does not own scenarios, simulation, Monte Carlo, grid search, or repeated-alternative management.
