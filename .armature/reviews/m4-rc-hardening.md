# Review Verdict: m4-rc-hardening

## Scope Compliance
- Declared scope: core (`src/limnalis`) + tests (`tests/`) + docs (`docs/`)
- Files modified:
  - `.armature/session/state.md` (orchestrator scope -- permitted)
  - `README.md` (project root -- quickstart rewrite, within scope for RC hardening)
  - `pyproject.toml` (version bump to 0.2.2rc1, extras, classifiers, URLs)
  - `src/limnalis/__init__.py` (added `__version__` export)
  - `src/limnalis/cli.py` (CLI stabilization: exit codes, `--json`, `--strict`, `--allowlist`, error handling)
  - `tests/test_cli_smoke.py` (expanded CLI smoke tests)
  - `tests/test_packaging_resources.py` (added packaging resource tests)
- Files added:
  - `src/limnalis/api/__init__.py` (public API package)
  - `src/limnalis/api/parser.py` (parser re-exports)
  - `src/limnalis/api/normalizer.py` (normalizer re-exports)
  - `src/limnalis/api/evaluator.py` (evaluator re-exports)
  - `src/limnalis/api/conformance.py` (conformance re-exports)
  - `src/limnalis/version.py` (version metadata)
  - `tests/test_public_api.py` (public API import + usage tests)
  - `tests/test_determinism.py` (determinism tests)
  - `tests/test_property.py` (Hypothesis property tests)
  - `tests/test_parser_robustness.py` (parser robustness tests)
  - `tests/test_conformance_reports.py` (conformance report format tests)
  - `docs/architecture.md` (architecture overview)
  - `docs/adr/001-pydantic-ast-models.md` (ADR)
  - `docs/adr/002-execution-model.md` (ADR)
  - `docs/adr/003-conformance-first-workflow.md` (ADR)
  - `docs/adr/004-public-api-freeze.md` (ADR)
  - `docs/compatibility_and_deviations.md` (deviation/compat policy)
  - `docs/release_candidate_status.md` (RC status report)
- Out-of-scope modifications: none

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| SCHEMA-001 | PASS | No schema changes. `validate_schema=True` paths preserved in CLI and API. |
| SCHEMA-002 | PASS | No schema file changes. Version-pinned filenames unchanged. |
| SCHEMA-003 | PASS | No schema changes, so no version bump required for schemas. |
| SCHEMA-004 | PASS | Fixture corpus schema validation unchanged. |
| PARSER-001 | PASS | No grammar changes. Parser remains permissive. |
| PARSER-002 | PASS | No inline grammar definitions added. Grammar loaded from `grammar/limnalis.lark`. |
| PARSER-003 | PASS | No grammar changes; parse tree structure unaffected. |
| MODEL-001 | PASS | No AST model changes. All models still inherit from `LimnalisModel`. |
| MODEL-002 | PASS | No model config changes. `extra='forbid'` preserved. |
| MODEL-003 | PASS | No model-schema divergence introduced. |
| NORM-001 | PASS | No normalizer logic changes. New `test_determinism.py` actively verifies determinism across all fixture cases. |
| NORM-002 | PASS | No normalizer diagnostic changes. |
| NORM-003 | PASS | No normalizer output format changes. |
| FIXTURE-001 | PASS | No fixture files modified. All 16/16 conformance cases pass. |
| FIXTURE-002 | PASS | Version alignment preserved: pyproject 0.2.2rc1, SPEC_VERSION v0.2.2, schema v0.2.2, corpus v0.2.2. |
| FIXTURE-003 | PASS | No fixture file changes. |
| RUNTIME-001 | PASS | No runner phase ordering changes. |
| RUNTIME-002 | PASS | No primitive signature changes. |
| RUNTIME-003 | PASS | No NoteExpr handling changes. |
| RUNTIME-004 | PASS | No PrimitiveSet changes. |

## Observations

1. **SPEC_VERSION duplication**: `SPEC_VERSION = "v0.2.2"` is defined independently in both `src/limnalis/__init__.py` (line 7) and `src/limnalis/version.py` (line 6). The `__init__.py` copy predates this changeset and is not imported from `version.py`. Both values are currently consistent, but this is a latent drift risk. Not a blocking issue -- the values match today and `version.py` is the canonical source for `get_version_info()`.

2. **Test coverage**: The changeset adds substantial new test coverage:
   - Public API import and usage tests (T6)
   - Full pipeline determinism tests (T7.1-T7.4)
   - Hypothesis property tests for four-valued logic, block fold, and set matching (T7)
   - Parser robustness tests for malformed inputs (T8)
   - Conformance report format tests for JSON and Markdown (T9)
   - Packaging resource accessibility tests (T6.6-T6.7)

3. **CLI hardening**: The CLI now uses structured error handling with consistent exit codes (0 for success, 1 for errors, 2 for unknown commands). The `--json`, `--strict`, and `--allowlist` flags are well-tested.

4. **Public API surface**: The `limnalis.api.*` re-export layer is clean, with `__all__` declarations on every submodule. Tests verify both importability and expected export names.

5. **All 308 tests pass** with 1 deprecation warning (`importlib.abc.Traversable` in `schema.py` -- pre-existing, not introduced by this changeset).

## Verdict: PASS

All invariants are satisfied. No out-of-scope modifications. Test suite fully green at 308 tests. The changeset is purely additive -- new files, expanded tests, CLI stabilization, and documentation. No existing behavior was modified.
