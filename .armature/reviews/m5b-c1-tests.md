# Red Team Review: m5b-c1-tests

## Summary

Two new test files add 30 tests covering D3 (extra-diagnostic blindness), D4 (reverse evaluator check), F1 (frame completion), and operator precedence. All 30 tests pass. The tests are substantive and exercise real code paths. However, there are naming/documentation inaccuracies that could mislead future maintainers, and the first six operator precedence tests (R6a, lines 87-161) test parenthesized structure preservation rather than actual precedence resolution -- a meaningful but mislabeled concern. No blocking issues found.

## Critical Findings

None.

## Subtle Issues

### 1. D3 unit tests (lines 44-104) test `_compare_diagnostics` return value, not the D3 fix itself (MEDIUM)

- **File:** `/home/user/limnal/tests/test_conformance_comparison.py`, lines 44-104
- **What:** Tests `test_extra_error_diagnostic_flagged`, `test_extra_fatal_diagnostic_flagged`, and `test_extra_warning_diagnostic_not_flagged` call `_compare_diagnostics` directly and assert on the returned unmatched list. But `_compare_diagnostics` always returned unmatched actuals -- it did not change in the D3 fix. The D3 fix is in `compare_case` (compare.py lines 509-514) where unmatched error/fatal diagnostics are promoted to FieldMismatch entries.
- **Impact:** These three tests would have passed identically *before* the D3 fix. They test a helper function's behavior that predates D3. They are not tautological (they exercise real code), but they do not prove the D3 fix works. Only `test_compare_case_flags_extra_error_diagnostic_end_to_end` (line 106) actually tests the D3 code path.
- **Risk:** A future developer might believe D3 is covered by four tests when only one of them actually tests the D3-specific logic.

### 2. First six operator precedence tests use explicit parenthesization, not implicit precedence (MEDIUM)

- **File:** `/home/user/limnal/tests/test_operator_precedence.py`, lines 87-161
- **What:** Tests like `test_and_binds_tighter_than_or` use the expression `((a AND b) OR c)`. After stripping the outer parens, the inner text is `(a AND b) OR c`. The AND is inside nested parens, so `_split_top_level` skips it when trying AND as the delimiter. The split only matches OR at the top level. This tests that the parser respects parenthesized grouping, not that AND has higher precedence than OR.
- **Contrast:** The "first_match_wins" tests (lines 163-277) DO test actual precedence because they use expressions like `(a AND b IFF c)` where both operators compete at the same paren depth.
- **Impact:** If someone swapped the precedence order in `_LOGICAL_OPERATORS` (e.g., put OR before AND), the first six tests would still pass because the explicit parenthesization forces the structure. Only the first-match-wins tests would fail.
- **Risk:** The first six tests give a false sense of precedence coverage. They are correct tests of parenthesized structure, but their names and docstrings claim to test binding tightness.

### 3. D3 test `test_extra_warning_diagnostic_not_flagged` proves a negative at the wrong layer (LOW)

- **File:** `/home/user/limnal/tests/test_conformance_comparison.py`, lines 86-104
- **What:** This test verifies that extra warning diagnostics are present in the unmatched return list from `_compare_diagnostics`. It asserts `len(mismatches) == 0` and `len(unmatched) == 1`. But the test does not verify that `compare_case` leaves warnings unflagged. The filtering logic is in `compare_case` (checking `severity in {"error", "fatal"}`), not in `_compare_diagnostics`.
- **Impact:** This test would pass even if `compare_case` incorrectly promoted warnings to mismatches, because it never calls `compare_case`.

## Test Gaps

### 1. No end-to-end D3 test for extra fatal diagnostics

There is an end-to-end test for extra error diagnostics (`test_compare_case_flags_extra_error_diagnostic_end_to_end`) but no corresponding end-to-end test for extra fatal diagnostics via `compare_case`. The unit test covers fatal at the `_compare_diagnostics` level only.

### 2. No end-to-end D3 test proving warnings are NOT flagged

There is no test that calls `compare_case` with extra warning-only diagnostics and verifies `comparison.passed` is True. This is the complement of the D3 fix and should be explicitly tested.

### 3. No negative precedence test

No test verifies that swapping the operator order in `_LOGICAL_OPERATORS` would break the first-match-wins tests. While this is an implementation detail, a test that explicitly asserts `(a OR b AND c)` produces `OR(a, pred("b AND c"))` (proving OR is tried after AND, not before) would strengthen coverage. Currently, `test_precedence_first_match_wins_and_over_or` tests `(a AND b OR c)` but not `(a OR b AND c)`.

### 4. D4 tests do not exercise `compare_case` end-to-end

All three D4 tests call `_compare_claim` directly. While this function contains the reverse-check logic, there is no end-to-end test via `compare_case` proving that extra evaluators cause `comparison.passed == False`. The D3 tests include such an end-to-end test; the D4 tests do not.

## Semantic Drift Risks

### Test names vs. tested behavior in D3 tests

The names `test_extra_error_diagnostic_flagged` and `test_extra_fatal_diagnostic_flagged` imply that the diagnostics are "flagged" (i.e., converted to mismatches). But the tests only verify that unmatched actuals are returned. "Flagged" happens in `compare_case`, not in `_compare_diagnostics`. The names should reflect what they actually test: that `_compare_diagnostics` identifies unmatched actuals correctly.

### Operator precedence test class name vs. content

The class `TestLogicalOperatorPrecedence` contains both explicit-parenthesization tests (lines 87-161) and first-match-wins tests (lines 163-277). The explicit-parenthesization tests test structure preservation, not precedence. Mixing these under one class name obscures the distinction.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

1. **D3 unit tests (lines 44-104) do not test the D3 fix.** They test `_compare_diagnostics` return values which are pre-D3 behavior. Only the end-to-end test (line 106) covers D3. Consider adding end-to-end tests for fatal diagnostics and warning non-flagging via `compare_case`.

2. **First six operator precedence tests (lines 87-161) test parenthesized grouping, not operator precedence.** Their names and docstrings are misleading. Consider renaming them to reflect what they actually test (e.g., `test_parenthesized_and_or_grouping`) or adding truly unparenthesized equivalents (the inner operators competing at the same depth).

3. **D4 tests lack an end-to-end `compare_case` test.** Adding one would parallel the D3 end-to-end test and verify that extra evaluators cause case comparison failure, not just individual claim mismatches.

4. **Missing reverse-order precedence tests.** Testing `(a OR b AND c)` (where the lower-precedence operator appears first in the text) would strengthen the first-match-wins suite by proving the parser does not simply split on the first operator it encounters in left-to-right scan order. Currently all first-match-wins tests place the higher-precedence operator first in the text.
