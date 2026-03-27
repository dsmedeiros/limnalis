# Red Team Review: a4-doc-test

## Summary

Documentation-only change plus one new test. All claims in the comments are factually accurate when cross-referenced against the JSON schema, the runtime enforcement code, and the public API. The new test correctly exercises the intended path and passes. No invariants are violated. Full test suite (350 tests) passes.

## Critical Findings

None.

## Subtle Issues

1. **Comment in test_normalizer.py references only one of two A4 tests.** The exclusion comment at line 98-99 says "it has a dedicated test below (test_normalizer_accepts_invalid_moving_baseline_fixture)" but there are now two dedicated A4 tests: the existing `test_normalizer_accepts_invalid_moving_baseline_fixture` (line 108) and the new `test_a4_public_api_rejects_moving_fixed_baseline` (line 191). The comment is not wrong -- it just does not mention both. This is minor and does not affect correctness.

2. **The new test imports from `limnalis.api.normalizer` but the function is defined in `limnalis.loader`.** The import path through `limnalis.api.normalizer` is a re-export (confirmed at `/home/user/limnal/src/limnalis/api/normalizer.py` line 8). This is intentional -- the test docstring says "Public API enforces schema" and the `api` module is the declared stable public API surface. This is correct usage.

## Test Gaps

None introduced by this change. The new test covers the one scenario that was previously untested (public API rejection of moving+fixed baseline via schema validation). The test is not tautological: it actually routes through `LimnalisParser -> Normalizer -> to_schema_data -> validate_payload` and confirms `SchemaValidationError` is raised.

## Semantic Drift Risks

1. **Comment references commit hash 549e3ce.** Commit hashes are stable (they never change), so this is safe. However, if the repository is ever rebased or force-pushed such that this commit disappears, the reference becomes a dead link. This is a standard tradeoff and not worth blocking over.

## Verdict: PASS

No blocking issues. No advisories warranting PASS_WITH_ADVISORIES -- the subtle issues identified are informational only and do not represent correctness or maintainability risks.
