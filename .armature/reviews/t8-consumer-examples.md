# Review: T8 -- Downstream Consumer Examples

**Reviewer:** compliance-reviewer
**Date:** 2026-03-30
**Verdict:** PASS

## Scope Verification

**Declared scope:** `examples/` (within core-impl extended scope)
**Actual scope:** `examples/consumers/` -- four new files, no modifications elsewhere.

Files reviewed:
- `examples/consumers/read_ast_envelope.py`
- `examples/consumers/read_result_envelope.py`
- `examples/consumers/inspect_package.py`
- `examples/consumers/linkml_consumer.py`

## Checklist Results

### 1. Public API only -- PASS

All three limnalis-dependent examples import exclusively from `limnalis.interop`:
- `read_ast_envelope.py` imports `SCHEMA_VERSION`, `SPEC_VERSION`, `check_envelope_compatibility`, `import_ast_envelope` -- all present in `limnalis.interop.__all__`.
- `read_result_envelope.py` imports `check_envelope_compatibility`, `import_result_envelope` -- both in `__all__`.
- `inspect_package.py` imports `inspect_package` -- in `__all__`.

No imports from internal modules (`limnalis.interop.envelopes`, `limnalis.interop.import_`, etc.). No imports from `limnalis.models`, `limnalis.runtime`, or other internals.

### 2. linkml_consumer.py uses only PyYAML -- PASS

`linkml_consumer.py` imports only `sys`, `pathlib.Path`, and `yaml` (PyYAML). Zero limnalis imports. This correctly demonstrates that LinkML projections are consumable without the Limnalis runtime, which is the design intent per the interop layer.

### 3. Standalone with `__main__` guard and docs -- PASS

All four files have:
- A module-level docstring with `Usage:` instructions showing the command-line invocation.
- A `main(path: str)` entry point.
- An `if __name__ == "__main__"` guard that validates `sys.argv` length, prints the docstring on misuse, and exits cleanly.

### 4. No cross-cutting changes -- PASS

`git status` confirms the T8 changeset consists solely of untracked files under `examples/consumers/`. The `src/` diff visible on this branch is from prior committed tasks (T1-T6). T8 introduces no modifications to source code, tests, schemas, or configuration.

## Invariant Compliance

No invariants are directly at risk from read-only example scripts. The examples do not modify AST models, schema validation, normalization, or runtime behavior. They consume the public API as documented.

## Notes

- Code quality is clean: consistent style, type annotations via `from __future__ import annotations`, proper argument validation.
- The examples cover four distinct consumer personas: AST reader, result reader, package inspector, and external-tool (LinkML) consumer.
- No `__init__.py` in `examples/consumers/`, which is correct -- these are standalone scripts, not a package.
