# Red Team Review: 3c-redteam-integration-r2 (Round 2)

## Summary

Round 2 verification of fixes from Round 1 findings. All 236 tests pass (0 failures, 0 errors). Conformance suite: 16/16 PASS. JSON report produces valid output. The two blocking items from Round 1 (missing resolve_baseline unit tests, silent baseline_not_found) are resolved. The model-schema divergence on BaselineNode is mitigated by the conformance runner's schema-fallback mechanism with internal_diagnostics isolation. No new regressions detected.

## Verification of Round 1 Findings

### RESOLVED: No unit tests for resolve_baseline (Round 1: 3c-redteam-runtime, HIGH advisory)

Five dedicated unit tests now exist in `tests/test_runtime_primitives.py` class `TestResolveBaseline` (lines 2187-2292):
- `test_resolve_baseline_fixed_is_ready` — point+fixed -> ready
- `test_resolve_baseline_lazy_is_deferred` — point+on_reference -> deferred
- `test_resolve_baseline_moving_tracked_is_ready` — moving+tracked -> ready
- `test_resolve_baseline_moving_invalid_is_unresolved` — moving+fixed -> unresolved + baseline_mode_invalid diagnostic with correct shape (code, subject, severity)
- `test_resolve_baseline_not_found_is_unresolved` — missing ID -> unresolved + baseline_not_found diagnostic

These cover all three branches of resolve_baseline and validate diagnostic dict shape. Round 1 Gap 4 (from 3c-redteam-tests) is also addressed by this.

### RESOLVED: Silent baseline_not_found (Round 1: 3c-redteam-runtime, ISSUE-2)

`resolve_baseline` in `src/limnalis/runtime/builtins.py` line 618-626 now emits a `baseline_not_found` warning diagnostic when the baseline ID is not found in the bundle. The unit test `test_resolve_baseline_not_found_is_unresolved` validates this behavior including severity="warning".

### MITIGATED: Model-schema divergence on BaselineNode (Round 1: 3c-redteam-models, HIGH)

The Pydantic model still accepts `moving+fixed` while the JSON schema rejects it. This is by design: the conformance runner (`src/limnalis/conformance/runner.py`) implements a schema-fallback mechanism:
1. First attempt: `normalize_surface_text(source, validate_schema=True)` — raises for A4
2. Fallback: `normalize_surface_text(source, validate_schema=False)` — succeeds
3. Schema warning stored in `run_result.internal_diagnostics` (not in `bundle_result.diagnostics`)
4. Conformance comparison never sees the schema warning, preventing false failures

Test `test_run_case_schema_validation_fallback_preserves_specific_diagnostic` in `tests/test_conformance.py` (lines 216-268) validates this mechanism end-to-end including the internal_diagnostics isolation.

The A4 conformance case passes 16/16 and exercises the runtime `baseline_mode_invalid` diagnostic path.

### NOT ADDRESSED (advisory, non-blocking): _compare_diagnostics extra-actual blind spot (Round 1: 3c-redteam-tests, FINDING-1+2)

`_compare_diagnostics` still does not flag unexpected/extra actual diagnostics, and `compare_case` still skips comparison for empty expected diagnostic lists. These remain as advisories from Round 1. They do not block this changeset because:
- No current corpus case relies on asserting zero diagnostics via `"diagnostics": []`
- The extra-actual gap is a strictness improvement, not a correctness regression

## Critical Findings

None. No new bugs found.

## Subtle Issues

### ISSUE-1: A4 exclusion from parametrized normalizer test lacks explanatory comment (MEDIUM, carried from Round 1)

- **File:** `tests/test_normalizer.py`, line 98
- **What:** `sorted(case_id for case_id in FIXTURE_CASES if case_id != "A4")` silently excludes A4 with no comment explaining why. The separate `test_normalizer_accepts_invalid_moving_baseline_fixture` test (line 106) covers A4 without schema validation, but a reader must cross-reference to understand the exclusion.
- **Severity:** MEDIUM. Documentation gap, not a correctness issue.

### ISSUE-2: No test proving the public API rejects A4 with schema validation (MEDIUM, carried from Round 1)

- **File:** `tests/test_normalizer.py`
- **What:** No test asserts that `normalize_surface_text(a4_source, validate_schema=True)` raises `SchemaValidationError`. The conformance runner test proves the fallback mechanism works, but the direct public API rejection path is untested.
- **Severity:** MEDIUM. The production behavior is correct (schema catches it), but if the schema constraint were accidentally removed, no test would catch it.

## Test Gaps

1. No comment on A4 exclusion from parametrized tests (carried)
2. No direct public API rejection test for A4 (carried)
3. Extra-actual diagnostic blind spot in compare (carried advisory)

## Semantic Drift Risks

None new beyond Round 1 advisories.

## Verdict: PASS

All Round 1 blocking items are resolved. The five new resolve_baseline unit tests provide solid coverage of the implementation's three branches plus error paths. The schema-fallback mechanism with internal_diagnostics isolation is well-tested. 236/236 tests pass, 16/16 conformance cases pass. The remaining advisories (A4 exclusion comment, public API rejection test, compare strictness) are tracked but non-blocking.

## Advisories (non-blocking):
- **[MEDIUM]** Add a comment to line 98 of `tests/test_normalizer.py` explaining the A4 exclusion
- **[MEDIUM]** Add a test proving `normalize_surface_text(a4_source, validate_schema=True)` raises `SchemaValidationError`
- **[MEDIUM]** Address the `_compare_diagnostics` extra-actual blind spot in a future iteration
