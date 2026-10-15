# Added-Work Taxonomy Verification

## Changes verified

- Canonical `AddedWorkCategory` now accepts only `AI_INTERACTION` and `AI_VERIFICATION`.
- OpenAI, Gemini, and DeepSeek share the updated prompt and response enum.
- Empty added-work results remain valid.
- The prompt requires the complete root response and explicitly excludes baseline work, implementation, maintenance, and passive waiting.
- Derived accounting preserves total added work and existing W0/W1 formulas; `AI_INTERACTION` feeds `ai_interaction_work` and `AI_VERIFICATION` feeds `ai_verification_work`.
- The OpenAI provider retains the existing 2,000-token default for added work.

## Tests

Focused verification passed:

```text
76 passed
```

This covered the taxonomy, staged pipeline, mathematical validation, transformation boundaries, and OpenAI provider tests. Ruff and format checks passed for the new taxonomy test and the directly edited contract/prompt files; the repository-wide Ruff command still reports pre-existing findings in the broader codebase. Compileall passed with an isolated bytecode cache.

The full repository suite retains three unrelated pre-existing failures in DeepSeek semantic fixtures and one semantic prompt assertion; these are not caused by the taxonomy change. The full run otherwise passed 235 tests with 6 skips.

The live Production Scheduling example was rerun with the existing 2,000-token added-work budget before this accounting migration. It completed operational decomposition, RETAIN/REMOVE, added-work classification, and accounting without truncation or excessive whitespace output. A fresh live run is not claimed for this local contract-only change.
