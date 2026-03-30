# Red Team Review: m5-rt-conformance

## Summary

Three changes to the conformance layer (D3 extra-diagnostic blindness fix, D4 reverse evaluator check, F1 frame completion) are functionally correct and all 313 tests pass (41 conformance, 272 other). However, the D4 fix was applied to `_compare_claim` but NOT to the structurally identical `_compare_block` function, leaving an asymmetric gap. There are also unused imports in the F1 block and an inconsistent path format in D4's FieldMismatch. None of these are blocking.

## Critical Findings

None.

## Subtle Issues

1. **`_compare_block` lacks reverse evaluator check (MEDIUM)**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, lines 292-315
   - D4 added a reverse check to `_compare_claim` (lines 121-126) that flags extra evaluators present in actual results but absent from expectations. The structurally identical `_compare_block` function at lines 292-315 iterates only over expected evaluator keys and never checks for extras. If the runtime produces an unexpected evaluator result for a block, the comparison silently ignores it.
   - Current risk is low because block evaluators are derived from claim evaluators in the runtime, so any extra evaluator in a block would likely also be caught at the claim level. But this creates an asymmetry where claim-level and block-level comparisons have different strictness guarantees. A future change that introduces block-specific evaluators could silently pass comparison with unexpected entries.

2. **D3 still skips comparison entirely when `expected.diagnostics` key is absent (MEDIUM)**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, line 505
   - The outer guard `if expected_diags is not None:` means that if a fixture case omits the `diagnostics` key entirely from `expected`, no diagnostic comparison runs at all -- including the new extra-diagnostic check. This is arguably correct (no declared expectation means no comparison), but it means a fixture case without a `diagnostics` key silently ignores runtime error/fatal diagnostics. All current fixture cases do specify `diagnostics`, so this is not triggered today.

3. **Frame completion only fills facets that are `None`, not facets absent from the dict (MEDIUM-LOW)**
   - File: `/home/user/limnal/src/limnalis/conformance/runner.py`, line 772
   - The condition `if k in existing_facets and existing_facets[k] is None` requires the key to already exist in `existing_facets`. This is currently safe because `_frame_facets` always returns all 7 facet keys. However, if `_FRAME_FACETS` is ever extended without updating `_frame_facets`, completion data for the new facet would be silently dropped.

## Test Gaps

1. **No dedicated test for the D4 reverse evaluator check triggering**
   - The reverse check was added to fix a blindness issue, but there is no test that constructs a scenario where the runtime produces an evaluator not listed in expectations and verifies the mismatch is reported. All 16 fixture cases happen to produce exactly the evaluators expected. The fix is therefore validated only by absence of regression, not by a positive test proving it detects extras.

2. **No test for frame completion when bundle already has all facets populated**
   - The "existing non-None values take precedence" logic is exercised only for the A1 case where some facets are None and some are set. There is no test where the bundle frame is already a complete FrameNode (all facets set) and completion data is provided -- verifying that no values are overwritten and the result is identical.

3. **No test that A2 (null frame_resolver) leaves the frame as a FramePatternNode**
   - A2 has `frame_resolver: null`, which correctly skips frame completion. However, no assertion verifies that the bundle's frame type after `run_case` remains FramePatternNode. The test passes because expected results match, but this is an implicit rather than explicit guarantee.

## Semantic Drift Risks

1. **Unused imports in F1 block**
   - File: `/home/user/limnal/src/limnalis/conformance/runner.py`, lines 765-766
   - Four of the six imports are unused: `FacetValueMap`, `FrameNode`, `FramePatternNode` (from `models.ast`), and `_merge_frame_facets` (from `runtime.builtins`). Only `_frame_facets` and `_facets_to_frame` are actually called. These dead imports add confusion about what the code depends on and will trigger linter warnings.

2. **Inconsistent path format in D4 FieldMismatch**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, line 125
   - The new reverse-check mismatch uses bracket notation `per_evaluator[{ev_id}]` while all other paths in the file use dot notation `per_evaluator.{ev_id}`. This inconsistency makes it harder to programmatically parse or grep mismatch paths.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **A1 (MEDIUM):** `_compare_block` should receive the same reverse evaluator check that `_compare_claim` received in D4, for symmetry and to prevent future silent mismatches at the block level.
- **A2 (LOW):** Remove unused imports from the F1 block in runner.py (lines 765-766): `FacetValueMap`, `FrameNode`, `FramePatternNode`, `_merge_frame_facets`.
- **A3 (LOW):** Normalize the FieldMismatch path format at compare.py line 125 from `per_evaluator[{ev_id}]` to `per_evaluator.{ev_id}` for consistency with the rest of the file.
- **A4 (LOW):** Consider adding a unit test that directly exercises the reverse evaluator check by constructing a StepResult with an extra evaluator and verifying the mismatch is reported.
