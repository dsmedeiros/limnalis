# Red Team Review: m4-rt2-cli

## Summary

The CLI (`src/limnalis/cli.py`) is well-structured with consistent error handling across most commands. All error paths tested return exit code 1, no stack traces leak to the user, and error messages consistently include file paths. However, there are several issues around `--json` flag semantics, an `assert` used for runtime control flow, inconsistent stdout/stderr routing in conformance output, and notable test gaps around flag behavior and error-path JSON output.

## Critical Findings

None. No data corruption, wrong results, or security issues found.

## Subtle Issues

### S1. `assert` used for runtime control flow (MEDIUM)
- **File:** `src/limnalis/cli.py`, line 501
- **What:** `assert result.canonical_ast is not None` is used as a runtime guard before accessing `result.canonical_ast.to_schema_data()`.
- **How to trigger:** Run `python -O -m limnalis normalize <file>` where the normalizer somehow returns `canonical_ast=None` without raising. Currently the normalizer always populates `canonical_ast` on success, so this is not triggerable today, but the pattern is fragile.
- **What happens:** With `python -O`, asserts are stripped. If the guard condition ever becomes reachable (e.g., a normalizer change), the code proceeds to `result.canonical_ast.to_schema_data()` and raises `AttributeError` with a stack trace.
- **Note:** The `_run_evaluate` function at line 534 handles the same condition correctly with an `if` check and `_error()` call. The two approaches are inconsistent.

### S2. `--json` flag semantics are inconsistent across subcommands (MEDIUM)
- **File:** `src/limnalis/cli.py`, lines 91-96, 107-113, 127-130, 159-164
- **What:** The `--json` flag has three different meanings depending on the subcommand:
  - `parse --json`: Changes output format from pretty-printed text to JSON (lines 375-387). This is meaningful and correct.
  - `normalize --json`: No-op. Output is always JSON regardless of flag (verified by test). Help text says "accepted for explicitness."
  - `validate-ast --json`: Changes the *content* of output. Without `--json`: full model dump. With `--json`: `{"status": "ok", "bundle": "..."}` (lines 417-420). Help text says "accepted for explicitness" which is misleading.
  - `validate-source --json`: Same as normalize (no-op).
  - `evaluate --json`: Same as normalize (no-op, output always JSON).
  - `validate-fixtures`: No `--json` flag at all, but always outputs JSON.
  - `conformance list`, `conformance show`: No `--json` flag; passing `--json` causes argparse error referencing the top-level parser, not the subcommand.

### S3. Error output is not JSON when `--json` is specified (MEDIUM)
- **File:** `src/limnalis/cli.py`, all error paths
- **What:** When `--json` is passed and the command fails, errors are emitted as plain text to stderr via `_error()`. A machine consumer using `--json` would expect JSON error responses. The `_surface_error_payload` helper (lines 30-40) exists for this purpose but is never called from any command handler.
- **How to trigger:** `python -m limnalis parse --json nonexistent.lmn` outputs `error: file not found: nonexistent.lmn` to stderr, not JSON.

### S4. Conformance run mixes stdout and stderr inconsistently (MEDIUM)
- **File:** `src/limnalis/cli.py`, lines 700-728
- **What:** In `_run_conformance_run`, ERROR cases print to `sys.stderr` (line 700-701), but FAIL cases print to `sys.stdout` (line 711-717). PASS and KNOWN also go to stdout. The summary always goes to stdout (line 728).
- **Consequence:** Piping stdout to a file for processing loses ERROR case details. ERROR cases are counted in the summary but their details are only visible on stderr.

### S5. `_load_allowlist` silently drops malformed list entries (LOW)
- **File:** `src/limnalis/cli.py`, lines 302-307
- **What:** If the allowlist is a JSON array containing non-dict entries (e.g., `["A1", "A2"]`), the comprehension on line 303-306 silently skips them via `if isinstance(entry, dict) and "id" in entry`. The result is an empty allowlist with no warning.
- **How to trigger:** `python -m limnalis conformance run --allowlist list_of_strings.json` where the file contains `["A1", "A2"]`.
- **What happens:** All cases run without any allowlist applied. User believes deviations are being allowed but they are not.

### S6. Unused import: `from dataclasses import asdict` (LOW)
- **File:** `src/limnalis/cli.py`, line 6
- **What:** The `asdict` import is never used anywhere in the file. Dead code.

### S7. Dead code: `_surface_error_payload` (LOW)
- **File:** `src/limnalis/cli.py`, lines 30-40
- **What:** The function `_surface_error_payload` is defined but never called. It appears to have been intended for JSON error responses but was never wired in.

### S8. Dead branch in strict mode logic (LOW)
- **File:** `src/limnalis/cli.py`, line 731 and line 881
- **What:** `return 0 if (failed == 0 and errors == 0 and skipped == 0) else 1` -- the `skipped == 0` check is always true when `strict=True` because line 706 only increments `skipped` when `not strict`. The check is tautological but not harmful.

## Test Gaps

### T1. No test for `--json` flag on error paths
No test verifies that `parse --json nonexistent.lmn` or `normalize --json nonexistent.lmn` behaves correctly (either producing JSON errors or at minimum returning exit code 1 with no stdout).

### T2. No test for `validate-ast --json` output difference
`validate-ast --json` produces `{"status": "ok", "bundle": "..."}` while `validate-ast` (without flag) produces the full model dump. No test verifies or documents this difference.

### T3. No test for `validate-fixtures` with valid but schema-invalid JSON
The test `test_validate_fixtures_cli_smoke` only tests the happy path. No test feeds a valid JSON file that fails fixture corpus schema validation.

### T4. No test for `evaluate` with `--normalized` flag
No test covers `evaluate --normalized <ast.json>`.

### T5. No test for `conformance show` with a valid case
No test verifies the output format of `conformance show A1`.

### T6. No test for `conformance run --cases` with specific case IDs
No test covers the `--cases A1,A2` flag.

### T7. No test for `--allowlist` on conformance commands
No test exercises the allowlist loading or its effect on conformance run/report.

### T8. No test for `validate-fixtures` or `validate-ast` with YAML input
Both support YAML (via `load_json_or_yaml`) but only JSON inputs are tested.

### T9. No test for `conformance report --strict`
The `--strict` flag on `conformance report` is untested.

## Semantic Drift Risks

1. **`--json` flag will confuse consumers.** The flag means "change format" for `parse`, "change content" for `validate-ast`, and "do nothing" for `normalize`/`evaluate`/`validate-source`. This semantic inconsistency will cause confusion as more consumers adopt the CLI.

2. **`_surface_error_payload` is dead code that suggests an unfinished design.** It implies someone planned JSON error output but never connected it. If not needed, it should be removed to avoid misleading future developers into thinking it's wired in.

3. **`corpus` parameter typed as `object` on lines 664 and 740.** The `_run_conformance_run` and `_run_conformance_report` functions type `corpus` as `object`, losing all type information. This means typos in attribute access (e.g., `corpus.casez` instead of `corpus.cases`) would not be caught by type checkers.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **S1 (assert for control flow):** Replace the `assert` on line 501 with an explicit `if` check and `_error()` call, matching the pattern used in `_run_evaluate` line 534.
- **S2/S3 (--json inconsistency):** Standardize `--json` behavior: either make it meaningful everywhere (JSON errors on failure, JSON data on success) or remove it from commands where it is a no-op.
- **S4 (stdout/stderr mixing):** Route all conformance run output consistently. Either all per-case status to stdout, or all to stderr.
- **S5 (silent allowlist drop):** Emit a warning when allowlist entries are silently skipped due to missing `id` fields or non-dict entries.
- **S6/S7 (dead code):** Remove unused `asdict` import and either wire in or remove `_surface_error_payload`.
- **T1-T9 (test gaps):** Prioritize T1 (error path JSON), T2 (validate-ast --json), T4 (evaluate --normalized), and T7 (allowlist).
