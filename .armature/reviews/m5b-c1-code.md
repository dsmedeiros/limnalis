# Red Team Review: m5b-c1-code

## Summary

This changeset contains three low-risk cleanup and correctness fixes across production code: removal of an unused `field_validator` import from `models/base.py`, removal of four unused imports from `conformance/runner.py`, a path format normalization (bracket to dot notation) in `conformance/compare.py`, and a message consistency fix ("none expected" to "not expected") in `conformance/compare.py`. All changes are verified correct. All 343 tests pass.

## Critical Findings

None.

## Subtle Issues

None. Each change was verified against the full file context:

1. **`field_validator` removal (base.py):** Confirmed `field_validator` is not used anywhere in `base.py`. It is imported and used in `models/ast.py` and `models/conformance.py` via their own imports -- no downstream breakage.

2. **Unused import removal (runner.py line 765):** The four removed names (`FacetValueMap`, `FrameNode`, `FramePatternNode`, `_merge_frame_facets`) do not appear anywhere else in `runner.py` after the import statement. The two retained imports (`_facets_to_frame`, `_frame_facets`) are used at lines 768 and 773. Correct.

3. **Path format fix (compare.py line 125):** Changed `per_evaluator[{ev_id}]` to `per_evaluator.{ev_id}`. All seven other `per_evaluator` path constructions in compare.py (lines 104, 115, 304, 311, 397) already use dot notation. The bracket notation was the sole inconsistency. Tests at lines 188, 250-252 of `test_conformance_comparison.py` already assert dot-notation paths, confirming the fix aligns with the existing test expectations.

4. **Message fix (compare.py line 513):** Changed `"none expected"` to `"not expected"`. The other occurrence at line 125 already used `"not expected"`. Tests at lines 133, 188 of `test_conformance_comparison.py` filter/assert on the string `"not expected"`, confirming consistency. The previous `"none expected"` was semantically misleading -- the code path handles extra unmatched diagnostics when some diagnostics *were* expected; the issue is that *these specific ones* were not expected.

## Test Gaps

None identified for this changeset. The existing test suite covers the affected code paths, including reverse evaluator detection, extra diagnostic flagging, and path format assertions.

## Semantic Drift Risks

None. The changes reduce inconsistency rather than introduce it.

## Verdict: PASS

No blocking issues. No advisories. All removed imports are confirmed unused, the path format change achieves consistency with all other patterns in the file, and the message fix is both semantically accurate and aligned with existing test assertions.
