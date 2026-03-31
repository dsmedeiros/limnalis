# Review: T3 -- Exchange Package Format

**Reviewer:** compliance-reviewer
**Date:** 2026-03-30
**Task:** T3 -- Exchange Package Format
**Declared scope:** src/limnalis/interop/
**Files under review:**
- `src/limnalis/interop/package.py` (new)
- `src/limnalis/interop/__init__.py` (modified)

---

## 1. Scope Compliance

**PASS.** Only two files affected, both within `src/limnalis/interop/`:
- `package.py` is a new untracked file.
- `__init__.py` was modified to add re-exports for the four new public functions and their `__all__` entries.

No files outside the declared scope were created or modified.

## 2. No Cross-Cutting Changes

**PASS.** `models/`, `runtime/`, governance files, grammar, normalizer, schemas, and tests are untouched. The `__init__.py` diff is limited to import additions and `__all__` list entries -- no behavioral changes to existing exports.

## 3. Code Quality

**PASS.**

- Imports are clean: only stdlib modules (`hashlib`, `json`, `shutil`, `tempfile`, `zipfile`, `datetime`, `pathlib`) plus the interop `types` module.
- Proper `try/finally` for temp directory cleanup in `create_package`.
- `validate_package` properly closes zip handles in `finally` blocks.
- Helper functions `_sha256_file`, `_is_zip_package` are appropriately private.
- Type annotations are complete and consistent (`str | Path` inputs, explicit return types).
- `__all__` in `__init__.py` is sorted alphabetically.

## 4. Security: Path Traversal in extract_package

**ISSUE (minor, non-blocking).** `extract_package` calls `zf.extractall(output_dir)` without filtering member names. On Python < 3.12, `extractall` does not guard against zip slip (path traversal via `../` in zip entry names). A malicious zip could write files outside `output_dir`.

**Mitigation context:** The project requires Python >= 3.11 (`pyproject.toml`). Python 3.12 added built-in zip slip protection to `extractall`. Python 3.11 does not have this protection. The current runtime is 3.13, but the declared minimum is 3.11.

**Recommendation:** Add an explicit member-name check before extraction, or raise the minimum Python to 3.12. Example guard:

```python
for member in zf.namelist():
    target = (output_dir / member).resolve()
    if not str(target).startswith(str(output_dir.resolve())):
        raise ValueError(f"Zip entry would escape output directory: {member}")
```

**Verdict on this item:** Non-blocking for acceptance because exchange packages are expected to be self-generated or from trusted sources in the reference implementation. However, this should be addressed before any use with untrusted input.

## 5. Consistency with ExchangeManifest

**PASS.**

- `create_package` constructs `ExchangeManifest` with all required fields from `types.py`.
- `inspect_package` uses `ExchangeManifest.model_validate()` for deserialization.
- `validate_package` likewise deserializes through `model_validate()` and checks field presence.
- `ExchangePackageMetadata` is correctly used as the return type for both `create_package` and `inspect_package`.
- Version constants `SPEC_VERSION` and `SCHEMA_VERSION` are imported from `types.py`, not duplicated.

## 6. Determinism

**PASS.**

- Manifest JSON is written with `sort_keys=True` (line 125).
- `artifact_types` list is `sorted()` before inclusion in the manifest (line 118).
- Zip entries are written in `sorted(build_root.rglob("*"))` order (line 134).
- Checksums are computed from file content, which is deterministic.
- The only non-deterministic field is `created_at` (current timestamp), which is appropriate for metadata.

## 7. Invariant Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| MODEL-001 | PASS | ExchangeManifest and ExchangePackageMetadata inherit LimnalisModel (verified in types.py) |
| MODEL-002 | PASS | LimnalisModel base uses extra='forbid'; ExchangeManifest validated via model_validate() |
| SCHEMA-001 | N/A | package.py does not produce or modify AST nodes |

---

## Verdict: **PASS**

All checklist items satisfied. One minor security recommendation (zip slip guard for Python 3.11 compatibility) is noted but non-blocking. The implementation is clean, well-structured, and correctly uses the existing type system.

**Conditions for future work:**
- If `extract_package` will ever handle packages from untrusted sources, add explicit path traversal protection or raise minimum Python to >= 3.12.
