# Red Team Review: m5-d3d4f1

## Summary

This changeset implements three coordinated fixes: F1 (frame completion in conformance runner), D3 (extra-diagnostic blindness), and D4 (extra-evaluator reverse check). The logic is correct for the cases exercised by the fixture corpus. All 313 tests pass and 16/16 conformance cases PASS. I found no critical or high-severity issues. There are unused imports in the F1 block, a consistency gap where the D4 reverse-evaluator check was applied to claims but not to blocks, and no dedicated unit tests for any of the three changes.

## Critical Findings

None.

## Subtle Issues

1. **Unused imports in F1 frame completion block (LOW)**
   - File: `/home/user/limnal/src/limnalis/conformance/runner.py`, lines 765-766
   - `FacetValueMap`, `FrameNode`, `FramePatternNode`, and `_merge_frame_facets` are imported but never used. Only `_frame_facets` and `_facets_to_frame` are referenced in the completion logic (lines 769-774).
   - This is cosmetic but indicates the implementation was adapted from a draft that used `_merge_frame_facets` and was then rewritten to use manual facet overlay. The unused imports are dead weight.
   - Severity: LOW

2. **D4 reverse-evaluator check not applied to `_compare_block` (MEDIUM)**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, function `_compare_block` (line 276)
   - The D4 fix adds a reverse check for extra evaluators in `_compare_claim` (lines 121-126), but `_compare_block` has the same one-directional comparison pattern (lines 292-315) and was not updated. If the runtime produces an evaluator for a block that the fixture does not expect, it will be silently ignored.
   - No current fixture exercises this path, so there is no active risk today. However, the same class of blindness that motivated D4 for claims exists identically for blocks.
   - Severity: MEDIUM (consistency gap; same defect class as D4 but in an adjacent function)

3. **Inconsistent FieldMismatch path format in D4 (LOW)**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, line 125
   - Extra evaluators use bracket notation `per_evaluator[{ev_id}]` while existing evaluator mismatches use dot notation `per_evaluator.{ev_id}` (lines 105, 115). If mismatch paths are ever parsed programmatically (e.g., for filtering or reporting), this inconsistency could cause mismatches to be missed by path-matching logic.
   - Severity: LOW

4. **F1 completion silently drops unknown facet keys (by design, but undocumented)**
   - File: `/home/user/limnal/src/limnalis/conformance/runner.py`, lines 771-773
   - If `bundle_frame_completion` contains keys not in `_FRAME_FACETS` (e.g., a typo like `"sytem"` instead of `"system"`), they are silently ignored because `_frame_facets` only returns the canonical facet set. This is safe behavior but could mask fixture authoring errors. No warning or diagnostic is emitted.
   - Severity: LOW

## Test Gaps

1. **No unit tests for D3 (extra-diagnostic detection)**
   - There is no test that specifically verifies: when expected diagnostics are non-empty AND the runtime produces an extra error/fatal diagnostic not in the expected list, a mismatch is reported. The only coverage is through A1 conformance integration, where the fix's effect is that A1 no longer produces a spurious `frame_unresolved_for_evaluation` diagnostic (because F1 prevents it). A targeted unit test for `compare_case` with crafted inputs would exercise D3 independently.

2. **No unit tests for D4 (extra-evaluator detection)**
   - There is no test that constructs a StepResult with an evaluator not present in the fixture expectations and verifies that `_compare_claim` flags it. The current conformance cases do not exercise this path (they match exactly).

3. **No unit tests for F1 (frame completion)**
   - The frame completion logic is only exercised through the A1 integration test. A targeted test that calls `run_case` with a synthetic fixture containing `bundle_frame_completion` data and verifies the resulting bundle frame would isolate F1 from the full evaluation pipeline.

4. **No test for A2 null frame_resolver path**
   - A2 has `frame_resolver: null`, which correctly skips the completion block. However, the A2 test existed before F1 was added. There is no assertion that specifically verifies A2's bundle frame remains a FramePatternNode after `run_case` (confirming no completion occurred). The existing A2 test passes because the expected output matches, but it would also pass if the frame completion were accidentally skipped for a different reason.

## Semantic Drift Risks

1. **`_compare_block` and `_compare_claim` are drifting apart**
   - These two functions serve the same structural role (compare expected vs. actual per-evaluator and aggregate results) but now have different feature sets. `_compare_claim` has the D4 reverse check; `_compare_block` does not. Over time, fixes applied to one may be forgotten for the other. This is a common source of silent regressions in parallel-structured code.

2. **The `FieldMismatch` value for D4 extra evaluators stores an EvalNode object**
   - Line 125: `actual_per_ev[ev_id]` is an EvalNode, stored directly as the `actual` field of FieldMismatch. The `__str__` method uses `repr()`, so this will print the Pydantic model's repr. This is acceptable for human debugging but could be surprising if FieldMismatch values are ever compared programmatically (e.g., in test assertions).

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **A1 (LOW):** Remove unused imports in the F1 block: `FacetValueMap`, `FrameNode`, `FramePatternNode`, and `_merge_frame_facets` at `/home/user/limnal/src/limnalis/conformance/runner.py` lines 765-766. Only `_facets_to_frame` and `_frame_facets` are needed.
- **A2 (MEDIUM):** Apply the D4 reverse-evaluator check to `_compare_block` in `/home/user/limnal/src/limnalis/conformance/compare.py` for consistency. The same blindness that D4 fixes for claims exists for blocks.
- **A3 (MEDIUM):** Add targeted unit tests for the three changes (D3 extra-diagnostic detection, D4 extra-evaluator detection, F1 frame completion) to reduce reliance on integration-only coverage.
