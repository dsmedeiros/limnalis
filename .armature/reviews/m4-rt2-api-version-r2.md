# Red Team Review: m4-rt2-api-version-r2 (Re-review)

## Summary

This is a re-review after fixes to findings H1 (version drift) and H2 (missing evaluator types). Both issues have been addressed in the source modules. All 26 tests pass (up from 25 -- the new `test_version_matches_pyproject_toml` was added). However, the H2 fix is only half-applied: `api/evaluator.py` now exports the types, but the test still imports from the internal path, and the expected-names assertion does not cover the three new exports. One new MEDIUM issue found regarding the test importing from the wrong path. No critical or high-severity findings remain.

## Critical Findings

None.

## Subtle Issues

### S1 -- `test_evaluate_via_public_api` still imports from internal path (MEDIUM)

- **File:** `tests/test_public_api.py` line 112
- **What:** Line 112 reads `from limnalis.runtime.models import EvaluationEnvironment, SessionConfig, StepConfig`. These three types are now correctly exported from `limnalis.api.evaluator` (the H2 fix), but the test that purports to exercise the "public API" still reaches into the internal module. This means the public API re-export path for these types is never actually exercised by any test. If the re-export were broken (e.g., a typo in the import inside `api/evaluator.py`), the test would still pass because it bypasses the public path entirely.
- **How to trigger:** Break the import of `EvaluationEnvironment` in `api/evaluator.py` (e.g., rename it). All 26 tests still pass. The re-export is dead code from a test-coverage perspective.

### S2 -- `test_all_contains_expected_names` omits the three new evaluator exports (MEDIUM)

- **File:** `tests/test_public_api.py` lines 65-68
- **What:** The parametrized expected names for `limnalis.api.evaluator` list `BundleResult`, `EvaluationResult`, `PrimitiveSet`, `SessionResult`, `StepResult`, `run_bundle`, `run_session`, `run_step` -- eight names. But `api/evaluator.py.__all__` now has eleven names (the eight plus `EvaluationEnvironment`, `SessionConfig`, `StepConfig`). The test does not assert the presence of the three new exports. While the generic `test_all_matches_actual_exports` verifies everything in `__all__` is importable, the specific expected-names test is the contract test that would catch accidental removal. These three types are not covered by it.

### S3 -- `SPEC_VERSION` still not accessible via `limnalis.api` (LOW, unchanged)

- **File:** `src/limnalis/__init__.py` line 14
- **What:** `SPEC_VERSION` remains in `limnalis.__all__` but is not exposed through any `limnalis.api.*` submodule. `get_version_info()` is similarly absent from the API layer. This was noted in the prior review (H3) and is not a regression, just unfixed.

### S4 -- `Typing :: Typed` classifier without `py.typed` marker (LOW, unchanged)

- **File:** `pyproject.toml` line 21
- **What:** Still no `py.typed` marker file. Same as prior review H4.

### S5 -- `importlib.abc.Traversable` deprecation (LOW, unchanged)

- **File:** `src/limnalis/schema.py` line 7
- **What:** Still triggers a DeprecationWarning on Python 3.13. Same as prior review H5.

## Test Gaps

### G1 -- Re-export of `EvaluationEnvironment`/`SessionConfig`/`StepConfig` via public API is untested (NEW)

No test imports these three types from `limnalis.api.evaluator` and uses them. The only functional test (`test_evaluate_via_public_api`) imports them from the internal path. This means the H2 fix is structurally present but functionally unverified.

### G2 -- `__all__` completeness remains one-directional (unchanged)

Same as prior review G2. Tests verify every name in `__all__` is importable, but not that every public name in the module is in `__all__`.

### G3 -- End-to-end evaluation test checks only type, not content (unchanged)

Same as prior review G3. `test_evaluate_via_public_api` asserts `isinstance(bundle_result, BundleResult)` only.

### G4 -- No negative tests via public API (unchanged)

Same as prior review G4. No test passes invalid input through the public API normalizer.

### G5 -- Conformance API not functionally tested (unchanged)

Same as prior review G6. All conformance exports are import-checked only.

## Semantic Drift Risks

### D1 -- `NormalizationResult` vs Pydantic BaseModel inconsistency (unchanged)

Same as prior review D1.

## Verification of Prior Findings

| Finding | Status | Evidence |
|---------|--------|----------|
| H1 (version drift) | **FIXED** | `test_version_matches_pyproject_toml` at line 163 parses `pyproject.toml` via `tomllib` and compares to `limnalis.__version__`. Test passes. |
| H2 (missing evaluator types) | **PARTIALLY FIXED** | `api/evaluator.py` now exports `EvaluationEnvironment`, `SessionConfig`, `StepConfig` in both imports and `__all__`. However, no test exercises the public path (see S1, S2, G1). |
| G1 (pyproject version sync) | **FIXED** | Covered by `test_version_matches_pyproject_toml`. |
| H3 (SPEC_VERSION) | Unchanged | Not addressed. |
| H4 (py.typed) | Unchanged | Not addressed. |
| H5 (Traversable deprecation) | Unchanged | Not addressed. |

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **S1 + S2 + G1 (MEDIUM):** The H2 fix for evaluator type exports is structurally correct but has zero test coverage through the public API path. `test_evaluate_via_public_api` should import `EvaluationEnvironment`, `SessionConfig`, `StepConfig` from `limnalis.api.evaluator` instead of `limnalis.runtime.models`. The expected-names list for `limnalis.api.evaluator` should include all eleven names.
- **S3 (LOW):** Consider exposing version metadata via `limnalis.api` or documenting the intended import path.
- **S4 (LOW):** Add `py.typed` marker or remove the `Typing :: Typed` classifier.
- **S5 (LOW):** Address `importlib.abc.Traversable` deprecation before Python 3.14.
