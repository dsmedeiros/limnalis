# Red Team Review: m5-rt-runtime

## Summary

Two changes to `src/limnalis/runtime/builtins.py`: (D1) replacing `list(dict.fromkeys(reasons))` with `sorted(set(reasons))` in `apply_resolution_policy`, and (D2) updating the module docstring from "6 fully internal + 7 stubs" to "12 of 13 fully; only resolve_ref remains a stub." Both changes are semantically safe. D1 is a no-op in all reachable code paths because the result is only consumed via a length check and single-element extraction. D2 is factually accurate. No regressions found; all 110 runtime primitive tests and all 41 conformance tests pass.

## Critical Findings

None.

## Subtle Issues

### D1: `sorted(set(reasons))` vs `list(dict.fromkeys(reasons))`

**File:** `/home/user/limnal/src/limnalis/runtime/builtins.py`, line 435

The old code (`list(dict.fromkeys(reasons))`) preserved insertion order while deduplicating. The new code (`sorted(set(reasons))`) deduplicates and sorts lexicographically.

**Analysis of actual impact:** The variable `unique_reasons` is consumed in exactly two ways:
1. `len(unique_reasons) == 1` -- pure cardinality check, unaffected by ordering.
2. `unique_reasons[0]` -- only reached when there is exactly one unique reason, so ordering is irrelevant.

When `len(unique_reasons) != 1`, the `reason` variable retains its default value of `None`. No downstream code ever sees the multi-element list.

**Conclusion:** The semantic change (insertion-order to lexicographic-order) is unreachable in practice. The change is safe.

**Residual concern (LOW):** If future code were to use `unique_reasons` beyond the `len == 1` gate (e.g., joining multiple reasons into a compound string), the sort order difference would become visible. This is speculative and does not warrant blocking.

## Test Gaps

1. **No test exercises paraconsistent_union with multiple distinct non-None reasons.** The existing tests cover: T+F conflict (reason="evaluator_conflict"), T+N (no reason asserted), N+N (no reason asserted), and single-evaluator (reason passthrough). There is no test where two evaluators produce different non-None reasons (e.g., reason="alpha" and reason="beta"), which would exercise the `len(unique_reasons) != 1` branch and confirm that `reason` is `None` in that case. This is a pre-existing gap, not introduced by this change.

2. **No test exercises paraconsistent_union with duplicate reasons across evaluators.** A test where ev1.reason="same" and ev2.reason="same" would explicitly confirm the dedup-to-single-reason propagation path. Again pre-existing.

## Semantic Drift Risks

None identified. The docstring update (D2) accurately reflects the current state: exactly one stub (`resolve_ref`) remains out of 13 primitives, verified by grep for `NotImplementedError` and manual count of public function definitions against the 13 Protocol classes in `primitives.py`.

## Verdict: PASS

No blocking issues. Both changes are correct and safe. The test gaps identified are pre-existing and do not constitute regressions.

## Advisories:
- Consider adding a test for the paraconsistent_union path where evaluators carry distinct non-None reasons, to lock down the `reason=None` behavior for multi-reason disagreement. This would have caught any future regression if the `unique_reasons` consumption pattern changes.
