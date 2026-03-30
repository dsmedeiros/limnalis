# Red Team Review: m4-rt2-conformance

## Summary

The conformance runner, comparator, and CLI are functionally correct for the current corpus -- all 16 cases pass, reports are well-structured, totals are consistent, and ordering is deterministic. However, there are two medium-severity issues (extra-diagnostic blindness and unguarded session-building crashes) and several subtle design concerns that could silently mask regressions or produce confusing output as the corpus grows.

## Critical Findings

None.

## Subtle Issues

### S1. Extra actual diagnostics silently ignored when expected is non-empty (MEDIUM)

- **File:** `src/limnalis/conformance/compare.py`, lines 497-507
- **What:** `compare_case` only checks for unexpected extra diagnostics (unmatched actuals) when `expected_diags` is an empty list (`if not expected_diags and unmatched_diags`). When `expected_diags` is non-empty, `_compare_diagnostics` returns unmatched extras but `compare_case` discards them entirely.
- **How to trigger:** A fixture case that expects `[{code: "missing_binding", severity: "error"}]` but the runner also produces an unexpected `{code: "SURPRISE_ERROR", severity: "error"}` -- the case still passes.
- **What happens:** Real error diagnostics produced by the runner go unnoticed in conformance results. A regression that introduces spurious error diagnostics would not be caught by any existing case that already expects at least one diagnostic.
- **Severity:** MEDIUM -- no current corpus case triggers this, but it creates a blind spot for future regressions.

### S2. Unguarded crash in `_build_sessions_from_case` propagates to CLI (MEDIUM)

- **File:** `src/limnalis/conformance/runner.py`, line 774; `src/limnalis/cli.py`, lines 694-718
- **What:** `_build_sessions_from_case` calls `TimeCtxNode(**time_data)` at line 544 without a try/except. If `time_data` is malformed (e.g., a string instead of a dict), a `TypeError` propagates out of `run_case` (which only catches exceptions at the parse and run_bundle stages, not the session-building stage). In the CLI, `_run_conformance_run` has no per-case try/except, so one bad case crashes the entire run and all subsequent cases are skipped.
- **How to trigger:** A corpus fixture with `environment.sessions[].steps[].time` set to a non-dict value.
- **What happens:** The CLI crashes with an unhandled `TypeError`. No summary line is printed. Other cases after the crashing one are never executed.
- **Severity:** MEDIUM -- currently all corpus data is well-formed, but any future corpus extension could trigger this.

### S3. `diagnostics_count` in report shows expected count, not actual (MEDIUM)

- **File:** `src/limnalis/cli.py`, line 779
- **What:** `case_entry["diagnostics_count"] = len(case.expected_diagnostics())` uses the expected diagnostic count from the fixture, not the actual diagnostic count from the run result. For passing cases these are equivalent (by definition of passing), but for failing or error cases this is misleading -- a developer looking at the report would see the expected count and assume it reflects what was produced.
- **Severity:** MEDIUM -- misleading for debugging but does not affect correctness of pass/fail decisions.

### S4. Dead code in strict mode return condition (LOW)

- **File:** `src/limnalis/cli.py`, line 731 and line 881
- **What:** The strict-mode return checks `skipped == 0`, but `skipped` is only incremented inside the branch guarded by `not strict` (line 706/767). When `strict=True`, the allowlist branch is never entered, so `skipped` is always 0. The `skipped == 0` check is therefore tautologically true in strict mode.
- **Severity:** LOW -- not a bug, but the dead condition is misleading to readers. The intent (strict should fail on allowlisted cases) is actually achieved by the fallthrough to the FAIL branch, not by this check.

### S5. `_build_fixture_eval_expr` and `_build_fixture_synthesize_support` share mutable closure state (LOW)

- **File:** `src/limnalis/conformance/runner.py`, lines 288 and 375
- **What:** Both closures use a mutable `state` dict with `step_index` and `last_step_ctx`. If a single `run_case` call were ever used in a concurrent context (e.g., parallel test execution), the shared mutable state would cause race conditions. Currently all usage is single-threaded, but the pattern is fragile.
- **Severity:** LOW -- no current concurrency, but the closures are not safe to share.

## Test Gaps

### TG1. No test for CLI crash isolation when a single case fails with an unhandled exception

There is no test verifying that if `run_case` throws an unhandled exception for one case, remaining cases still execute. The CLI currently does NOT handle this -- one crash poisons the whole run. A test should exist to document this behavior (or the behavior should be fixed).

### TG2. No test for extra-diagnostic blindness

No test verifies whether unexpected extra diagnostics (beyond those in `expected`) are detected or ignored. The current behavior silently ignores them when `expected_diags` is non-empty. A test should explicitly document whether this is intentional.

### TG3. No negative test for `conformance run --cases UNKNOWN`

The CLI correctly returns exit code 1 for unknown case IDs, but there is no test for this path in the test suite. Only the `conformance show NONEXISTENT_CASE` path is implicitly tested.

### TG4. No test for `--strict` mode with allowlist entries

There is no test verifying that `--strict` causes allowlisted-but-failing cases to be reported as FAIL rather than KNOWN. This is a key behavioral guarantee with no explicit test coverage.

### TG5. No test for report format with failing cases

`TestConformanceReportFailingCases.test_failing_case_has_mismatches_in_json_report` only checks if any failing cases exist and validates their structure. Since the current corpus has no failures, the test body is effectively a no-op (the `for case_entry in failing` loop iterates zero times). This is a false green.

### TG6. No test for Markdown report failure detail section

The Markdown report has a "## Failures" section that is only emitted when failures exist. No test verifies this section's formatting or content. Like TG5, the current all-pass corpus means this code path is untested.

### TG7. No test for schema_violations appearing in report output

`validate_result_schema` is called in both `_run_conformance_run` and `_run_conformance_report`, and schema violations affect pass/fail determination. But no test exercises a case that produces schema violations to verify they appear correctly in the report.

## Semantic Drift Risks

### SD1. `--all` flag is a no-op

The `--all` flag (line 221) is accepted but has no effect -- the default behavior already runs all cases. It exists "for explicitness" per the help text, but a user might incorrectly believe that without `--all`, only a subset runs. In fact, without `--cases`, all cases run regardless of `--all`.

### SD2. Report `diagnostics_count` name suggests actual, shows expected

The field name `diagnostics_count` in the JSON report does not indicate it represents the expected count. A consumer parsing this report would reasonably assume it reflects what was actually produced. If the field is renamed to `expected_diagnostics_count` or supplemented with `actual_diagnostics_count`, the semantic ambiguity disappears.

### SD3. `compare_case` returns `passed=True` when `expected` has no `sessions` key

At line 474: `if expected_sessions:` -- when a case has no `sessions` in its expected output, all session-level comparison is skipped. The case can pass based solely on diagnostics matching. This is intentional for diagnostic-only cases (e.g., A2), but there is no guard against a case that accidentally omits sessions and passes when it should not.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **S1** (extra-diagnostic blindness): Consider flagging unmatched actual error/fatal diagnostics even when `expected_diags` is non-empty, or at minimum add a test documenting the current behavior as intentional.
- **S2** (unguarded crash propagation): Wrap the per-case loop body in `_run_conformance_run` and `_run_conformance_report` with try/except to prevent one bad case from aborting the entire run. Similarly, guard `_build_sessions_from_case` within `run_case`.
- **S3** (diagnostics_count semantics): Rename to `expected_diagnostics_count` or add an `actual_diagnostics_count` field to reduce ambiguity.
- **TG5** (false green): The failing-case report test passes vacuously because no cases currently fail. Add a test that injects a synthetic failure to exercise the failure-reporting code path.
