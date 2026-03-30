# Review Verdict: T7 — EvaluationResult shaping

## Scope Compliance
- Declared scope: `src/limnalis/runtime/`
- Files modified (in-scope):
  - `src/limnalis/runtime/models.py`
  - `src/limnalis/runtime/runner.py`
  - `src/limnalis/runtime/builtins.py`
  - `src/limnalis/runtime/agents.md`
- Supporting files (governance/tests, permitted):
  - `.armature/invariants/invariants.md`
  - `.armature/invariants/registry.yaml`
  - `.armature/journal.md`
  - `.armature/session/state.md`
  - `.armature/reviews/wave1-t1-t3-t6.md`
  - `.armature/reviews/wave2-t2-t4.md`
  - `tests/test_runtime_primitives.py`
  - `tests/test_runtime_runner.py`
- Out-of-scope modifications: none

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 | PASS | 13 phases confirmed in strict ascending order (1-13). Phase 5 (compose_license) correctly inserted; all subsequent phases renumbered. |
| RUNTIME-002 | PASS | New primitives (compose_license, execute_transport) follow uniform shape `op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)`. Existing primitives unchanged. |
| RUNTIME-003 | PASS | NoteExpr bypass logic preserved at phases 8, 9, 10. Non-evaluable claims skip eval_expr and support synthesis. |
| RUNTIME-004 | PASS | PrimitiveSet includes all 13 primitives with injectable callables. compose_license comment removed (was deferred, now scheduled). |
| MODEL-001 | N/A | Runtime models correctly use `BaseModel`, not `LimnalisModel` (these are not AST nodes, per `runtime/agents.md`). |
| MODEL-002 | N/A | `extra='forbid'` applies to AST models only; runtime models correctly omit it. |

## Additional Checks

| Check | Status | Notes |
|---|---|---|
| Deterministic ordering | PASS | `sort_diagnostics` sorts by `(phase, code, subject)` with stable fallback keys. Applied at StepResult, SessionResult, and BundleResult levels. ClaimResult/BlockResult lists follow source order (bundle claim/block order). |
| New models (ClaimResult, BlockResult) | PASS | Use `BaseModel`, consistent with runtime model convention. Fields reference existing types (ClaimClassification, EvalNode, LicenseResult). |
| EvaluationResult alias | PASS | Simple type alias `EvaluationResult = BundleResult`. No behavioral change. |
| SessionResult additions | PASS | `baseline_states` and `adequacy_store` extracted from final step's machine state. Sensible session-level aggregation. |
| LicenseResult restructure | PASS | Expanded from `{claim_id, licensed, diagnostics}` to structured `{claim_id, overall, individual, joint, diagnostics}` with typed sub-models. |
| TransportResult model | PASS | New model with `TransportStatus` import, typed fields, stored in `MachineState.transport_store`. |
| MachineState additions | PASS | `license_store` and `transport_store` added with appropriate types and defaults. |
| EvaluatorBindings Protocol | PASS | New Protocol class with `get_handler` method. Uses `runtime_checkable` decorator. Does not alter existing contracts. |
| Test suite | PASS | All 124 tests pass (72 + 52 across all test files). No regressions. |

## Verdict: PASS

All invariants are satisfied. The changeset is within declared scope. All existing tests pass. New models follow runtime conventions (BaseModel, not LimnalisModel). Deterministic ordering is applied via `sort_diagnostics` at all result assembly points. The phase count increased from 12 to 13 with compose_license inserted at phase 5, correctly shifting subsequent phases.
