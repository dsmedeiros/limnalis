# Review: T7 -- CLI + LinkML Projection + Compatibility Tests

**Reviewer:** compliance-reviewer
**Date:** 2026-03-30
**Verdict:** PASS

## Files Under Review

| File | Tests | Status |
|---|---|---|
| `tests/test_cli_interop.py` | 12 | PASS |
| `tests/test_interop_linkml.py` | 8 | PASS |
| `tests/test_interop_compat.py` | 4 | PASS |

All 24 tests pass (pytest exit 0, 1.08s).

## 1. Scope Compliance

**PASS.** All three files reside in `tests/`. No files outside the declared scope were created or modified by this task.

## 2. Public API Only

**PASS.** Imports are limited to:

- `limnalis.cli.main` -- the public CLI entry point
- `limnalis.interop.ProjectionResult`, `project_linkml_schema` -- exported in `__init__.py` and `__all__`
- `limnalis.interop.ASTEnvelope`, `SCHEMA_VERSION`, `SPEC_VERSION`, `check_envelope_compatibility` -- all exported in `__init__.py` and `__all__`

No private/internal module imports. No `_`-prefixed symbols accessed.

## 3. Coverage Assessment

### CLI commands (`test_cli_interop.py`, 12 tests)
- `export-ast`: JSON output, YAML output, nonexistent file error -- **covered**
- `export-result`: happy path with tmp file -- **covered**
- `export-conformance`: happy path with tmp file -- **covered**
- `package-create/inspect/validate/extract`: full lifecycle with tmp_path -- **covered**
- `project-linkml`: default target and `--target evaluation_result` -- **covered**
- `--version`: structured JSON output with version fields -- **covered**

### LinkML projection (`test_interop_linkml.py`, 8 tests)
- Return type validation for all three source models (ast, evaluation_result, conformance_report) -- **covered**
- File output and YAML validity -- **covered**
- Warnings and lossy_fields population -- **covered**
- Deterministic regeneration (stability) -- **covered**
- Top-level schema keys (id, name, classes, prefixes, default_range) -- **covered**

### Compatibility checking (`test_interop_compat.py`, 4 tests)
- Matching versions (empty list) -- **covered**
- Mismatched spec_version only -- **covered**
- Mismatched schema_version only -- **covered**
- Both mismatched (two issues) -- **covered**

## 4. Test Quality

- **Assertions:** All tests contain substantive assertions (not just `code == 0`). Structural checks on JSON payloads, field presence, type checks, and content validation.
- **Edge cases:** Nonexistent file path for export-ast. Both single and double version mismatches for compat. Three different source models for LinkML.
- **Cleanup:** Uses pytest `tmp_path` fixture for all filesystem operations; no manual cleanup needed, no test pollution.
- **Determinism:** No randomness, no network calls, no ordering dependencies. Stability test compares two runs of the same projection.
- **Naming:** Follows `test_{component}_{aspect}.py` convention per `tests/agents.md`.

## 5. Invariant Compliance

No invariants are violated:
- Tests do not modify fixture files or schemas (restricted per `tests/agents.md`)
- Tests are deterministic and order-independent
- File naming follows conventions

## 6. Observations

- Test count is 24 (12 + 8 + 4), not 25 (13 + 8 + 4) as declared in the task scope. `test_cli_interop.py` contains 12 tests, not 13. Minor discrepancy in the task declaration but not a blocking issue.
- The `DeprecationWarning` from `importlib.abc.Traversable` in `schema.py` is pre-existing and unrelated to this task.

## Conclusion

All checks pass. The test suite provides solid coverage of the CLI interop commands, LinkML projection pipeline, and envelope compatibility checker using only public API surfaces, with proper cleanup and meaningful assertions.
