# Review: T5 -- CLI Export/Package/Project Commands + Versioning

**Reviewer:** compliance-reviewer
**Date:** 2026-03-30
**Task:** T5 -- CLI export/package/project subcommands and --version flag
**Declared scope:** src/limnalis/ (core-impl)

## Files Reviewed

| File | Status | Notes |
|------|--------|-------|
| `src/limnalis/cli.py` | modified | 8 new subcommands + --version flag |
| `src/limnalis/interop/compat.py` | new | check_envelope_compatibility function |
| `src/limnalis/interop/__init__.py` | modified | added compat export |

## Checklist Results

### 1. Scope Compliance -- PASS

Only files within `src/limnalis/` were touched. No changes to `models/`, `runtime/`, governance files, schemas, or grammar. The `.armature/` changes in the diff are reviews and session state from prior tasks, not governance modifications made by this task.

### 2. CLI Backward Compatibility -- PASS

All six original subcommands (`parse`, `normalize`, `validate-source`, `validate-ast`, `validate-fixtures`, `print-schema`) are preserved with identical argument signatures. The one structural change is that `required=True` was removed from `add_subparsers()` to allow the `--version` flag to work without a subcommand. This is handled correctly: when `args.command is None` and `--version` was not given, `parser.error("a command is required")` is called, preserving the prior behavior. Smoke tests pass (6/6).

### 3. Code Quality -- PASS

- **Lazy imports**: All new command handlers use deferred imports (e.g., `from .interop import export_ast` inside handler functions). The `--version` handler lazily imports from `.interop.types`. This avoids adding import-time cost for unrelated commands.
- **Error handling**: Every command handler wraps its logic in try/except, emits structured JSON error output to stderr, and returns exit code 1 on failure.
- **JSON output**: All output is structured JSON with `indent=2`, consistent with existing commands.
- **Helper function**: `_load_data_file` correctly handles both JSON and YAML by suffix, uses `yaml.safe_load` (not `yaml.load`).

### 4. Versioning / check_envelope_compatibility -- PASS

`check_envelope_compatibility` correctly:
- Accepts all three envelope types via union type annotation.
- Checks `spec_version` against `SPEC_VERSION` and `schema_version` against `SCHEMA_VERSION`.
- Returns an empty list for compatible envelopes, descriptive strings for mismatches.
- Uses strict equality (not semver range matching), which is appropriate for a 0.x specification where any version difference indicates incompatibility.
- Is properly exported from `__init__.py` and listed in `__all__`.

### 5. No Cross-Cutting Changes -- PASS

- `models/` -- untouched
- `runtime/` -- untouched
- `schemas/` -- untouched
- `grammar/` -- untouched
- `.armature/` governance files -- untouched (only reviews/session state from other tasks)

## Invariant Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| SCHEMA-001 | N/A | No schema changes |
| MODEL-001 | N/A | No model changes |
| MODEL-002 | N/A | No model changes |
| NORM-001 | N/A | No normalizer changes |
| FIXTURE-001 | N/A | No fixture changes |

CLI backward compatibility directive from `src/limnalis/agents.md`: "CLI interface must remain backward-compatible" -- satisfied.

## Minor Observations (Non-Blocking)

1. The `--version` flag uses `action="store_true"` rather than argparse's built-in `action="version"`. This is a deliberate choice since the version output is structured JSON containing three version fields rather than a simple string, so this approach is correct.

2. The `compat.py` module uses absolute imports (`from limnalis.interop.envelopes import ...`) rather than relative imports. This is consistent with the style used in `__init__.py` and other interop modules, so it is acceptable, though relative imports would be slightly more idiomatic for intra-package references.

## Verdict: PASS

All checks pass. The implementation is within declared scope, preserves backward compatibility, follows code quality conventions, and introduces no invariant violations. Approved for commit.
