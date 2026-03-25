# Red Team Review: 3c-redteam-tests

## Summary

The 3C test suite passes all 231 tests and covers the declared conformance targets. However, the diagnostic comparison logic has a structural blind spot: it only checks that expected diagnostics appear in actuals, never that unexpected actuals are absent. This means spurious diagnostics go undetected by the entire conformance harness. The determinism tests verify function purity (same input -> same output) but do not verify canonical ordering under varied inputs. Several edge-case paths in `_compare_diagnostics` crash on `None` input rather than degrading gracefully.

## Critical Findings

### FINDING-1: `_compare_diagnostics` ignores unexpected actual diagnostics (HIGH)

- **File:** `src/limnalis/conformance/compare.py`, lines 397-437
- **What:** The function iterates over `expected_diags` and searches for matches in `actual_diags`. It never checks whether `actual_diags` contains entries not present in `expected_diags`. Extra actual diagnostics are silently ignored.
- **How to trigger:** Any conformance case that produces a spurious diagnostic (e.g., a regression that emits an extra warning) will still pass comparison as long as the expected diagnostics are present.
- **What happens:** False green. The conformance suite reports PASS for a case that has unexpected error diagnostics in its output.
- **Severity:** HIGH. This undermines the diagnostic contract: if the fixture corpus specifies exactly which diagnostics should appear, extra diagnostics should be flagged as mismatches.

### FINDING-2: `compare_case` skips diagnostic comparison when `expected_diags` is empty list (HIGH)

- **File:** `src/limnalis/conformance/compare.py`, line 491
- **What:** The guard `if expected_diags:` treats an empty list `[]` the same as an absent key. A fixture case that explicitly declares `"diagnostics": []` (meaning "no diagnostics expected") will not flag any actual diagnostics as mismatches.
- **How to trigger:** A case with `"diagnostics": []` in expected, where the runtime produces error diagnostics. `compare_case` returns `passed=True`.
- **What happens:** False green. Cases that should be diagnostic-clean pass even when they emit diagnostics.
- **Severity:** HIGH. This is a truthiness bug: `if []:` is falsy in Python.

## Subtle Issues

### ISSUE-1: `_compare_diagnostics` crashes on `None` input

- **File:** `src/limnalis/conformance/compare.py`, lines 408-410
- **What:** If either `expected_diags` or `actual_diags` is `None`, the function raises `TypeError: 'NoneType' object is not iterable`. The caller (`compare_case`) uses `.get("diagnostics", [])` which guards against missing keys, but a malformed fixture with `"diagnostics": null` would crash.
- **Severity:** MEDIUM. Low probability in current corpus, but no defensive guard.

### ISSUE-2: Diagnostic contract tests (TestDiagnosticContractEnforcement) do not test the extra-actual blind spot

- **File:** `tests/test_conformance.py`, lines 604-669
- **What:** All five tests in this class test the happy path (severity mismatch, code mismatch, subject mismatch, exact match, stable ordering). None of them test the scenario where actual diagnostics contain entries not in expected. Given FINDING-1, this means the tests validate only the non-missing direction of the contract, not the non-extra direction.
- **Severity:** MEDIUM. The tests are not tautological (they do exercise real comparison logic), but they have a systematic blind spot that mirrors the code's blind spot.

### ISSUE-3: Determinism tests prove purity, not canonical ordering

- **File:** `tests/test_conformance.py`, lines 706-784
- **What:** All four `TestDeterminism` tests run the same case twice with identical input and assert identical output. This proves the function is deterministic (pure), which is valuable. However, it does not prove that ordering is *canonical* — i.e., that different inputs producing the same logical set of results would be ordered consistently. For example, `test_deterministic_evaluator_iteration_ordering` runs A8 twice but does not test whether evaluator iteration order is stable under different evaluator insertion orders.
- **Severity:** MEDIUM. The tests are useful but their names and docstrings overclaim. They prove determinism, not canonicalization.

### ISSUE-4: The renamed baseline tests leave a gap in the validation chain

- **Files:** `tests/test_ast_models.py:104`, `tests/test_normalizer.py:106`
- **What:** Both tests were changed from asserting rejection to asserting acceptance. The docstrings say "caught at runtime instead" and "validation is at runtime." The A4 conformance case (`TestNewTargets3C.test_a4_baseline_modes`) does exercise the runtime path end-to-end, so the gap is covered — but only through the conformance harness. There is no unit-level test of the runtime `resolve_baseline` function that directly asserts `baseline_mode_invalid` diagnostic emission for a `moving+fixed` combination.
- **Severity:** MEDIUM. The end-to-end test via A4 conformance covers it, but a unit-level regression test for `resolve_baseline` would be more robust against future refactoring.

## Test Gaps

1. **No test for extra/unexpected actual diagnostics.** Neither `_compare_diagnostics` unit tests nor any conformance test verifies that extra actual diagnostics are flagged. This is the most significant gap.

2. **No test for `expected_diags: []` (empty list) vs absent key.** A case explicitly declaring zero expected diagnostics should fail if diagnostics appear. Currently passes silently.

3. **No test for `_compare_diagnostics` with `None` inputs.** Would crash with `TypeError`.

4. **No unit test for `resolve_baseline` emitting `baseline_mode_invalid`.** Only tested via A4 conformance end-to-end. If the conformance runner changes, this check could silently break.

5. **No test for `compare_case` when `expected` has zero claims in a step.** The step comparison iterates `claims_exp.items()` which would be empty, silently skipping all claim comparison. If the actual step has claim results, they go unchecked. Same pattern as the diagnostic extra-actual gap but for claims/blocks/transports.

6. **No test for `validate_result_schema` raising unexpected exceptions inside the conformance runner.** The monkeypatch test (`test_run_case_schema_validation_fallback_preserves_specific_diagnostic`) tests the `ValueError` path, but not other exception types.

7. **No negative test for `_run_and_compare` helper.** The `TestMismatchDetection` class tests `compare_case` directly with tampered data, but there is no test that `_run_and_compare` itself actually calls `pytest.fail` on mismatch. The helper's structure is sound (line 63: `pytest.fail(...)`) but its contract is not independently tested.

## Semantic Drift Risks

1. **`_compare_diagnostics` docstring says "Matching is done by (code, severity) pair"** but the function actually matches by (code, severity, subject) triple when subject is present in expected. The docstring understates the matching criteria.

2. **Test name `test_stable_diagnostic_ordering`** in `TestDiagnosticContractEnforcement` (line 654) is a duplicate concern with `test_deterministic_diagnostic_ordering` in `TestDeterminism` (line 726). Both run A12 twice and compare diagnostic lists. One lives in the "contract enforcement" class, the other in the "determinism" class. This is not a bug but it inflates apparent coverage.

3. **The parametrized normalizer test excludes A4** (`case_id != "A4"` at line 98 of `test_normalizer.py`). The separate `test_normalizer_accepts_invalid_moving_baseline_fixture` test covers A4 without schema validation. This means A4 is the only corpus case whose normalized AST is never validated against the schema in the normalizer tests. The conformance runner's schema fallback path handles this, but it's an asymmetry worth noting.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **[HIGH] FINDING-1 + FINDING-2:** `_compare_diagnostics` does not flag extra/unexpected actual diagnostics, and `compare_case` skips comparison entirely for empty expected diagnostic lists. These together mean the conformance suite cannot detect diagnostic regressions where new spurious diagnostics appear. Should be addressed before relying on diagnostic counts for correctness.
- **[MEDIUM] ISSUE-2:** Add a test that asserts extra actual diagnostics ARE flagged (once the code is fixed to detect them).
- **[MEDIUM] ISSUE-3:** Consider renaming determinism tests to accurately reflect they prove purity/repeatability, not canonical ordering.
- **[MEDIUM] ISSUE-4 + Gap 4:** Add a unit test for `resolve_baseline` directly.
- **[MEDIUM] Gap 5:** The same extra-actual blind spot exists for claims, blocks, and transports in session comparison — actual results not referenced by expected are silently ignored.
