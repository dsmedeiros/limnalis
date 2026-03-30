# Red Team Review: 3c-redteam-runtime

## Summary

The `resolve_baseline` implementation is functionally correct for the happy path and aligns with fixture corpus expectations (case A4). However, it mutates `machine_state` in-place rather than defensively copying it, creating a consistency hazard with other builtins. The total absence of dedicated unit tests for `resolve_baseline` is the most significant gap -- zero coverage for an implementation that moved from stub to production logic.

## Critical Findings

None.

## Subtle Issues

1. **In-place mutation of machine_state (builtins.py lines 620, 646)**
   `resolve_baseline` mutates `machine_state.baseline_store[baseline_id]` directly, then returns the same `machine_state` object as the "new" state. Compare with `build_evidence_view` (line 279) which does `machine_state.model_copy(deep=True)` before mutation. This is not a bug today because the runner (line 307) reassigns `machine = ...` from the return value, and no other code holds a reference to the pre-mutation state. However, it creates a latent hazard: if any future caller captures `machine` before calling `resolve_baseline`, that reference is silently mutated. The inconsistency with `build_evidence_view` makes this a maintenance trap -- a developer reading the codebase would reasonably assume either "all primitives copy" or "all primitives mutate" but the actual behavior is mixed. Note: `execute_transport` and `evaluate_adequacy_set` also mutate in-place, so this is a codebase-wide inconsistency, not unique to this changeset.

2. **Missing baseline_id produces silent unresolved state with no diagnostic (builtins.py lines 618-623)**
   When `baseline_node is None` (baseline_id not found in bundle), the code silently writes an "unresolved" BaselineState and returns an empty diagnostics list. No warning or info diagnostic is emitted. This means a typo in a baseline ID would produce an "unresolved" status that is indistinguishable from the `moving + !tracked` invalid-combo case (which does emit a diagnostic). If a conformance fixture expected "ready" for a baseline but the ID was wrong, the mismatch would surface in the compare layer, but during development or manual runs the silent unresolved is easy to miss.

3. **Phase 3 in runner only resolves baselines declared in `bundle.baselines` (runner.py line 306)**
   The runner iterates `bundle.baselines` to call `resolve_baseline`. Baselines that are referenced elsewhere (e.g., in BaselineRefTerm nodes within claim expressions) but not declared in the bundle's baselines list will never be resolved. The `resolve_baseline` function has a guard for this (the `baseline_node is None` path), but it is unreachable via the runner since the runner only passes IDs from `bundle.baselines`. This is not a bug per se -- the runner correctly resolves only declared baselines -- but the dead code path in `resolve_baseline` (lines 618-623) is misleading about what scenarios are actually exercised.

## Test Gaps

1. **No dedicated unit tests for `resolve_baseline` exist in `test_runtime_primitives.py`.** This is the primary gap. The function moved from a `NotImplementedError` stub to a full implementation with three branches (`on_reference` -> deferred, `moving+!tracked` -> unresolved + diagnostic, else -> ready), and none of these branches have direct unit test coverage. The only indirect coverage is through conformance fixture A4, which is an integration test.

2. **Missing test: `services["__bundle__"]` is None or absent.** If `services` is empty or `__bundle__` is missing, `bundle` is `None`, the `for bl in bundle.baselines` loop is skipped, and the function falls through to the `baseline_node is None` branch. This works but is accidental -- it should be tested explicitly.

3. **Missing test: `kind="point"` with `evaluationMode="fixed"` -> ready.** The "ready" branch needs a test for each valid combination: `(point, fixed)`, `(set, fixed)`, `(manifold, fixed)`, `(moving, tracked)`, `(point, on_reference)` -> deferred, etc.

4. **Missing test: `kind="moving"` with `evaluationMode="fixed"` -> unresolved + diagnostic.** The invalid combo branch needs a test proving the diagnostic dict has the expected shape (`severity`, `code`, `subject`, `phase`, `message`).

5. **Missing test: partial failure in phase 3 loop.** If a bundle has two baselines and `resolve_baseline` succeeds for the first but throws for the second, the runner catches the exception at the phase level (runner.py line 319), but the first baseline's state is already committed to `machine_state` via in-place mutation. No test verifies this partial-state scenario.

6. **Missing negative test: diagnostic shape validation.** The `baseline_mode_invalid` diagnostic uses `"phase": "baseline"` (string), while runner-level diagnostics use integer phases. Downstream consumers (e.g., `sort_diagnostics`) handle both types, but no test asserts the specific diagnostic dict shape produced by `resolve_baseline`.

## Semantic Drift Risks

1. **`resolve_baseline` returns `None` as its first tuple element in all branches.** The return type is `tuple[Any, MachineState, Diagnostics]`. Every call path returns `(None, machine_state, diags)`. The first element is vestigial -- the runner (line 307) captures it as `_` but the function signature implies it should return a meaningful value. If a future implementer tries to return baseline data in the first position, nothing in the type system or tests would catch consumers that ignore it.

2. **The `"phase": "baseline"` string in diagnostics.** While consistent with other domain-level diagnostics (e.g., `"phase": "license"`, `"phase": "transport"`), it creates two diagnostic namespaces: runner phases (integers 1-13) and domain phases (strings). The `sort_diagnostics` function in `models.py` handles this via the `_phase_key` helper, but the dual namespace is undocumented and fragile.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **[HIGH]** Add dedicated unit tests for `resolve_baseline` covering all three branches (deferred, unresolved+diagnostic, ready), the missing-baseline fallback, and the diagnostic dict shape. The zero-test-coverage state is unacceptable for production logic that replaced a stub.
- **[MEDIUM]** Emit an info/warning diagnostic when `baseline_node is None` so silent unresolved states are observable.
- **[LOW]** Consider standardizing the mutation-vs-copy contract for primitives. The current mixed approach is a maintenance hazard but does not cause bugs today.
