# Red Team Review: Milestone 6C Wave 2+3

## Summary

The Wave 2+3 changeset is well-structured and mostly correct. All 833 tests pass. Cross-module integration in `cli/__init__.py` is coherent -- all commands register and dispatch correctly with no circular imports. I found one MEDIUM security issue (path traversal in `init` command), one MEDIUM correctness issue (invalid Python identifiers in `plugin_pack_template`), and several LOW-severity items. No CRITICAL or HIGH findings. The SARIF output is structurally valid. Graph output is deterministic and Mermaid-syntax-correct. The `--no-color` propagation works for all commands that emit colored output.

## Critical Findings

None.

## Subtle Issues

### S1: Path traversal in `init_cmd._run_init` [MEDIUM]

- **File:** `src/limnalis/cli/init_cmd.py`, lines 55-59
- **What:** The `identifier` argument is concatenated directly into a filename (`identifier + gen["ext"]`) and written to `out_dir / filename`. If `identifier` contains path separators (e.g., `../../malicious`), the file can be written outside the intended output directory.
- **How to trigger:** `limnalis init bundle "../../etc/malicious"` writes `../../etc/malicious.lmn` relative to the output dir.
- **Impact:** File written to unintended location. The risk is limited because the user is running the command themselves (no remote trigger), and the file content is a benign template. But the principle matters.
- **Severity:** MEDIUM

### S2: Invalid Python identifiers in `plugin_pack_template` [MEDIUM]

- **File:** `src/limnalis/templates.py`, lines 37 and 52
- **What:** The `name` parameter is interpolated directly into `def {name}_handler(` and `def register_{name}_plugins(`. If `name` contains hyphens, spaces, or other non-identifier characters (e.g., `my-pack`), the generated Python is syntactically invalid. Since `limnalis init plugin-pack` accepts arbitrary identifiers, this is a realistic scenario.
- **How to trigger:** `limnalis init plugin-pack my-pack --dry-run` produces `def my-pack_handler(` which is a syntax error.
- **Impact:** Generated file cannot be imported. User sees confusing syntax error with no connection to the original cause.
- **Severity:** MEDIUM

### S3: Mermaid ID collision potential in `_mermaid_id` [LOW]

- **File:** `src/limnalis/graph.py`, line 185
- **What:** `_mermaid_id` replaces all non-alphanumeric, non-underscore characters with `_`. Two distinct IDs that differ only in special characters (e.g., `bridge-1` vs `bridge.1`) would both become `bridge_1`, causing Mermaid to render them as the same node. In practice this is unlikely because the graph builders add prefixes (`frame_`, `ev_`, `cb_`, `evi_`) and because Limnalis IDs are typically simple identifiers. But the function has no collision detection or warning.
- **Severity:** LOW

### S4: Misleading comment in `_inspect_machine_state` [LOW]

- **File:** `src/limnalis/cli/inspect_cmd.py`, line 226
- **What:** Comment says "last step of the first session" but the loop iterates all sessions and all steps, so `machine` ends up being the last step of the LAST session. With the current `_run_default_evaluation` (1 session, 1 step) this is indistinguishable. It becomes wrong if someone reuses this function with multi-session evaluation.
- **Severity:** LOW

### S5: Duplicated error-handling code in `inspect_cmd.py` [LOW]

- **File:** `src/limnalis/cli/inspect_cmd.py`, lines 28-73 and 76-106
- **What:** `_run_default_evaluation` and `_normalize_only` have near-identical exception-handling blocks (5 except clauses each). This is a maintenance risk: if a new exception type needs handling, it must be updated in both places. The 407 LOC count (exceeding the 350 LOC target) is partly driven by this duplication.
- **Severity:** LOW

### S6: `_LINT_COMMANDS` set created inside function body on every call [LOW]

- **File:** `src/limnalis/cli/__init__.py`, line 100
- **What:** `_LINT_COMMANDS = {"lint", "analyze", "symbols", "explain"}` is recreated as a local variable on every call to `main()`. Harmless (Python optimizes small set literals), but unconventional for a module-level constant pattern.
- **Severity:** LOW

## Test Gaps

### T1: No negative tests for `init` command path traversal

There are no tests verifying that `limnalis init bundle "../traversal"` is handled safely. Given S1, this should be tested regardless of whether a fix is applied.

### T2: No test for `plugin_pack_template` with non-identifier names

No test calls `plugin_pack_template("my-pack")` and verifies the output is valid Python (or that the function rejects the input).

### T3: No tests for `inspect` commands with invalid files

The help text snapshot tests verify `--help` works, but there are no tests verifying graceful error handling when `inspect ast /nonexistent.lmn` is invoked.

### T4: No SARIF output validation test

The SARIF module produces output claiming to conform to the SARIF 2.1.0 schema, but no test validates the output against the actual SARIF JSON Schema. The structure looks correct on inspection, but schema conformance is not verified programmatically.

### T5: `doctor` check results not asserted individually

If a new check is added that always FAILs, the existing tests would not catch it unless they assert on individual check names.

## Semantic Drift Risks

### D1: `visualize_cmd` uses `load_surface_bundle` while `inspect_cmd` uses `normalize_surface_file`

These are functionally equivalent (the former calls the latter internally), but the error-handling behavior differs significantly. `inspect_cmd` catches and formats 5 specific exception types with detailed messages. `visualize_cmd` catches `Exception` with a generic message. A user seeing "failed to normalize ..." from visualize gets less diagnostic information than from inspect for the same file. This inconsistency will grow as more error cases are added.

### D2: `doctor_cmd._check_example_files` always SKIPs in non-dev installs

The walk-up-from-`__file__` strategy to find `examples/` will never find the directory when the package is installed via pip into site-packages. The SKIP result is handled gracefully, so this is not a bug. But if someone adds more checks that depend on dev-install paths, the doctor command becomes increasingly unhelpful for end users.

### D3: `_check_pydantic_version` reports version but does not validate it

The check reports Pydantic is importable and shows the version, but does not verify it meets the minimum requirement (Pydantic 2.x). If someone has Pydantic 1.x installed, this check would PASS even though the toolchain would fail elsewhere.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **S1 (MEDIUM):** `init_cmd._run_init` should validate that `identifier` does not contain path separators before constructing the output path. This is the most actionable item.
- **S2 (MEDIUM):** `plugin_pack_template` should either validate that `name` is a valid Python identifier or sanitize it (e.g., replace hyphens with underscores). The generated code must be syntactically valid.
- **S3-S6 (LOW):** Noted for future cleanup. Do not block commit.
- **T1-T5:** Test gaps to address in a follow-up. Do not block commit.
- **D1-D3:** Semantic drift risks to track. Do not block commit.
