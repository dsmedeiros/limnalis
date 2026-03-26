# Red Team Review: m4-rt2-conformance-r2

## Summary

Re-review of the conformance runner hardening fixes. All four findings from the previous pass (S2/S3/S4 crash isolation, diagnostics_count, dead skipped check) are confirmed fixed. All 52 conformance-related tests pass. The full corpus (16 cases) passes in strict mode. One pre-existing MEDIUM issue (extra-diagnostic blindness, S1 from the previous pass) remains, and is now empirically confirmed to affect two corpus cases (A1 and A4). No new critical or high-severity issues found.

## Critical Findings

None.

## Subtle Issues

### S1. Extra-diagnostic blindness remains and is empirically active (MEDIUM)

- **File:** `src/limnalis/conformance/compare.py`, lines 497-507
- **What:** When `expected_diags` is non-empty, `_compare_diagnostics` returns unmatched actual diagnostics but `compare_case` discards them. The previous pass noted this as theoretical; it is now confirmed active in the corpus.
- **How to trigger:** Run `A1` -- the fixture expects one `info/frame_pattern_completed` diagnostic. The runner also produces an `error/frame_unresolved_for_evaluation` diagnostic that is silently ignored. Similarly, `A4` expects one `error/baseline_mode_invalid` but the runner also produces an `info/stubbed_primitive` that is silently ignored.
- **What happens:** A1 passes conformance despite the runner producing an unmatched error-severity diagnostic. Any future regression that introduces spurious error diagnostics in cases with at least one expected diagnostic would go undetected.
- **Severity:** MEDIUM -- the unmatched diagnostics in A1 and A4 appear to be legitimate runner behavior (not bugs), but the conformance harness provides no visibility into them. This is a design gap, not a correctness bug.

### S2. `_build_conformance_result_payload` iterates strings as sequences (LOW)

- **File:** `src/limnalis/conformance/runner.py`, line 173
- **What:** `all_diags.extend(_to_schema_diag(diag) for diag in bundle_result.diagnostics)` -- if `bundle_result.diagnostics` were accidentally a string instead of a list, Python would iterate over individual characters. Each character would pass through `_to_schema_diag` (which returns non-dict values as-is) and become a spurious "diagnostic" entry. The schema validator would catch these downstream, but the error messages would be confusing (reporting single characters as invalid objects).
- **How to trigger:** A `BundleResult` with `diagnostics="not_a_list"` (not possible via normal code paths but possible via a future bug in runner internals).
- **Severity:** LOW -- defense-in-depth concern only. The crash isolation in the CLI would prevent user-facing breakage.

## Test Gaps

### TG1. No test for crash isolation behavior (carried forward)

There is still no test verifying that if `run_case` throws an unhandled exception for one case in a multi-case run, remaining cases still execute. The fix is present in the CLI code (try/except wrapping the per-case loop body in both `_run_conformance_run` and `_run_conformance_report`), but no test exercises this path.

### TG2. No test for extra-diagnostic blindness (carried forward)

No test documents whether ignoring unmatched actual diagnostics when expected is non-empty is intentional behavior. Given that A1 and A4 are now confirmed to trigger this, a test should explicitly document the design decision.

### TG5. False green in failing-case report test (carried forward)

`TestConformanceReportFailingCases.test_failing_case_has_mismatches_in_json_report` iterates zero times because no corpus case currently fails. The test passes vacuously.

## Semantic Drift Risks

### SD1. A1 unmatched error diagnostic may indicate a runner issue

Case A1 expects `info/frame_pattern_completed` and passes, but also produces `error/frame_unresolved_for_evaluation`. This error diagnostic suggests the runner is reporting that required frame facets are unresolved. If this is expected behavior for A1 (which tests resolved shorthand frames), the fixture should either (a) add this diagnostic to its expected list, or (b) the runner should not emit it for this case. The conformance harness currently masks the question entirely.

## Verification of Previous Findings

| Finding | Status | Evidence |
|---------|--------|----------|
| S2: Unguarded crash in CLI per-case loop | **FIXED** | `cli.py` lines 697-706 and 765-780 wrap per-case logic in try/except |
| S3: `diagnostics_count` showed expected not actual | **FIXED** | `cli.py` lines 796-803 now iterate over actual `bundle_result` diagnostics |
| S4: Dead `skipped==0` check in strict mode | **FIXED** | `skipped` is now incremented regardless of strict mode (line 718); strict check on line 740 is meaningful |
| S1: Extra-diagnostic blindness | **OPEN** | Confirmed active in A1 and A4; design decision, not a bug |

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **S1** (extra-diagnostic blindness): Two corpus cases (A1, A4) produce unmatched actual diagnostics that the conformance harness silently ignores. Consider either: (a) updating A1/A4 fixtures to include these diagnostics in their expected lists, or (b) adding a warning mechanism for unmatched error-severity actuals, or (c) adding a test that explicitly documents this as intentional.
- **TG1** (crash isolation test gap): The crash isolation fix is correct but untested. A synthetic test injecting a `run_case` exception would provide regression coverage for this fix.
- **TG5** (false green): The failing-case report test passes vacuously. Inject a synthetic failure to exercise the code path.
