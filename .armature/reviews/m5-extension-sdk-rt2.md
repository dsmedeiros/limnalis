# Red Team Review: m5-extension-sdk-rt2

## Summary

Cycle 2 re-review of the fixture plugin pack fixes from cycle 1. All 7 findings from RT1 have been addressed. All 446 tests pass. The _JOIN table is correct across all 16 combinations. Two minor issues found in the inlined adjudicator logic -- dead code and a support-default inconsistency -- neither produces wrong results in any reachable code path. Verdict: PASS.

## Fix Verification

### S1/D1 (MEDIUM): FixtureEvalHandler buggy + exported
**Status: FIXED.**
- `fixtures.py` line 34: class renamed to `_FixtureEvalHandler` with underscore prefix.
- `fixtures.py` lines 440-446: `__all__` does not include `_FixtureEvalHandler`.
- Grep across src/ and tests/: no file imports `FixtureEvalHandler` by the old public name.
- Deprecation docstring present at lines 35-42.

### S2 (MEDIUM): FixtureAdjudicator imports private helpers
**Status: FIXED.**
- No import of `_aggregate_truth` or `_aggregate_support` in `fixtures.py`.
- `_JOIN` table (lines 189-196) contains all 16 (4x4) entries for {T, F, B, N}:
  - TT=T, TF=B, TB=B, TN=T -- correct
  - FT=B, FF=F, FB=B, FN=F -- correct
  - BT=B, BF=B, BB=B, BN=B -- correct
  - NT=T, NF=F, NB=B, NN=N -- correct
  - Table is symmetric as expected.
- Support aggregation priority order (line 213): conflicted > partial > supported > inapplicable > absent -- matches spec.

### T1 (MEDIUM): TestFixtureEvalHandler was testing wrong class
**Status: FIXED.**
- `test_fixture_plugin_pack.py` line 182: class is `TestFixtureEvalHandlerForEvaluator`, matching the handler class `FixtureEvalHandlerForEvaluator`.

### T2 (MEDIUM): No test for adjudicator mixed-truth non-conflict path
**Status: FIXED.**
- `test_fixture_plugin_pack.py` lines 301-319: `test_mixed_t_and_n_aggregates` and `test_mixed_f_and_n_aggregates` exercise the mixed-truth branch (truth_set has 2 elements, not T+F conflict).
- Both tests verify truth, reason (is None), and provenance.
- Both tests pass.

### T5 (MEDIUM): FixtureSupportHandler default_synth untested
**Status: FIXED.**
- `test_fixture_plugin_pack.py` lines 324-366: `TestFixtureSupportHandlerDefaultSynth` with:
  - `test_default_synth_fallback_non_tuple`: verifies non-tuple return used directly (identity check with `is`).
  - `test_default_synth_fallback_tuple`: verifies tuple[0] extraction.
- Both tests use `is` identity assertions, confirming the actual object flows through, not a copy.

### D2 (MEDIUM): build_services_from_registry ignores 5 of 8 kinds
**Status: FIXED.**
- `__init__.py` lines 229-233: adjudicator wiring for single-registration case.
- `__init__.py` lines 187-207: docstring documents all 8 kinds -- 4 auto-wired (EVALUATOR_BINDING, EVIDENCE_POLICY, ADEQUACY_METHOD, ADJUDICATOR) and 4 registry-only (CRITERION_BINDING, TRANSPORT_HANDLER, BASELINE_HANDLER, BINDING_RESOLVER).

### S3 (LOW): CLI exit code inconsistency
**Status: FIXED.**
- `test_cli_plugins.py` lines 84-100: two tests document the intentional behavior:
  - `test_plugins_list_nonexistent_kind_exits_0`: empty list returns 0.
  - `test_plugins_list_nonexistent_kind_json_returns_empty_array`: JSON variant returns `[]`.

## Critical Findings

None.

## Subtle Issues

### SI-1: Dead code in mixed-truth support aggregation (LOW)

File: `src/limnalis/plugins/fixtures.py`, line 210.

```python
if agg_truth == "B" and "T" in truth_set and "F" in truth_set:
    agg_support = "conflicted"
```

The mixed-truth branch is only reached when the early return at line 161 did NOT fire -- i.e., when `"T" in truth_set and "F" in truth_set` is False. Therefore the condition on line 210 is always False and the `agg_support = "conflicted"` assignment is dead code. The logic is correct (it falls through to the priority loop), but the dead code is misleading to future readers who might think this branch is reachable.

### SI-2: Support default inconsistency between unanimous and mixed-truth branches (LOW)

In the unanimous branch (line 177-178), when no evaluator has a non-None support, `support` is explicitly set to `"absent"`. In the mixed-truth branch (lines 207-216), when `supports` is empty, `agg_support` remains `None`. Both are valid (`SupportValue | None`), but the inconsistency could confuse consumers that expect uniform behavior. In practice this is unlikely to be triggered since the fixture test data always provides support values, but it is a latent inconsistency.

## Test Gaps

None blocking. The mixed-truth branch tests cover T+N and F+N. Additional combinations (B+N, T+B, F+B) are not tested but the _JOIN table is a simple dict lookup with no conditional logic, so the risk is minimal.

## Semantic Drift Risks

### SD-1: "evaluator_conflict" reason for non-T/F B results (LOW)

Line 202: when `agg_truth == "B"` in the mixed-truth branch, reason is set to `"evaluator_conflict"`. This fires for cases like T+B or F+B, where one evaluator already reported B. Calling this "evaluator_conflict" is defensible (there is a conflict in the lattice) but potentially misleading since the conflict pre-exists in one evaluator's own result rather than arising from disagreement. No wrong behavior today; worth noting for future semantics review.

## Verdict: PASS

All cycle 1 findings verified as resolved. No new critical, high, or medium issues introduced. The two LOW subtle issues and one LOW semantic drift risk are advisory only and do not block.
