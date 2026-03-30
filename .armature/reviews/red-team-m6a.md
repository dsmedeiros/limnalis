# Red Team Review: Milestone 6A (Interop Layer)

**Reviewer:** Red Team Adversarial Reviewer
**Date:** 2026-03-30
**Scope:** All new interop code, tests, CLI commands, and examples
**Test suite status:** All 196 tests PASS
**CLI commands:** All interop CLI commands execute successfully

---

## CRITICAL (must fix before merge)

### C1. [package.py:317] Path traversal vulnerability in `extract_package`

`extract_package` uses `zf.extractall(output_dir)` without any path traversal protection. A maliciously crafted zip file with entries like `../../../etc/crontab` could write files outside the intended extraction directory. While Python 3.13 on Windows resolves `../` sequences within the target in practice, this behavior is platform-dependent, undocumented as a security guarantee, and the project targets Python 3.11+ where behavior may differ.

**Fix:** Validate each member name before extraction. Reject entries containing `..` path components or absolute paths:

```python
for member in zf.namelist():
    member_path = Path(output_dir) / member
    if not str(member_path.resolve()).startswith(str(Path(output_dir).resolve())):
        raise ValueError(f"Path traversal detected in zip member: {member}")
zf.extractall(output_dir)
```

### C2. [linkml.py:168] Non-deterministic output violates NORM-001

`_JsonSchemaToLinkML.convert()` embeds a live timestamp in the `description` field:

```python
timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(...)
```

This makes the LinkML projection output non-deterministic -- two calls one second apart produce different output. The test `test_regeneration_produces_stable_output` works around this by comparing only parsed structure keys, masking the defect.

While NORM-001 technically governs the normalizer, the interop `agents.md` scoping document does not carve out an exception for projections, and deterministic serialization is a stated design goal throughout the codebase (sort_keys everywhere else).

**Fix:** Accept an optional `timestamp` parameter (defaulting to None meaning "omit" or a fixed sentinel), or move the timestamp to a YAML comment rather than a structural field that affects the serialized output.

---

## HIGH (should fix before merge)

### H1. [cli.py:374-382] `_load_data_file` does not validate return type

`_load_data_file` is annotated as returning `dict` but `yaml.safe_load()` can return any scalar or list for valid YAML (e.g., a file containing just `42` or `[1,2,3]`). The import module's `_parse_text` correctly validates with `if not isinstance(result, dict)`, but this CLI helper does not. If a user passes a non-object YAML file to `export-result` or `export-conformance`, the failure will surface as a confusing Pydantic validation error rather than a clear user-facing message.

**Fix:** Add `if not isinstance(result, dict): raise ValueError(...)` after `yaml.safe_load`.

### H2. [export.py:23,48,63,80,103] `format` parameter shadows Python builtin

Multiple functions use `format` as a parameter name (e.g., `export_ast(..., format=...)`) and as a keyword argument to `_serialize(data, format=format)`. While this works, it shadows the Python builtin `format()` function within those scopes. This is a code quality issue that can cause subtle bugs if someone later tries to use `format()` in those functions.

**Fix:** Rename to `output_format` or `fmt` throughout the interop API. This is also present in `import_.py`, `package.py`, and `cli.py`.

### H3. [linkml.py:454] LinkML YAML uses `sort_keys=False`

The `_render_yaml` function calls `yaml.dump(..., sort_keys=False)`. While the JSON serialization paths consistently use `sort_keys=True` for determinism, the LinkML YAML output does not sort keys. Since LinkML schema keys have semantic meaning in their ordering (e.g., `id` before `name` before `classes`), this may be intentional, but it means the output key order depends on dict insertion order from `_JsonSchemaToLinkML.convert()`, which in turn depends on `$defs` iteration order from `json_schema`. If Pydantic ever changes its JSON Schema generation order, the output changes silently.

**Fix:** Either document this as intentional and add a code comment explaining why, or use `sort_keys=True` for full determinism.

### H4. [package.py:233] Redundant zip file open in `validate_package`

`validate_package` opens the zip file twice: once at line 190 to read the manifest (closed at line 202), and again at line 233 for checksum and directory validation. The first open/close cycle is unnecessary -- the second open handles everything. This wastes resources and on Windows could cause transient file locking issues.

**Fix:** Restructure to open the zip file only once and keep it open for the entire validation.

### H5. Missing test: import of malformed/invalid envelope data

There are no negative test cases for `import_ast_envelope`, `import_result_envelope`, or `import_conformance_envelope` with structurally invalid data (e.g., missing required fields, wrong `artifact_kind` value). The `test_interop_export_import.py` file tests round-trips and format detection errors, but never tests that importing an envelope with `artifact_kind: "evaluation_result"` into `import_ast_envelope` fails with a clear error.

---

## MEDIUM (should fix, not blocking)

### M1. [__init__.py:38-63] `__all__` is not consistently sorted

The `__all__` list mixes uppercase-first entries (correctly sorted among themselves) with lowercase entries inserted in the middle. For example, `check_envelope_compatibility` and `project_linkml_schema` appear between `ResultEnvelope` and `SCHEMA_VERSION`. Proper ASCIIbetical sorting would place all uppercase names before lowercase names, or case-insensitive sorting should be used consistently.

Current order issue: `"ResultEnvelope"` (R) -> `"check_envelope_compatibility"` (c) -> `"project_linkml_schema"` (p) -> `"SCHEMA_VERSION"` (S) -- the `S` should come before `c` in ASCIIbetical order.

### M2. [linkml.py:38] `conformance_report` maps to `ExpectedResult` model

Both `evaluation_result` and `conformance_report` source models map to `("limnalis.models.conformance", "ExpectedResult")`. This seems intentional for now but is potentially misleading -- a "conformance report" and an "evaluation result" are conceptually different, and projecting both from the same Pydantic model suggests they should share a single key or the mapping should be documented as a known simplification.

### M3. [package.py:104-105] Variable shadowing in loop

Line 105 reassigns `src = Path(src)`, shadowing the loop variable with a different type. While functional, this is a style issue -- use a different name like `src_path = Path(src)` for clarity.

### M4. Missing test: empty package creation

No test verifies behavior when `create_package` is called with no artifact files at all (all lists empty/None). The function will create a package with an empty `artifact_types` list and no subdirectories, which may or may not be the intended behavior.

### M5. Missing test: determinism of `envelope_to_dict`

The `TestDeterminism` class tests serialized string output determinism but does not verify that `envelope_to_dict` itself produces deterministic dict key ordering. Since `envelope_to_dict` calls `model_dump(mode="json")` without `sort_keys`, the dict key order depends on Pydantic's internal ordering. The serializers (`_serialize`) compensate with `sort_keys=True`, but direct consumers of `envelope_to_dict` would not get sorted keys.

### M6. [cli.py:230] Overly broad exception catch in CLI handlers

All CLI command handlers catch `Exception` (the broadest possible catch). This swallows `KeyboardInterrupt` on Python < 3.12 and makes debugging difficult. Consider catching `(ValueError, OSError, RuntimeError)` or a custom exception hierarchy instead.

### M7. Missing test: CLI `--version` output matches `types.py` constants

The `test_version_flag` test checks that the output contains `spec_version`, `schema_version`, and `package_version` keys, but does not verify the values match `SPEC_VERSION` and `SCHEMA_VERSION` from `types.py`.

---

## LOW (nice to have)

### L1. [export.py:96-101] `envelope_to_dict` name suggests generic utility but is typed narrowly

The function accepts a union of three specific envelope types. If new envelope types are added, this function signature must be updated. Consider using a protocol or the common `LimnalisModel` base instead.

### L2. [linkml.py:275-279] Dead conditional branch

Lines 275-279 have identical behavior for both branches of `if ref_name in self._enum_names`:

```python
if ref_name in self._enum_names:
    attr["range"] = ref_name
else:
    attr["range"] = ref_name
```

Both branches do the same thing, making the conditional pointless dead code.

### L3. Example scripts use `print` statements

While examples are not library code, the global coding standard says "No print statements in library code; use structured diagnostics." The examples are fine for demonstration purposes, but consider adding a note that they are consumer-facing examples not governed by the library print restriction.

### L4. [types.py:10-11] Version constants are manually maintained

`SPEC_VERSION` and `SCHEMA_VERSION` are hardcoded strings in `types.py`. If the vendored schemas change version, these must be manually updated. Consider deriving them from the actual vendored schema filenames.

### L5. `import_` module name uses trailing underscore

The module is named `import_.py` to avoid collision with the Python `import` keyword. This is a standard Python convention and is fine, but worth noting that imports read slightly oddly: `from limnalis.interop.import_ import import_ast_envelope`.

---

## PASS (things that are correct)

- **MODEL-001 compliance:** All 7 new model classes (SourceInfo, ASTEnvelope, ResultEnvelope, ConformanceEnvelope, ExchangeManifest, ExchangePackageMetadata, ProjectionResult) inherit from LimnalisModel. Verified programmatically.

- **MODEL-002 compliance:** All 7 new model classes enforce `extra='forbid'`. Extra fields are rejected with ValidationError. Verified programmatically and via test assertions.

- **YAML safe_load usage:** `import_.py` correctly uses `yaml.safe_load` (not `yaml.load`). The CLI helper `_load_data_file` also uses `yaml.safe_load`. No unsafe YAML loading anywhere.

- **JSON serialization determinism:** All JSON serialization paths use `sort_keys=True` and `ensure_ascii=False` consistently via `_serialize()`.

- **Round-trip correctness:** All three envelope types (AST, Result, Conformance) round-trip correctly through export/import in both JSON and YAML formats. Verified by tests and manual CLI execution.

- **Package checksum integrity:** SHA256 checksums are correctly computed and validated. Tests verify both valid packages and tampered-file detection.

- **Zip and directory format parity:** Both package formats (directory and zip) work correctly for create, inspect, validate, and extract operations. Round-trip tests cover both formats.

- **CLI error handling:** All CLI commands return proper exit codes (0 for success, 1 for errors) and output structured JSON error messages to stderr on failure.

- **Test coverage is solid:** The test suite covers happy paths, error cases (missing files, bad extensions, nonexistent paths, checksum mismatches), round-trips, and format variations. 196 tests all pass.

- **LinkML projection quality:** The projection correctly handles JSON Schema features (refs, enums, unions, arrays, objects) with appropriate lossy-mapping warnings. The consumer example demonstrates standalone usage.

- **Example scripts are functional:** All four example scripts follow correct patterns, use `yaml.safe_load`, handle CLI arguments, and demonstrate the interop API without requiring the full Limnalis runtime.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 5     |
| MEDIUM   | 7     |
| LOW      | 5     |
| PASS     | 12    |

**Verdict: CONDITIONAL PASS** -- The two CRITICAL issues (path traversal in `extract_package` and non-deterministic LinkML output) must be resolved before merge. The HIGH issues should also be addressed. The codebase is generally well-structured and the test coverage is good, but the security and determinism gaps are real.
