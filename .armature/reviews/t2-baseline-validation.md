# Review Verdict: T2 — Fix A4 Baseline Validation

## Scope Compliance
- Declared scope: `src/limnalis/models/ast.py`, `src/limnalis/runtime/builtins.py`
- Files modified: `src/limnalis/models/ast.py`, `src/limnalis/runtime/builtins.py`, `.armature/session/state.md`
- Out-of-scope modifications: `.armature/session/state.md` (session bookkeeping only, non-code, acceptable)

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| MODEL-001 | PASS | `BaselineNode` still inherits from `LimnalisModel`. Only the `_moving_requires_tracked` model validator was removed; class hierarchy is intact. |
| MODEL-002 | PASS | `extra='forbid'` is set on `LimnalisModel` base class in `base.py` (line 12). `BaselineNode` inherits this. No config override introduced. |
| MODEL-003 | PASS | The removed validator was a Pydantic-only constraint not present in the JSON Schema. Removing it brings the model closer to schema parity, not further away. |
| SCHEMA-001 | PASS | `test_schema_validation.py` passes (4/4). The A4 normalized AST now validates against the vendored schema. |
| FIXTURE-001 | PASS | The fixture corpus expects A4 to normalize successfully. The old validator blocked this. The change aligns implementation with the conformance authority. This is the correct direction per FIXTURE-001 ("implementation must conform to fixtures, not the other way around"). |
| RUNTIME-002 | PASS | `resolve_baseline` signature is `(baseline_id, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)`, matching the uniform primitive shape. |
| RUNTIME-004 | N/A | The stub was replaced with a real implementation. `test_runtime_primitives.py` passes (105/105). |

## Test Results

- `test_schema_validation.py`: 4/4 PASS
- `test_runtime_primitives.py`: 105/105 PASS
- `test_runtime_runner.py`: 24/24 PASS
- `test_ast_models.py`: 7/8 (1 FAIL)
- `test_normalizer.py`: 15/16 (1 FAIL)
- `test_cli_smoke.py`: 2/3 (1 FAIL)
- `test_conformance.py`: 2/3 (1 FAIL)

**4 test failures**, all caused by tests that asserted the old model-level rejection behavior:

1. `test_moving_baseline_requires_tracked_mode` — asserts `BaselineNode(kind="moving", evaluationMode="fixed")` raises `ValidationError`. No longer true; constraint moved to runtime.
2. `test_normalizer_rejects_invalid_moving_baseline_fixture` — asserts A4 normalization raises `NormalizationError`. A4 now normalizes successfully per FIXTURE-001.
3. `test_validate_source_cli_reports_normalization_errors` — uses A4 as the invalid-baseline example, expects CLI exit code 1 with phase "normalize". A4 now succeeds; test needs a different invalid input or updated assertions.
4. `test_conformance_run_default_runs_full_corpus` — expected `code == 1` because A4 used to fail. Full corpus now passes (code 0).

## Observations

1. **Docstring inconsistency (minor):** The `resolve_baseline` docstring lists state logic in an order that does not match the code's evaluation precedence. The code correctly checks `on_reference` first (deferred regardless of kind), but the docstring lists `moving+!tracked -> unresolved` first. Not a bug, but potentially confusing for future readers.

2. **Constraint relocation is sound:** Moving the `moving+!tracked` validation from the model layer to the runtime layer is architecturally correct. The model layer should be permissive enough for normalization to succeed (per PARSER-001 philosophy: "parser is permissive; normalizer enforces constraints"). The runtime appropriately flags the invalid combination via a diagnostic with code `baseline_mode_invalid`.

## Verdict: CONDITIONAL

The code changes to `ast.py` and `builtins.py` are correct and properly align with FIXTURE-001 and the system's architectural principles. However, the changeset leaves 4 tests in a failing state. These tests must be updated before the commit can be accepted.

## Required Changes

- Update the 4 failing tests to reflect the new behavior. This should be handled in a dedicated test-fix task (as noted in the changeset description). The test updates must:
  1. Remove or replace `test_moving_baseline_requires_tracked_mode` (the model no longer enforces this; a new test could verify the runtime diagnostic instead)
  2. Replace `test_normalizer_rejects_invalid_moving_baseline_fixture` with a test that verifies A4 normalizes successfully
  3. Update `test_validate_source_cli_reports_normalization_errors` to use a genuinely invalid input (not A4)
  4. Update `test_conformance_run_default_runs_full_corpus` to expect exit code 0 (full pass)
- Fix the `resolve_baseline` docstring to match the actual code precedence order (minor)
