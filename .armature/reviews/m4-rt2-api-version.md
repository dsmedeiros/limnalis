# Red Team Review: m4-rt2-api-version

## Summary

The public API surface (`limnalis.api.*`) and version metadata are well-structured and mostly correct. All 25 tests pass. Re-exports are accurate -- every name in every `__all__` exists in the source module. However, there is one HIGH-severity issue (version drift risk between `pyproject.toml` and `version.py`), one MEDIUM issue (public API test uses internal imports), and several test gaps that reduce the actual assurance these tests provide.

## Critical Findings

None.

## Subtle Issues

### H1 -- Version string duplicated in two authoritative locations with no sync guard (HIGH)

- **File:** `pyproject.toml` line 7 (`version = "0.2.2rc1"`) and `src/limnalis/version.py` line 5 (`PACKAGE_VERSION = "0.2.2rc1"`)
- **What:** The package version is declared as a literal string in two separate files. There is no mechanism (dynamic version via hatchling, build-time generation, or test assertion) that enforces these two values stay in sync.
- **How to trigger:** Edit one file but not the other during a release bump.
- **What happens:** `pip show limnalis` would report one version while `limnalis.__version__` reports another. Dependency resolution, caching, and debugging all break silently.
- **Note:** The test `test_version_consistency` in `test_public_api.py` only checks `limnalis.__version__ == get_version_info()["package"]`, which is tautological -- both derive from the same `version.py` constant. The `pyproject.toml` value is never compared.

### H2 -- `EvaluationEnvironment`, `SessionConfig`, `StepConfig` not exposed via public API (MEDIUM)

- **File:** `tests/test_public_api.py` line 112
- **What:** The `test_evaluate_via_public_api` test claims to test the public API, but imports `EvaluationEnvironment`, `SessionConfig`, and `StepConfig` from the internal path `limnalis.runtime.models`. These types are required parameters for `run_bundle`/`run_session`/`run_step`, making them de facto public API, yet they are not re-exported from `limnalis.api.evaluator`.
- **How to trigger:** Any user of `limnalis.api.evaluator.run_bundle` must also import from `limnalis.runtime.models`, defeating the purpose of the stable API facade.
- **What happens:** If `limnalis.runtime.models` is refactored (the API docs say internal paths may change without notice), downstream code breaks.

### H3 -- `SPEC_VERSION` exported from `limnalis.__init__` but not from `limnalis.api` (LOW)

- **File:** `src/limnalis/__init__.py` line 14
- **What:** `SPEC_VERSION` is in `limnalis.__all__` but is not exposed through any `limnalis.api.*` submodule, and `get_version_info()` / the version module itself are not re-exported from the API layer. Users wanting version metadata must import from the convenience `__init__` (unstable?) or directly from `limnalis.version` (internal?).

### H4 -- `Typing :: Typed` classifier without `py.typed` marker (LOW)

- **File:** `pyproject.toml` line 21
- **What:** The classifier `"Typing :: Typed"` is declared, but there is no `py.typed` marker file in `src/limnalis/`. PEP 561 compliance requires this file for type checkers (mypy, pyright) to treat the package as typed.

### H5 -- `importlib.abc.Traversable` deprecation warning (LOW)

- **File:** `src/limnalis/schema.py` line 7 (per test output)
- **What:** Importing `Traversable` from `importlib.abc` is deprecated in Python 3.13 and slated for removal in 3.14. The `pyproject.toml` claims 3.13 support.

## Test Gaps

### G1 -- `pyproject.toml` version vs `PACKAGE_VERSION` never compared

There is no test asserting `pyproject.toml`'s `version` field equals `limnalis.__version__`. The existing `test_version_consistency` is tautological on this axis since both sides read from `version.py`.

### G2 -- `__all__` completeness test is one-directional

`test_all_matches_actual_exports` verifies every name in `__all__` is importable, but does NOT verify that every public name in the module is declared in `__all__`. A new export added to (say) `api/evaluator.py` without updating `__all__` would go undetected.

### G3 -- End-to-end test does not verify evaluation output correctness

`test_evaluate_via_public_api` checks only `isinstance(bundle_result, BundleResult)`. It does not assert on any field of the result (e.g., that `session_results` is non-empty, that diagnostics or claims are present). This proves the function returns without crashing, not that it works.

### G4 -- No negative test for `normalize_surface_text` with invalid input

The public API normalizer exports `normalize_surface_text` but no test passes invalid surface syntax through it to verify that errors propagate correctly via the public API path.

### G5 -- No test that `EvaluationResult` alias works

`EvaluationResult = BundleResult` is exported from `api.evaluator` but never imported or used in any test.

### G6 -- Conformance API not functionally tested

`limnalis.api.conformance` exports `FixtureCase`, `compare_case`, `load_corpus`, `load_corpus_from_default`, and `run_case`. The tests only verify they are importable (via `__all__` checks). No test exercises any of these functions through the API layer.

## Semantic Drift Risks

### D1 -- `NormalizationResult` is a dataclass, not a Pydantic model

The normalizer source defines `NormalizationResult` as a `@dataclass`, while every other result type in the runner (`StepResult`, `SessionResult`, `BundleResult`) inherits from `BaseModel`. This inconsistency means `NormalizationResult` does not support `.model_dump()`, `.model_validate()`, or Pydantic serialization. Users who assume uniform Pydantic APIs across the public surface will be surprised.

### D2 -- `limnalis.__init__` imports are eager and heavy

`limnalis.__init__` eagerly imports from `loader`, `models.ast`, `normalizer`, and `schema`. This means `import limnalis` triggers Lark grammar compilation, Pydantic model metaclass setup, and jsonschema loading. For users who only need `limnalis.api.parser`, this is unnecessary overhead. The `api.*` modules are lighter since they import only their specific submodule, but `limnalis.__init__` re-exports overlap with `limnalis.api.*`, creating two import paths with different performance characteristics.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **H1 (HIGH):** Add a test that parses `pyproject.toml` and asserts its `version` field matches `limnalis.__version__`, or switch to hatchling dynamic versioning to eliminate the duplication.
- **H2 (MEDIUM):** Export `EvaluationEnvironment`, `SessionConfig`, and `StepConfig` from `limnalis.api.evaluator` so the public API is self-contained. Update the test to import from the public path.
- **G1-G6:** Strengthen tests per the gaps identified above, particularly G1 (version sync) and G3 (evaluation correctness).
- **H4 (LOW):** Add a `py.typed` marker file or remove the `Typing :: Typed` classifier.
- **H5 (LOW):** Migrate `importlib.abc.Traversable` usage before Python 3.14 removes it.
