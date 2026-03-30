# Red Team Review: m4-rt2-tests-docs (Re-review Pass 2)

## Summary

All five findings from Pass 1 have been correctly fixed. The parser robustness tests now catch only `UnexpectedInput`, the tautological tests now have real assertions, the Hypothesis reproducibility issue is resolved with `st.randoms`, the dead assertion is removed, and the RC status document no longer falsely claims Hypothesis coverage of parser/normalizer. One minor new documentation inaccuracy was found (test count off by one). The test suite is now in good shape for an RC.

## Verification of Pass 1 Fixes

### S3 (Parser robustness catches Exception -- too broad): FIXED
All `pytest.raises` calls in `test_parser_robustness.py` now catch only `UnexpectedInput`. A `TypeError` or `AttributeError` from a parser bug would now correctly cause test failure. Confirmed at lines 25, 30, 35, 40, 93, 98, 103.

### S4 (Tautological tests 5-7): FIXED
`test_extremely_deeply_nested_input` (lines 55-59) and `test_very_long_input` (lines 71-77) now use try/except that catches only `UnexpectedInput`, with `isinstance(result, Tree)` assertion on the success path. A parser crash (e.g., `RuntimeError`) would now propagate as test failure. `test_unicode_input` (lines 79-89) additionally asserts the tree string is non-empty. These tests now prove meaningful properties about parser behavior.

### S2 (random.shuffle breaks Hypothesis reproducibility): FIXED
Lines 67-68 and 91-92 now use `rng=st.randoms(use_true_random=False)` as a Hypothesis-managed strategy, and shuffle via `rng.shuffle(shuffled)`. This is the canonical Hypothesis pattern: the RNG state is tracked by Hypothesis's example database, so failing cases are fully reproducible on replay.

### S1 (Dead assertion in test_join_annihilator_B): FIXED
The test at line 57-58 now contains a single clean assertion: `assert _TRUTH_JOIN[(a, "B")] == "B"`. The misleading docstring exception clause is gone. The docstring correctly states B is the annihilator for all values.

### D1 (RC status falsely claims Hypothesis parser/normalizer coverage): FIXED
Line 88 of `docs/release_candidate_status.md` now accurately states: "Property tests (Hypothesis) for four-valued logic lattice properties (commutativity, associativity, idempotency, annihilation, block fold order-independence)". No false claim about parser or normalizer Hypothesis coverage.

## Critical Findings

None.

## Subtle Issues

### S1. Test count in RC status doc is off by one (LOW)
- **File:** `docs/release_candidate_status.md`, line 83
- **What:** The document claims "308 tests total." Actual collected test count is 309 (verified via `pytest --co -q`). This is likely stale from before the most recent test additions.
- **How to trigger:** Run `python -m pytest tests/ --co -q` and count items.
- **Severity:** LOW (cosmetic; does not affect release readiness)

## Test Gaps

The advisories from Pass 1 regarding coverage gaps (G1-G4) remain open but were explicitly categorized as non-blocking advisories, not regressions. They are tracked for future improvement:
- No property tests for parser or normalizer
- Missing fold_block property tests for B-only and N-only branches
- No explicit T JOIN F = B distinguishing-property test
- Left-identity for N not explicitly tested (covered implicitly by commutativity)

## Semantic Drift Risks

### D1. Test count will continue to drift
The RC status doc hardcodes "308 tests total" rather than referencing a dynamic count. Each time tests are added or removed, this number becomes stale. This is standard for a point-in-time document but worth noting.

## Verdict: PASS

All five blocking advisories from Pass 1 are resolved. The remaining issues are LOW severity (stale test count) and previously-acknowledged non-blocking coverage gaps. The test suite and documentation are accurate and meaningful for RC purposes.

## Advisories:
- **S1 (LOW):** Test count in `docs/release_candidate_status.md` line 83 says 308; actual count is 309. Update before final release.
- **G1-G4 (carried forward, non-blocking):** Property test coverage gaps from Pass 1 remain as future improvement items.
