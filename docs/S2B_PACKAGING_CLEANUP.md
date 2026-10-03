# S2B Packaging Cleanup

## Files changed

- `.gitignore`
- `pyproject.toml`
- `uv.lock`
- `docs/S2B_PACKAGING_CLEANUP.md`

An existing change to `src/task_decomposition/ports/README.md` was preserved and was not part of the packaging cleanup.

## Dependency classification

- `pydantic`: `RUNTIME_CORE`; imported by contracts and optional port data models.
- `openai`: `OPTIONAL_PROVIDER`; used by the OpenAI and DeepSeek adapters through their provider extras.
- `google-genai`: `OPTIONAL_PROVIDER`; used only by the Gemini adapter.
- `pytest`: `DEV_TEST`; imported by tests only.
- `ruff`: `DEV_TEST`; repository lint and format tool.
- `black`: `DEV_TEST`; development formatter retained in the existing dev group.
- `pylance`: `DEV_TEST`; editor/static-analysis tooling, not runtime code.
- `pylint`: `DEV_TEST`; development lint tooling, not runtime code.
- `setuptools`: build-system dependency, not a package runtime dependency.

The previous runtime declarations for `black`, `pylance`, and `pylint` were moved to the existing `dev` dependency group. No declared dependency was classified as unused after checking source and test imports.

## Packaging and generated artifacts

`pyproject.toml` now declares only `pydantic` in core runtime dependencies. Provider extras remain optional and the aggregate `providers` extra installs OpenAI and Gemini support; DeepSeek uses the isolated OpenAI-compatible SDK already included by the OpenAI extra.

`uv.lock` was regenerated offline and agrees with the updated project metadata. `uv lock --check --offline` passed.

No checked-in `src/task_decomposition.egg-info/` existed. Local `dist/`, `__pycache__/`, `.pytest_cache/`, and `.ruff_cache/` artifacts were removed. `.gitignore` now explicitly ignores `.pytest_cache/` and `.ruff_cache/`; existing rules continue to ignore bytecode, build, dist, wheels, and egg-info artifacts.

## Provider isolation

Core package imports do not eagerly import OpenAI or Gemini SDKs. The provider isolation tests passed, and a direct core import confirmed that neither `openai` nor `google.genai` is imported by `import task_decomposition`.

## Installation and verification

- `uv sync --dev --offline`: passed and rebuilt the editable package from the cleaned metadata.
- `pytest -q`: `68 passed, 3 skipped`.
- `ruff check src tests`: passed.
- `ruff format --check src tests`: passed.
- `python -m compileall -q src`: passed using a temporary bytecode cache.
- Core public import smoke test: passed.
- `git diff --check`: passed.

`uv build --offline` could not complete because the sandbox has no cached `setuptools>=68` build backend and network access is unavailable. The failure is an environment-only build verification limitation; it did not affect editable installation or package metadata resolution.

## Remaining packaging debt

No repository packaging issue remains. A fully isolated wheel/sdist build should be rerun in an environment with the declared setuptools build backend available.

PACKAGING CLEAN — PROCEED TO S3
