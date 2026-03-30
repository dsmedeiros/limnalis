# Red Team Review: m4-rt2-cli-r2

## Summary

Re-review of `src/limnalis/cli.py` after fixes from the first red team pass (m4-rt2-cli). All seven previously identified issues have been addressed. The CLI is stable: 16/16 smoke tests pass, all stress-test commands exit cleanly with correct codes, conformance runs 16/16 cases, and the JSON report validates. No critical or high-severity issues found. Two low-severity observations remain from the previous round (S2 `--json` semantic inconsistency on `validate-ast`, stdout/stderr mixing in conformance run), both explicitly accepted as advisories and not regressions. No new issues introduced by the fixes.

## Previous Findings Status

| ID | Finding | Status |
|----|---------|--------|
| S1 | `assert` used for control flow | FIXED: replaced with `if` guard + `_error()` at line 502 |
| S2 | `--json` inconsistency across subcommands | PARTIALLY FIXED: help text updated to "accepted for explicitness", `--json` added to `validate-fixtures`. Note: `validate-ast --json` still changes output content (status envelope vs full model dump) while help text says "accepted for explicitness" -- this is misleading but not a regression |
| S3 | Error output not JSON when `--json` specified | ACCEPTED: dead helper `_surface_error_payload` removed; errors consistently use `_error()` plain text to stderr across all commands |
| S4 | stdout/stderr mixing in conformance run | UNCHANGED: ERROR cases to stderr, PASS/FAIL/KNOWN to stdout. Acceptable given ERROR implies infrastructure failure |
| S5 | `_load_allowlist` silently drops list entries | FIXED: plain string lists now handled (lines 303-305). Mixed-type lists (dicts without `id` mixed with strings) still silently drop non-matching entries, but this is an unlikely edge case |
| S6 | Unused `asdict` import | FIXED: removed |
| S7 | Dead code `_surface_error_payload` | FIXED: removed |
| S8 | Dead `skipped == 0` check in strict mode | FIXED: `skipped` counter now increments regardless of `--strict`, so the strict check on line 740 is meaningful |
| Crash isolation | Per-case error handling in conformance run/report | FIXED: try/except wraps each case (lines 698-706 in run, 766-780 in report) |

## Critical Findings

None.

## Subtle Issues

### S1. `validate-ast --json` help text is misleading (LOW)
- **File:** `src/limnalis/cli.py`, line 115
- **What:** Help says "accepted for explicitness" but `--json` actually changes the output from a full model dump to a `{"status": "ok", "bundle": "..."}` envelope (lines 418-421). Without the flag, you get the full AST; with it, you get a status summary. This is a semantic content change, not just a format change.
- **How to trigger:** Compare `limnalis validate-ast file.json` vs `limnalis validate-ast --json file.json`.
- **Severity:** LOW. The flag works correctly; the help text just understates what it does.

### S2. `_load_allowlist` uses `sys.exit(1)` instead of returning (LOW)
- **File:** `src/limnalis/cli.py`, lines 280, 283
- **What:** On file-not-found or parse error, `_load_allowlist` calls `sys.exit(1)` directly rather than returning an error or raising. Every other error path in the CLI returns an exit code from the command function. This makes the function harder to test in isolation and breaks the return-code pattern.
- **Severity:** LOW. Works correctly in practice; testability concern only.

### S3. Exception handler pattern `except (json.JSONDecodeError, Exception)` (LOW)
- **File:** `src/limnalis/cli.py`, lines 281, 404, 437
- **What:** `json.JSONDecodeError` is a subclass of `Exception`, so listing both in the same except clause is redundant. The `isinstance` checks inside the handler compensate, but the pattern is confusing to readers.
- **Severity:** LOW. Functionally correct but unidiomatic.

## Test Gaps

Previous test gaps T1-T9 remain open. No new test gaps introduced. The most impactful remaining gaps:

- **T2:** No test for `validate-ast --json` vs `validate-ast` output difference. These produce different content and a regression here would be silent.
- **T7:** No test for `--allowlist` on conformance commands. The allowlist loading logic is non-trivial with multiple format branches.
- **T4:** No test for `evaluate --normalized <ast.json>`.

## Semantic Drift Risks

1. **`corpus` typed as `object`** on lines 667 and 749. Type checkers cannot catch attribute typos on the corpus parameter. This was noted in the first review and remains unchanged.

## Verdict: PASS

All blocking issues from the first review have been fixed. The remaining observations are low-severity style/documentation concerns that do not affect correctness. The CLI is stable under stress testing and all conformance cases pass.
