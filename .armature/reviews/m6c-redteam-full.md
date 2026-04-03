# Red Team Review: m6c-full

## Summary

The Milestone 6C changeset (~4,700 LOC) is structurally sound with clean
deterministic output, correct SARIF 2.1.0 structure, proper graph sorting,
and sensible template scaffolding. However, adversarial testing uncovered
two HIGH-severity bugs (uncaught `FileNotFoundError` in lint causing full
Python tracebacks to users; `_sanitize_identifier` insufficient for
Python-identifier safety producing uncompilable plugin-pack output) and
two MEDIUM-severity issues (SARIF format unreachable from CLI despite
backend support; Mermaid title/label injection via newlines).

**Test baseline**: 833 existing tests pass. 47 adversarial tests written,
44 pass, 3 fail (each revealing a real bug).

## Critical Findings

### Finding 1: `lint` command leaks full Python traceback on nonexistent file

- **File**: `src/limnalis/cli/lint_cmd.py`, line 38
- **Severity**: HIGH
- **What**: `_lint_file()` catches `UnexpectedInput` and `NormalizationError`
  but does NOT catch `FileNotFoundError`. When a user runs
  `limnalis lint nonexistent.lmn`, the full Python traceback is printed to
  stderr instead of a clean error message.
- **Contrast**: `inspect_cmd.py` lines 39-40 and `visualize_cmd.py` lines
  74-75 both correctly handle `FileNotFoundError`. The lint path is the
  only one that leaks.
- **Reproduction**:
  ```bash
  python -m limnalis lint nonexistent.lmn
  # Produces: Traceback (most recent call last): ... FileNotFoundError: ...
  ```
- **Expected**: `error: file not found: nonexistent.lmn` (matching inspect behavior)
- **Impact**: Professional UX broken. Users see internal implementation
  details. Also applies to `analyze` and `symbols` commands since they
  share `_lint_file`.

### Finding 2: `_sanitize_identifier` produces invalid Python identifiers

- **File**: `src/limnalis/cli/init_cmd.py`, line 45-57
- **Severity**: HIGH
- **What**: The sanitizer only strips path separators (via `Path.name`) and
  replaces hyphens/spaces with underscores. It does NOT strip or replace
  parentheses, quotes, dots, at-signs, or other characters that are invalid
  in Python identifiers. The `plugin_pack_template` then uses the name
  directly as a Python function name (`def {name}_handler(...)`) producing
  code that does not compile.
- **Reproduction**:
  ```bash
  python -m limnalis init plugin-pack "__import__('os').system('whoami')" --dry-run
  # Produces: def __import__('os').system('whoami')_handler(  ... SyntaxError
  ```
- **Note**: This is not a code execution vulnerability (the output is a
  static file, not eval'd), but it violates the template contract that
  generated code should be valid and usable.
- **Impact**: Any identifier containing characters invalid in Python
  identifiers (parentheses, dots, quotes, etc.) will produce broken output.

## Subtle Issues

### Finding 3: SARIF format supported in backend but unreachable from CLI

- **File**: `src/limnalis/cli/lint_cmd.py`, line 176; `src/limnalis/diagnostic_fmt.py`, line 121-123
- **Severity**: MEDIUM
- **What**: `format_diagnostics()` accepts `mode="sarif"` and correctly
  delegates to `diagnostics_to_sarif()`. But the argparse `choices` for
  `--format` on both `lint` and `analyze` commands only list
  `["plain", "json", "grouped"]`. SARIF output is implemented but
  unreachable via CLI.
- **Reproduction**:
  ```bash
  python -m limnalis lint --format sarif examples/minimal_bundle.lmn
  # error: argument --format: invalid choice: 'sarif'
  ```
- **Impact**: The SARIF module (`sarif.py`) was built and tested but never
  wired to the CLI, defeating its purpose for CI/CD integration.

### Finding 4: Mermaid title injection via newlines

- **File**: `src/limnalis/graph.py`, lines 200-203
- **Severity**: LOW
- **What**: The `title` parameter to `render_mermaid()` is interpolated
  directly into YAML front matter without any newline sanitization. A title
  containing `\n` can inject arbitrary YAML keys into the Mermaid front
  matter block.
- **Reproduction**:
  ```python
  from limnalis.graph import render_mermaid
  render_mermaid([], [], title="Evil\n---\ninjected: true")
  # Produces broken YAML front matter with injected keys
  ```
- **Practical risk**: LOW because titles come from hardcoded strings in
  `visualize_cmd.py` (line 85-88), not from user input. But if the API is
  used programmatically, this is a sanitization gap.

### Finding 5: Mermaid label newline injection

- **File**: `src/limnalis/graph.py`, lines 213, 219
- **Severity**: LOW
- **What**: Node and edge labels are only sanitized for double quotes
  (`"` -> `'`). Newlines in labels break Mermaid syntax since each line
  is interpreted as a separate statement. Labels come from AST data
  (frame facets, bridge IDs) so practical risk is low but the sanitization
  is incomplete.

## Test Gaps

1. **No test for `lint` with nonexistent file.** The existing test suite
   has no test that verifies `limnalis lint <missing-file>` produces a clean
   error. `inspect` and `visualize` have implicit coverage through their
   exception handlers, but `lint` was never tested with FileNotFoundError.

2. **No negative tests for `_sanitize_identifier`.** The sanitizer is only
   tested with path-traversal scenarios (which it handles correctly). There
   are no tests verifying that identifiers with Python-invalid characters
   produce valid Python when used in `plugin_pack_template`.

3. **No test that SARIF is reachable from CLI.** The SARIF module has unit
   tests but no integration test that exercises `limnalis lint --format sarif`.

4. **No test for `analyze`/`symbols` with nonexistent file.** Same
   `_lint_file` code path as `lint`.

## Semantic Drift Risks

1. **`_SARIF_SCHEMA` URL**: The hardcoded OASIS URL
   (`https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-schema-2.1.0.json`)
   in `sarif.py` line 14 is correct for SARIF 2.1.0 but will need updating
   if/when SARIF 2.2 is adopted.

2. **`_SEVERITY_TO_LEVEL` mapping**: Maps `"info"` to `"note"` (correct per
   SARIF spec) but does not have a fallback-to-`"none"` for unknown
   severities -- it falls back to `"note"` via `.get(severity, "note")`.
   This is reasonable but worth documenting.

3. **Duplicate error handling patterns**: `_lint_file()` and
   `_normalize_only()` (in `inspect_cmd.py`) have nearly identical
   try/except blocks but catch different exception sets. This duplication
   invites drift as one gets fixed but not the other (exactly what happened
   with `FileNotFoundError`).

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **[HIGH] Fix FileNotFoundError handling in `_lint_file()`** (`lint_cmd.py` line 38): Add `FileNotFoundError` to the caught exceptions, or add a broader `except Exception` fallback with clean error formatting. This affects `lint`, `analyze`, and `symbols` commands.
- **[HIGH] Fix `_sanitize_identifier()` to produce valid Python identifiers** (`init_cmd.py` line 45): Strip all characters that are not valid in Python identifiers (alphanumeric + underscore), or use a regex like `re.sub(r'[^a-zA-Z0-9_]', '_', name)`. Consider also ensuring the result does not start with a digit.
- **[MEDIUM] Add `"sarif"` to argparse `choices` for `--format`** on both `lint` and `analyze` commands (`lint_cmd.py` lines 176, 193).
- **[LOW] Sanitize newlines in Mermaid title and labels** (`graph.py` lines 200-203, 213, 219).

## Adversarial Tests Written

File: `tests/test_redteam_m6c.py` (47 tests total)

| Test Class | Tests | Pass | Fail |
|---|---|---|---|
| TestInitPathTraversal | 3 | 3 | 0 |
| TestInitMaliciousIdentifiers | 3 | 2 | 1 |
| TestInitHyphenatedNames | 2 | 2 | 0 |
| TestInitUnicodeNames | 2 | 2 | 0 |
| TestEmptyAndMissingFiles | 4 | 3 | 1 |
| TestMalformedLmn | 2 | 2 | 0 |
| TestSarifEdgeCases | 6 | 6 | 0 |
| TestSarifCli | 1 | 1 | 0 |
| TestMermaidInjection | 2 | 2 | 0 |
| TestEmptyGraph | 2 | 2 | 0 |
| TestDoctorCommand | 2 | 2 | 0 |
| TestDeterminism | 3 | 3 | 0 |
| TestFormatEdgeCases | 2 | 2 | 0 |
| TestErrorMessageQuality | 2 | 1 | 1 |
| TestTemplateRoundTrip | 3 | 3 | 0 |
| TestAnalysisEdgeCases | 2 | 2 | 0 |
| TestDiagnosticFromDict | 2 | 2 | 0 |
| TestSanitizeIdentifier | 4 | 4 | 0 |

3 failing tests correspond to Findings 1, 2 (real bugs).

## Full Test Suite Results

- **Before adversarial tests**: 833 passed, 0 failed
- **After adversarial tests (existing suite only)**: 833 passed, 0 failed (no regressions)
- **Adversarial tests**: 44 passed, 3 failed (3 real bugs found)
