# Review: Milestone 5 -- Extension SDK, Plugin Registry, Plugin Packs, Consumer Examples, Docs, CLI

**Reviewer:** Reviewer agent
**Date:** 2026-03-29
**Verdict:** PASS

---

## Checklist

### 1. Invariant Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| SCHEMA-001 | OK | No schema changes. AST validation pipeline untouched. |
| SCHEMA-002 | OK | No schema file changes. |
| SCHEMA-003 | OK | No schema version changes needed. |
| MODEL-001 | OK | No AST model changes in this changeset. |
| MODEL-002 | OK | No model config changes. |
| MODEL-003 | OK | Models and schemas remain consistent. |
| NORM-001 | OK | Normalizer not modified. |
| NORM-002 | OK | Normalizer not modified. |
| NORM-003 | OK | Normalizer not modified. |
| FIXTURE-001 | OK | Fixture corpus untouched. 16/16 conformance PASS confirmed. |
| RUNTIME-001 | OK | Phase ordering not modified. |
| RUNTIME-002 | OK | Primitive shape not modified. |
| RUNTIME-003 | OK | NoteExpr bypass not modified. |
| RUNTIME-004 | OK | PrimitiveSet not modified. |

**No invariant violations detected.**

### 2. Scope Compliance

All new `api/` modules are pure re-export wrappers:
- `api/plugins.py` -- re-exports from `runtime.primitives`, `runtime.models`, `runtime.runner`
- `api/context.py` -- re-exports from `runtime.models`
- `api/results.py` -- re-exports from `runtime.models`, `runtime.runner`
- `api/models.py` -- re-exports from `models.ast`
- `api/services.py` -- re-exports from `plugins`

No new logic in any `api/` re-export module. **PASS.**

### 3. Public API Freeze

`api/__init__.py` change is purely additive:
- Existing exports preserved: `conformance`, `evaluator`, `normalizer`, `parser`
- New exports added: `context`, `models`, `plugins`, `results`, `services`

No removals, no renames. **PASS.**

### 4. No Core Semantic Changes

Working tree diff confirms zero changes to:
- `src/limnalis/normalizer.py`
- `src/limnalis/parser.py`
- `src/limnalis/schema.py`
- `src/limnalis/models/`
- `src/limnalis/runtime/`

Evaluation semantics unchanged. **PASS.**

### 5. Plugin System Correctness

`src/limnalis/plugins/__init__.py`:
- `PluginRegistry` uses `dict[tuple[str, str], PluginMetadata]` -- deterministic keying.
- `list_plugins()` returns `sorted()` by `(kind, plugin_id)` -- deterministic enumeration.
- `kinds()` returns sorted set -- deterministic.
- `PluginConflictError` on duplicate registration -- clean error.
- `PluginNotFoundError` on missing lookup -- clean error with kind/id in message.
- `PluginMetadata` is a frozen dataclass -- immutable.
- `build_services_from_registry()` bridges registry to runner services dict cleanly.

**PASS.**

### 6. Example Quality -- Public-Only Imports

Consumer examples verified:
- `examples/consumer_parse_normalize.py` -- imports from `limnalis.api.normalizer` only.
- `examples/consumer_fixture_conformance.py` -- imports from `limnalis.api.conformance` only.
- `examples/consumer_grid_b1.py` -- imports from `limnalis.api.conformance`, `limnalis.api.services`, `limnalis.plugins.grid_example`.
- `examples/consumer_jwt_b2.py` -- imports from `limnalis.api.conformance`, `limnalis.api.services`, `limnalis.plugins.jwt_example`.

Plugin packs (`grid_example.py`, `jwt_example.py`) use deferred imports from `limnalis.api.results` and `limnalis.plugins` -- public API only.

`fixtures.py` uses internal relative imports (`..conformance.fixtures`, `..runtime.models`) which is acceptable since it ships as part of the `limnalis` package, not as a consumer example.

**PASS.**

### 7. Test Coverage

439 tests passing, 0 failures. New test files:
- `test_plugin_registry.py` -- 18 registry tests (CRUD, conflict, enumeration)
- `test_fixture_plugin_pack.py` -- fixture pack registration and handler tests
- `test_grid_plugin_pack.py` -- grid pack tests
- `test_jwt_plugin_pack.py` -- JWT pack tests
- `test_cli_plugins.py` -- CLI `plugins list` and `plugins show` command tests
- `test_integration_plugins.py` -- integration tests

Coverage appears adequate for the new surface area. **PASS.**

### 8. CLI Changes

CLI additions are strictly additive:
- New `plugins` top-level command with `list` and `show` subcommands.
- Existing commands untouched.
- `_build_demo_registry()` gracefully handles missing plugin packs via `try/except ImportError`.
- Both subcommands support `--json` output flag.

**PASS.**

---

## Advisories (non-blocking)

1. **ADVISORY-01 (LOW):** `fixtures.py` imports `_aggregate_truth` and `_aggregate_support` from `..runtime.builtins` (private names with leading underscore). While acceptable for an internal module, this couples the fixture pack to private builtins API. Consider promoting these to public helpers if they are needed by plugin authors.

2. **ADVISORY-02 (LOW):** The `api/services.py` module name overlaps semantically with the `api/plugins.py` module (both expose plugin registry types). The `services.py` module re-exports from `plugins.__init__`, so `api.plugins` (Protocol types) and `api.services` (Registry types) form a clear split, but the naming could be documented more explicitly.

3. **ADVISORY-03 (LOW):** Documentation files (7 new .md files in `docs/`) were not reviewed for technical accuracy in this pass since they are outside the invariant enforcement surface. A separate documentation review is recommended.

---

## Verdict

**PASS** -- No invariant violations. All changes are additive. Core semantics untouched. Plugin registry is deterministic with clean errors. Consumer examples use only public API imports. 439 tests passing. CLI extensions are additive.

Approved for commit.
