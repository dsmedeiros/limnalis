# Review Verdict: wave1-t1-t3-t6

## Scope Compliance
- Declared scope: `src/limnalis/runtime/` (with test file write authority per scope definition)
- Files modified:
  - `src/limnalis/runtime/models.py` — new models (AdequacyResult, AnchorAdequacyResult, JointAdequacyResult, ExprHandler, EvaluatorBindings)
  - `src/limnalis/runtime/builtins.py` — eval_expr full implementation, evaluate_adequacy_set full implementation, apply_resolution_policy metadata fixes
  - `src/limnalis/runtime/runner.py` — `services.setdefault("__bundle__", bundle)` injection
  - `tests/test_runtime_primitives.py` — 11 new tests, 1 updated test
  - `.armature/session/state.md` — session state tracking update
- Out-of-scope modifications: `.armature/session/state.md` is a session coordination file, not production code. This is acceptable orchestrator bookkeeping.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 | PASS | Phase ordering 1-12 preserved in runner.py. No phases added, removed, or reordered. The only runner change (`services.setdefault`) is pre-phase setup. |
| RUNTIME-002 | PASS | All new primitive implementations follow uniform shape `(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)`. eval_expr: `(claim, evaluator_id, step_ctx, machine_state, services) -> (TruthCore, MachineState, Diagnostics)`. evaluate_adequacy_set: `(anchor_ids, step_ctx, machine_state, services) -> (dict, MachineState, Diagnostics)`. apply_resolution_policy: already established non-uniform shape `(per_evaluator, policy, adjudicator) -> EvalNode` — unchanged and consistent with existing contract. |
| RUNTIME-003 | PASS | NoteExpr bypass preserved in runner.py phases 7/8/9 via `cc.evaluable` check. eval_expr includes NoteExpr safety fallback returning N[note_expr] at line 1159. classify_claim correctly marks NoteExpr as non-evaluable. |
| RUNTIME-004 | PASS | PrimitiveSet dataclass unchanged — still accepts all 13 injectable primitives. eval_expr and evaluate_adequacy_set replaced stubs with implementations (no longer raise NotImplementedError). Remaining stubs (resolve_ref, resolve_baseline, synthesize_support, execute_transport, compose_license) still raise NotImplementedError with descriptive messages. |
| MODEL-001 | PASS | New runtime models (AdequacyResult, AnchorAdequacyResult, JointAdequacyResult, ExprHandler, EvaluatorBindings) correctly use `pydantic.BaseModel`, NOT `LimnalisModel`. Runtime models are not AST nodes per the agents.md directive. |
| MODEL-002 | N/A | MODEL-002 applies to AST models only. Runtime models correctly do not use `extra='forbid'` — they are not AST nodes. |

## Additional Checks

- **Circular imports**: No circular imports introduced. `builtins.py` imports from `..models.ast` and `.models` (runtime). `runner.py` imports from `.builtins` and `.models`. Import chain is clean.
- **NoteExpr bypass**: Preserved in runner phases 7, 8, and 9. Safety fallback exists in eval_expr for defense-in-depth.
- **Test results**: All 126 tests pass (65 runtime tests, 61 other tests). Zero regressions.
- **Determinism**: Provenance lists are consistently sorted (`sorted(prov)`) across all new code paths. Truth aggregation uses a deterministic lattice join table.
- **Error handling**: eval_expr never propagates binding handler exceptions — catches and returns N[missing_binding] with diagnostic. evaluate_adequacy_set handles missing bundles, missing anchors, missing policies, and circular dependencies gracefully.
- **Runner phase 7/8 error fallback**: Runner provides default TruthCore(truth="N") and SupportResult(support="absent") on both NotImplementedError and general Exception, preventing phase crashes from blocking subsequent phases.
- **Adjudicated policy empty-filter guard**: When policy members filter results to empty set, returns N[no_evaluators] without calling the adjudicator — tested by `test_adjudicated_empty_filter_returns_n`.

## Verdict: PASS

All invariants satisfied. No out-of-scope production code modifications. Full test suite passes with zero regressions. The changeset is well-structured with appropriate error handling, deterministic outputs, and defense-in-depth for NoteExpr bypass.
