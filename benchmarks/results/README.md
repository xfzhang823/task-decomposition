# Live semantic benchmark results

The live runner writes one Markdown review artifact and one JSON result artifact per executed benchmark case under `provider/model/`. The JSON artifact includes provider provenance and hard-validity and semantic-review signals without storing API keys or raw provider responses.

Live execution is opt-in with `RUN_SEMANTIC_BENCHMARKS=1` and requires the corresponding provider API key. No live results are committed by default. This directory currently contains no provider output because no provider credentials were configured during S4B-2.
