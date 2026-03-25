# Red Team Review: 3C — Models and Normalizer (BaselineNode focus)

## Summary

The removal of the `_moving_requires_tracked` model validator from `BaselineNode` creates a **silent correctness gap** in the normalization pipeline. The vendored JSON schema (`limnalis_ast_schema_v0.2.2.json`) still enforces `moving -> evaluationMode=tracked` via an `allOf/if-then` constraint. This means the Pydantic model layer now accepts invalid combinations that the schema layer rejects. The test suite has been specifically structured to avoid exercising this gap: the A4 fixture test bypasses `validate_payload`, and A4 is excluded from the parametrized corpus test that does validate. The public API (`normalize_surface_text`, `load_surface_bundle`) correctly rejects A4 via schema validation, so production consumers are protected. However, the test suite creates a false impression that `moving+fixed` is a fully valid normalization output.

## Critical Findings

### 1. A4 fixture produces schema-invalid AST that no test catches (MEDIUM)

- **File:** `tests/test_normalizer.py`, lines 106-112
- **What:** `test_normalizer_accepts_invalid_moving_baseline_fixture` normalizes A4 and asserts `kind=moving, evaluationMode=fixed` without calling `validate_payload`. Meanwhile, all other fixture cases go through `_normalize_source` which calls `validate_payload`. A4 is explicitly excluded from the parametrized test at line 98: `sorted(case_id for case_id in FIXTURE_CASES if case_id != "A4")`.
- **How to trigger:** `normalize_surface_text(a4_source, validate_schema=True)` raises `SchemaValidationError: ast schema validation failed at $.baselines[3].evaluationMode: 'tracked' was expected`
- **What happens:** The test passes, giving the impression that A4 normalizes into a valid AST. In reality, A4's output is schema-invalid and would be rejected by every public API entry point (`normalize_surface_text`, `normalize_surface_file`, `load_surface_bundle`).
- **Severity:** MEDIUM. The production code is actually correct (schema validation catches it). The test is misleading but not a production bug.

### 2. Model-schema constraint divergence violates SCHEMA-001 (HIGH)

- **File:** `src/limnalis/models/ast.py`, line 371-378 (BaselineNode); `schemas/limnalis_ast_schema_v0.2.2.json` lines 686-701
- **What:** The JSON schema has an `allOf` block: `if kind=moving then evaluationMode must be "tracked"`. The Pydantic model has no such constraint. This means `BaselineNode.model_validate(data)` succeeds on data that `validate_payload(data, "ast")` rejects.
- **How to trigger:** `BaselineNode(node="Baseline", id="b1", kind="moving", criterion=..., frame=..., evaluationMode="fixed")` succeeds at the model layer but its `.to_schema_data()` output fails schema validation.
- **What happens:** Any code path that constructs a BaselineNode and trusts it without subsequent schema validation can produce invalid data. The invariant registry declares SCHEMA-001: "Every normalized AST must validate against vendored schema." The normalizer alone no longer guarantees this -- schema validation is now a required post-step, enforced only by the loader layer.
- **Severity:** HIGH. The model and schema disagree about what constitutes valid data. This violates the defense-in-depth principle where model validation is the first line of enforcement.

## Subtle Issues

### 1. Schema validation is the sole enforcement point for moving+evaluationMode constraint

With the model validator removed, the constraint enforcement chain is:

1. ~~Pydantic model validator~~ (removed)
2. JSON schema `allOf/if-then` (via `validate_payload` in loader)
3. Runtime `resolve_baseline` (emits diagnostic but continues execution)

If anyone bypasses `validate_payload` (e.g., constructing a `Normalizer` directly without the loader wrapper, which is exactly what the test does), the invalid combination passes silently until runtime, where it becomes a diagnostic rather than an error. This is a defense-in-depth regression.

### 2. The test name is misleading

`test_normalizer_accepts_invalid_moving_baseline_fixture` and `test_moving_baseline_invalid_mode_accepted_at_model_layer` both state "accepted at model layer" / "caught at runtime instead." This framing implies the design intent is for schema validation to NOT catch this. But schema validation DOES catch it, and all production code paths include schema validation. The tests are documenting what appears to be an intentional relaxation but the schema was never relaxed to match.

### 3. No test verifies that the public API rejects A4

There is no test asserting that `normalize_surface_text(a4_source)` raises `SchemaValidationError`. The only test for A4 goes through the raw `Normalizer()` without schema validation. If the schema constraint were accidentally removed in a future schema update, no test would catch the regression.

## Test Gaps

1. **Missing negative test for A4 via public API:** No test proves that `normalize_surface_text(a4_source, validate_schema=True)` raises `SchemaValidationError` for the moving+fixed baseline. This is the actual production behavior and it is untested.

2. **Missing test for schema-model alignment on BaselineNode:** No test systematically verifies that everything the Pydantic model accepts also passes schema validation. A parametrized test over `(kind, evaluationMode)` combinations would catch future divergence.

3. **The A4 exclusion from parametrized tests is not documented:** Line 98 silently excludes A4 with no comment explaining why. A reader would not know this is intentional without cross-referencing the separate A4-specific test.

## Semantic Drift Risks

1. **"Validation at runtime" framing vs. actual behavior:** The test docstrings say "caught at runtime instead" but the actual catch point is schema validation in the loader, which runs before any runtime execution. The runtime `resolve_baseline` function also catches it, but as a diagnostic, not an error. These are three different behaviors (model reject, schema reject, runtime diagnose) and the codebase conflates the latter two.

2. **SPEC_VERSION as module-level constant in `__init__.py`:** The import `from limnalis import SPEC_VERSION` in `schema.py` (line 15) works today because `SPEC_VERSION` is defined before any other imports in `__init__.py`. However, `__init__.py` line 5 imports from `.loader`, which imports from `.schema`. This is a circular import that only works because Python caches partially-initialized modules. The `SPEC_VERSION = "v0.2.2"` assignment on line 3 executes before the circular chain begins, so the import resolves. This is fragile: if anyone adds an import above `SPEC_VERSION` that triggers `.schema` loading, it would break. No circular import risk exists today, but the ordering dependency is implicit and undocumented.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **[HIGH] Model-schema constraint divergence on BaselineNode:** The Pydantic model accepts `moving+fixed` but the JSON schema rejects it. Production code is protected by schema validation in the loader layer, but this divergence violates the principle that model validation should be a superset of schema validation constraints. Consider either: (a) re-adding a model validator that rejects `moving+evaluationMode!=tracked`, or (b) adding a prominent comment in BaselineNode explaining why the constraint is deliberately relaxed and where it is enforced instead.
- **[MEDIUM] Add a test proving the public API rejects A4:** A test like `with pytest.raises(SchemaValidationError): normalize_surface_text(a4_source)` would document and protect the actual production behavior.
- **[MEDIUM] Add a comment to the A4 exclusion in the parametrized test:** Line 98 of `test_normalizer.py` should explain why A4 is excluded.
- **[LOW] Document the `__init__.py` import ordering dependency:** The `SPEC_VERSION` constant must remain above the wildcard imports for `schema.py` to resolve it without circular import failure.
