# Review Verdict: wave2-t2-t4

## Scope Compliance
- Declared scope: `src/limnalis/runtime/` (with test file write authority)
- Files modified:
  - `src/limnalis/runtime/builtins.py` (T2: synthesize_support, T4: compose_license)
  - `src/limnalis/runtime/models.py` (T4: AnchorLicenseEntry, JointLicenseEntry, LicenseOverall, license_store)
  - `src/limnalis/runtime/runner.py` (T4: phase 5 compose_license integration, 13-phase renumbering)
  - `tests/test_runtime_runner.py` (T4: phase count 12->13, compose_license in expected primitives)
- Out-of-scope modifications: none

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 | CONDITIONAL | Runner correctly executes 13 phases in strict ascending order (1-13), tests enforce this. However, invariant text in `registry.yaml` (line 171) and `invariants.md` still says "12 phases (1-12)". The `agents.md` overview also says "12-phase step runner". These governance text files must be updated to say "13 phases (1-13)" to match the code and tests. |
| RUNTIME-002 | PASS | `compose_license(claim_id, step_ctx, machine_state, services) -> (LicenseResult, MachineState, Diagnostics)` follows uniform shape. `synthesize_support(claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state, services) -> (SupportResult, MachineState, Diagnostics)` follows uniform shape. Both match their Protocol definitions in `primitives.py`. |
| RUNTIME-003 | PASS | NoteExpr claims continue to bypass eval_expr (phase 8) and synthesize_support (phase 9). The synthesize_support implementation also includes a defensive NoteExprNode guard returning `support="inapplicable"`. Runner logic at phase 7 classification and phase 8/9 `cc.evaluable` checks are preserved. |
| RUNTIME-004 | PASS | PrimitiveSet has 13 fields, all injectable. `compose_license` defaults to the builtin. `synthesize_support` defaults to the builtin. Previously stubbed primitives (`synthesize_support`, `compose_license`) now have real implementations but still follow the contract: the runner catches NotImplementedError for custom stubs and records diagnostics. |
| SCHEMA-* | N/A | No schema files modified. |
| MODEL-* | N/A | Runtime models use standard `BaseModel`, not `LimnalisModel` (as specified in agents.md). New models (`AnchorLicenseEntry`, `JointLicenseEntry`, `LicenseOverall`, `LicenseResult` expansion) are correctly scoped to runtime. |
| No circular imports | PASS | `builtins.py` imports from `..models.ast` and `.models` only. `runner.py` imports from `.builtins` and `.models` only. No new cross-cutting imports introduced. |

## Test Results
- All 124 tests pass (0 failures, 0 errors).
- Phase trace tests validate 13 phases in strict ascending order.
- NoteExpr bypass tests confirm non-evaluable claims skip eval_expr and synthesize_support.
- Custom injection tests confirm PrimitiveSet accepts overrides for all primitives.
- Fold block fallback test confirms error handling in phase 12.

## Implementation Quality Notes

### T2 - synthesize_support
- Default support policy correctly implements the decision ladder: NoteExpr -> absent -> conflicted -> partial -> supported.
- Evidence policy override dispatch correctly looks up evaluator's `evidencePolicy` URI in `services["support_policy_handlers"]` and delegates when a handler exists, falling through to default when not found.
- NoteExpr guard is a sensible defensive measure even though the runner already bypasses.
- Conflict detection examines both `relations` (kind="conflicts") and `cross_conflict_score`.
- Partial detection checks both `completeness < 1.0` and `internalConflict > 0`.

### T4 - compose_license
- Exact-set matching for joint adequacy uses subset check (`needed_joint_set <= ja_anchor_set`), which is correct for "covers the needed anchors".
- Missing joint adequacy produces `N` with `missing_joint_adequacy` reason and a diagnostic.
- Circular dependency detection scans `per_assessment` list for `reason == "circular_dependency"`.
- Worst-truth-wins severity ordering `F > B > N > T` is implemented via `_SEVERITY_ORDER` dict and `max()`.
- License results are stored in `machine_state.license_store` and also returned in `StepResult.per_claim_licenses`.
- License results stay separate from world truth (resolution_store) -- design constraint satisfied.

## Verdict: CONDITIONAL

## Required Changes (for PASS):
1. **Update RUNTIME-001 text in `registry.yaml`** (line 171): Change "12 phases" to "13 phases" and "(1-12)" to "(1-13)".
2. **Update RUNTIME-001 text in `invariants.md`** (line 123): Change "12 phases in strict ascending order (1-12)" to "13 phases in strict ascending order (1-13)".
3. **Update `src/limnalis/runtime/agents.md`**: Change "12-phase step runner" to "13-phase step runner" in the Overview section, and "12 phases" to "13 phases" in Behavioral Directives and Change Expectations sections.

These are governance text updates only -- no code changes needed. The code and tests are correct. The conditional verdict reflects that invariant text must match the enforced behavior (otherwise the invariant itself is misleading). Once the text is updated, this changeset is PASS.

**Escalation note on RUNTIME-001**: The invariant says phase ordering must not be altered "without a spec change". The implementer argues compose_license is required by the spec. The reviewer does not evaluate spec compliance (that is outside review scope), but confirms the implementation is internally consistent: 13 phases, strict ascending order, all tests pass. The orchestrator should confirm the spec justification and approve the invariant text update.
