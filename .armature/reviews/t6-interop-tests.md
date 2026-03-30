# Review: T6 -- Envelope + Round-trip + Package + Determinism Tests

**Reviewer:** compliance-reviewer
**Date:** 2026-03-30
**Verdict:** PASS

---

## Scope Compliance

| Check | Result |
|---|---|
| Only tests/ files created? | PASS -- three files: `tests/test_interop_envelopes.py`, `tests/test_interop_export_import.py`, `tests/test_interop_package.py` |
| No writes to src/? | PASS -- the `src/limnalis/interop/__init__.py` diff is a pre-existing uncommitted change (adds `project_linkml_schema` import from a separate task). T6 test files do not reference or depend on it. |
| Public API only? | PASS -- all three files import exclusively from `limnalis.interop`. No internal module imports. |

## Coverage Assessment

| Area | Covered | Notes |
|---|---|---|
| SourceInfo | Yes | Creation, defaults, extra-field rejection, serialization |
| ASTEnvelope | Yes | Creation, defaults, extra-field rejection, serialization |
| ResultEnvelope | Yes | Creation, extra-field rejection, serialization |
| ConformanceEnvelope | Yes | Creation, optional fields, extra-field rejection, serialization |
| export_ast (from source) | Yes | JSON + YAML formats, source_info inclusion |
| export_ast_from_dict | Yes | JSON + YAML, custom SourceInfo |
| export_result | Yes | JSON + YAML |
| export_conformance | Yes | JSON + YAML, corpus_version |
| import_ast_envelope | Yes | JSON string, YAML string, dict, JSON file, YAML file, error cases (missing format, bad extension) |
| import_result_envelope | Yes | Via round-trip tests |
| import_conformance_envelope | Yes | Via round-trip tests |
| Round-trips (export then import) | Yes | AST from source (JSON+YAML), result (JSON+YAML), conformance (JSON+YAML) |
| Determinism | Yes | Four tests verifying repeated exports produce identical output |
| create_package | Yes | Directory + zip formats, multi-artifact, version metadata, SHA256 checksum verification |
| inspect_package | Yes | Directory + zip |
| validate_package | Yes | Valid packages, missing manifest, checksum mismatch, missing files |
| extract_package | Yes | From zip and directory |
| Full package round-trip | Yes | create -> inspect -> validate -> extract for both directory and zip |

## Test Quality

- **Assertions:** Specific and meaningful -- checking exact values, types, field presence.
- **Edge cases:** Extra-field rejection (MODEL-002 enforcement), missing format parameter, bad file extension, missing manifest, tampered checksums, missing files.
- **Cleanup:** All filesystem operations use `tmp_path` fixture (pytest-managed cleanup).
- **Determinism:** Tests are order-independent; no shared mutable state.
- **Naming:** Follows `test_{component}_{aspect}.py` convention per `tests/agents.md`.

## Invariant Compliance

- **MODEL-002:** Extra-field rejection tested for all four envelope/model types.
- **NORM-001:** Determinism tests verify repeated export produces identical output (aligned with normalizer determinism requirement).
- **FIXTURE-001:** Tests do not modify fixtures; they use `examples/minimal_bundle.lmn` read-only.

## Test Execution

All 59 tests pass (25% envelopes, 47% export/import, 28% package). No errors, no failures. One unrelated deprecation warning from `importlib.abc.Traversable`.

## Notes

- The uncommitted change to `src/limnalis/interop/__init__.py` (adding `project_linkml_schema`) is outside T6 scope and should be committed separately as part of its own task.
- Total test count: 15 envelope + 28 export/import + 16 package = 59 tests.
