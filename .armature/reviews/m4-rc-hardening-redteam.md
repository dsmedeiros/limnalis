# Red Team Review: m4-rc-hardening

## Summary

The Milestone 4 RC hardening changeset is structurally sound. All 308 tests pass, 16/16 conformance cases PASS, and the new public API surface correctly re-exports internal symbols. The CLI refactor is clean and well-organized. One HIGH finding exists: the `conformance run` and `conformance report` subcommands classify error-vs-allowlist cases in different priority order, which can cause the `run` command to silently mask runner errors as "KNOWN" deviations. Several test gaps and minor issues are noted below.

## Critical Findings

None.

## Subtle Issues

### S1: SPEC_VERSION defined in two places (MEDIUM)

- **Files:** `src/limnalis/__init__.py` line 7 and `src/limnalis/version.py` line 6
- **What:** `SPEC_VERSION = "v0.2.2"` is hardcoded in both files as independent string literals. They are currently equal but are not the same object and not derived from a single source of truth.
- **Risk:** If a future version bump updates one but not the other, schema loading (which imports from `__init__`) will use a different version string than `get_version_info()` (which imports from `version.py`). This would cause silent schema mismatches.
- **How to trigger:** Update `version.py:SPEC_VERSION` without updating `__init__.py:SPEC_VERSION` (or vice versa). The schema loader will look for the wrong filename.

### S2: Error/allowlist priority inconsistency between `run` and `report` (HIGH)

- **File:** `src/limnalis/cli.py`
- **What:** In `_run_conformance_run` (line 694-718), the priority order is PASS > KNOWN (allowlist) > ERROR > FAIL. In `_run_conformance_report` (line 756-772), the priority order is ERROR > PASS > KNOWN > FAIL.
- **Risk:** If a case is in the allowlist AND has a runner error, the `run` command silently classifies it as "KNOWN" (skipped), while the `report` command correctly classifies it as "error". This can mask real runner failures during `conformance run`.
- **How to trigger:** Add a case ID to an allowlist file. Make the runner produce an error for that case (e.g., by causing a parse/normalize crash). Run `conformance run --allowlist <file>` -- the error will be hidden as "KNOWN". Run `conformance report --allowlist <file>` -- the error will correctly surface as "error".

### S3: `except (json.JSONDecodeError, Exception)` is semantically redundant (LOW)

- **File:** `src/limnalis/cli.py` lines 288, 403, 436
- **What:** `Exception` is a superclass of `json.JSONDecodeError`, so `(json.JSONDecodeError, Exception)` catches exactly the same set as `Exception` alone. The isinstance-based routing inside the handler works correctly, so this is not a bug, but the except clause is misleading -- it suggests `json.JSONDecodeError` has special handling at the exception-matching level when it does not.

### S4: `_run_conformance_run` and `_run_conformance_report` type `corpus` as `object` (LOW)

- **File:** `src/limnalis/cli.py` lines 664 and 740
- **What:** Both functions accept `corpus: object` then call `.cases`, `.get_case()`, `.case_ids()` on it. This is duck-typed and works at runtime, but mypy would flag these attribute accesses on `object`.

## Test Gaps

### T1: No tests for `parse --json` flag

No test exercises the `limnalis parse --json` code path. The `_tree_to_dict` helper function (lines 377-383) in `_cmd_parse` is untested. Manual verification confirms it works, but there is no regression guard.

### T2: No tests for `evaluate --normalized` flag

The `evaluate` command's `--normalized` flag (which loads a pre-normalized AST JSON/YAML file instead of surface source) has no test coverage. The code path at `cli.py` line 530-531 is untested.

### T3: No tests for `--strict` or `--allowlist` flags

The `conformance run --strict`, `conformance run --allowlist`, `conformance report --strict`, and `conformance report --allowlist` flags are all untested. The `_load_allowlist` function (lines 275-310) has no dedicated test.

### T4: `TestExactSetMatching` in `test_property.py` is tautological

The `TestExactSetMatching` class (lines 136-165) tests Python's built-in `set` equality semantics, not any limnalis code. It asserts `set(A) == set(B)` and `set(A) != set(A | {extra})` -- these are properties of Python's `set` type, not properties of the system under test. These tests prove nothing about limnalis correctness.

### T5: No negative test for `conformance show` with invalid case ID via CLI

The test `test_conformance_show` in `test_conformance.py` only tests the happy path (case "A1"). There is no test verifying that `conformance show <invalid_id>` returns a non-zero exit code with a helpful error message.

### T6: `test_parse_invalid_file` and `test_normalize_invalid_file` catch all exceptions

In `test_cli_smoke.py` lines 101-118, both tests wrap the assertion in `try/except (SystemExit, FileNotFoundError, Exception)` with a `pass` body, meaning the test passes whether `main()` returns a non-zero code, raises an exception, or does literally anything. These tests are effectively no-ops.

## Semantic Drift Risks

### D1: `version.py` PACKAGE_VERSION vs `pyproject.toml` version

`version.py` defines `PACKAGE_VERSION = "0.2.2rc1"` and `pyproject.toml` defines `version = "0.2.2rc1"`. These are two independent sources of truth for the package version. Neither is derived from the other. A version bump that updates one but not the other will produce inconsistent behavior: `limnalis.__version__` will differ from the installed package metadata version.

### D2: `importlib.abc.Traversable` deprecation warning

`schema.py` imports `from importlib.abc import Traversable` which is deprecated in Python 3.14. The project currently targets 3.11-3.13, so this is not a current bug, but it will become one when Python 3.14 support is added. The warning already appears in the test output.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **S2 (HIGH):** Fix the error/allowlist priority inconsistency in `_run_conformance_run` so that errors are checked before the allowlist, matching the behavior of `_run_conformance_report`.
- **S1 (MEDIUM):** Consolidate `SPEC_VERSION` to a single source of truth. Either `__init__.py` should import from `version.py`, or both should be eliminated in favor of a single definition.
- **T1-T3:** Add tests for the `parse --json`, `evaluate --normalized`, `--strict`, and `--allowlist` code paths.
- **T4:** Replace or remove the tautological `TestExactSetMatching` class. If exact-set matching is used in conformance comparison, test the actual conformance comparison function.
- **T6:** Fix the catch-all exception handling in `test_parse_invalid_file` and `test_normalize_invalid_file` so they actually assert the expected behavior rather than passing unconditionally.
- **D1:** Derive `PACKAGE_VERSION` from `pyproject.toml` or vice versa to prevent drift.
