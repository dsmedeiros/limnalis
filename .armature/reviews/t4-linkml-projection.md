# Review: T4 — LinkML Projection Pipeline

**Reviewer:** Compliance Reviewer
**Date:** 2026-03-30
**Verdict:** PASS

---

## Scope Compliance

**Status:** PASS

All changes are within the declared scope:
- `src/limnalis/interop/linkml.py` — new file in interop subpackage
- `src/limnalis/interop/__init__.py` — modified to add `project_linkml_schema` export
- `linkml/limnalis_ast.linkml.yaml` — new generated artifact at project root
- `linkml/limnalis_results.linkml.yaml` — new generated artifact at project root

No files outside `src/limnalis/interop/` and `linkml/` were created or modified by this task.

## No Cross-Cutting Changes

**Status:** PASS

Verified via `git diff main --name-only`:
- `src/limnalis/models/` — untouched
- `src/limnalis/runtime/` — untouched
- `.armature/invariants/` — untouched
- `.armature/personas/` — untouched
- `.armature/ARMATURE.md` — untouched

## LinkML Is Projection, Not Canonical

**Status:** PASS

The non-authoritative nature is documented in multiple reinforcing locations:

1. **Module docstring** (`linkml.py` line 1-8): States artifacts are "PROJECTIONS -- derived, approximate views -- NOT the canonical source of truth."
2. **Function docstring** (`project_linkml_schema`): Reiterates "This is a PROJECTION -- not the canonical source of truth."
3. **Generated YAML header** (both `.linkml.yaml` files): Large banner comment reading "THIS FILE IS A DERIVED PROJECTION -- NOT THE CANONICAL SOURCE OF TRUTH."
4. **Generated YAML description field**: Embeds "This is a DERIVED artifact -- the canonical source of truth is the Pydantic model layer in ..."
5. **Lossy mapping summary** in YAML header enumerates four categories of known information loss.

This is thorough and leaves no ambiguity about canonical authority.

## Invariant Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| MODEL-001 | PASS | `ProjectionResult` inherits from `LimnalisModel` (via `types.py`) |
| MODEL-002 | PASS | `LimnalisModel` enforces `extra='forbid'` in `ConfigDict` |
| SCHEMA-001 | N/A | LinkML artifacts are projections, not canonical AST; schema validation applies to canonical path only |

No invariants are violated.

## Code Quality

**Status:** PASS

- **Imports:** Clean; lazy import of `importlib` inside the function to avoid import-time dependency on model modules.
- **Error handling:** The converter gracefully handles unknown JSON Schema constructs (union wrappers, non-object defs) by emitting warnings and lossy_fields rather than raising.
- **Type annotations:** Proper use of `Literal` for `source_model` parameter; return type is `ProjectionResult`.
- **YAML rendering:** Uses `yaml.dump` with `sort_keys=False` to preserve field order; header comment is clearly formatted.
- **No mutable default arguments.**
- **`__init__.py` exports:** `project_linkml_schema` added to both the import block and `__all__`.

## Lossy Mappings Documented

**Status:** PASS

Lossy mappings are documented at three levels:

1. **YAML header comment** lists four categories of lossy mappings.
2. **Per-field annotations** in generated YAML: fields with lossy projections carry `description` values like "Discriminated union (lossy projection). Canonical variants: ..." or "Open dict type (lossy projection)".
3. **`ProjectionResult.warnings` and `ProjectionResult.lossy_fields`** programmatically enumerate every lossy mapping (27 total for the AST projection), allowing downstream tooling to inspect them.

Categories of documented lossiness:
- Discriminated unions projected as first variant class or string
- Open `dict[str, Any]` projected as string
- Nested arrays / tuples projected as multivalued string
- Pydantic validators and cross-field constraints not represented
- Mixed union types projected as string

## Functional Verification

Executed `project_linkml_schema('ast')` successfully. The function returned a `ProjectionResult` with 27 warnings and 27 lossy fields, confirming it runs end-to-end without error.

## Minor Observations (Non-Blocking)

1. The `_SOURCE_MODELS` dict maps both `"evaluation_result"` and `"conformance_report"` to the same class (`ExpectedResult` from `limnalis.models.conformance`). This is intentional (both produce the same results schema) but could benefit from a brief comment explaining why.
2. The generated YAML files contain a timestamp that will differ on regeneration. This is acceptable for derived artifacts but means `git diff` will always show changes on regeneration even if the schema hasn't changed. Consider making timestamp optional in a future iteration.

---

## Final Verdict: PASS

All five review criteria are satisfied. The implementation is clean, well-documented, correctly scoped, and properly marks all output as non-authoritative derived projections. No invariants are violated and no cross-cutting changes were made.
