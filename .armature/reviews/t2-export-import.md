# Review: T2 -- Export/Import Functions + Envelope Serialization

**Reviewer:** compliance-reviewer
**Date:** 2026-03-30
**Verdict:** PASS (with advisory notes)

---

## Checklist

### 1. SCHEMA-001: Does export_ast validate against vendored schema?

**PASS.** `export_ast()` delegates to `normalize_surface_file(source_path, validate_schema=validate)`. When `validate=True` (the default), `normalize_surface_file` calls `validate_payload(ast_data, "ast")` against the vendored JSON Schema before returning. The `validate` parameter allows callers to opt out explicitly, which is acceptable -- the default enforces the invariant.

`export_ast_from_dict()` does **not** run schema validation on the incoming dict. This is acceptable given its purpose (wrapping a pre-validated dict), but callers bear responsibility for prior validation. The docstring should note this; flagged as advisory, not blocking.

### 2. NORM-001: Is serialization deterministic?

**PASS.** Both `_serialize` paths use `sort_keys=True`:
- JSON: `json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)`
- YAML: `yaml.dump(data, default_flow_style=False, sort_keys=True, allow_unicode=True)`

`envelope_to_dict` uses `model_dump(mode="json")` which produces deterministic output from Pydantic models (field declaration order, consistent type coercion). Combined with sorted serialization, identical inputs will always produce identical outputs.

### 3. Scope compliance: Only files within src/limnalis/interop/ touched?

**PASS.** Working tree shows:
- `M  src/limnalis/interop/__init__.py` (modified)
- `?? src/limnalis/interop/export.py` (new)
- `?? src/limnalis/interop/import_.py` (new)

All three are within declared scope `src/limnalis/interop/`.

### 4. No cross-cutting changes?

**PASS.** No changes to models/, runtime/, governance files, grammar, or schemas.

### 5. Code quality

**PASS.**

- Clean imports, no unused imports, no circular dependencies.
- `validate_payload` is imported in `export.py` but not directly called -- validation is handled via `normalize_surface_file`. The import is unused. **Advisory: remove `from limnalis.schema import validate_payload` from export.py.**
- Proper error handling: `export_ast` raises `ValueError` if normalization produces no AST.
- `import_.py` uses `yaml.safe_load` (not `yaml.load`) -- correct for security.
- Type annotations are complete and consistent.
- `__all__` in `__init__.py` is sorted and comprehensive.

### 6. Import safety: Edge case handling

**PASS.**

- **Missing format on string input:** `_load_input` raises clear `ValueError` with guidance.
- **Unknown file extension:** `_detect_format` raises `ValueError` for unrecognized suffixes.
- **Non-dict YAML/JSON:** `_parse_text` validates result is `dict` and raises `ValueError` otherwise.
- **Dict pass-through:** Dicts are returned directly without unnecessary re-serialization.
- **Path handling:** Uses `read_text(encoding="utf-8")` for consistent encoding.

---

## Advisory Notes (non-blocking)

1. **Unused import in export.py:** `from limnalis.schema import validate_payload` is imported but never called directly. Consider removing to keep imports clean.

2. **export_ast_from_dict lacks schema validation:** Unlike `export_ast`, this function accepts an arbitrary dict without validating it against the vendored schema. Consider adding an optional `validate: bool = False` parameter (defaulting to False to match the "pre-validated" use case) that calls `validate_payload` when True.

3. **No trailing newline in serialized output:** `json.dumps` does not append a trailing newline. If files are written from this output, they may lack POSIX-compliant line endings. Minor concern.

---

## Invariant Compliance Summary

| Invariant | Status | Notes |
|-----------|--------|-------|
| SCHEMA-001 | Compliant | Via normalize_surface_file default path |
| NORM-001 | Compliant | sort_keys=True on both JSON and YAML |
| MODEL-001 | N/A | No new models introduced |
| MODEL-002 | N/A | No new models introduced |

---

**Final Verdict: PASS**

The implementation is clean, well-scoped, handles edge cases properly, and respects all claimed invariants. Advisory notes are improvement suggestions, not blocking issues.
