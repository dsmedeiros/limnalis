# Red Team Review: m4-rt2-tests-docs

## Summary

The three test files (determinism, property, parser robustness) and the documentation suite are broadly sound but contain several issues ranging from misleading documentation claims to test quality weaknesses that reduce confidence in what the tests actually prove. No critical bugs were found in application code, but the test suite has gaps that could mask regressions, and one documentation claim is factually incorrect.

## Critical Findings

None.

## Subtle Issues

### S1. `test_property.py` line 58: Dead assertion with misleading docstring (MEDIUM)
- **File:** `tests/test_property.py`, lines 55-61
- **What:** `test_join_annihilator_B` has two assertions. Line 58 asserts `_TRUTH_JOIN[(a, "B")] == "B" or a == "N"`, and line 61 asserts `_TRUTH_JOIN[(a, "B")] == "B"` unconditionally. Line 58 is strictly weaker than line 61 and can never fail if line 61 passes. The docstring says "except N JOIN B = B" implying there is an exception, but there is none -- B is the universal annihilator. The dead assertion on line 58 is confusing dead code.
- **How to trigger:** Read the code; the `or a == "N"` clause on line 58 is never reached.
- **Severity:** MEDIUM (misleading, not incorrect)

### S2. `random.shuffle` inside Hypothesis tests breaks reproducibility (MEDIUM)
- **File:** `tests/test_property.py`, lines 71-77 and 93-101
- **What:** `test_aggregate_truth_commutative` and `test_fold_block_truth_order_independent` use `random.shuffle` (stdlib) inside a Hypothesis `@given` test. Hypothesis controls its own PRNG for example generation, but `random.shuffle` uses a separate global RNG that Hypothesis does not manage. This means test failures may not be reproducible via Hypothesis's example database -- the same Hypothesis-generated input could produce different shuffle orders on replay.
- **How to trigger:** A flaky commutativity failure would not reproduce when Hypothesis replays the failing example.
- **Severity:** MEDIUM (undermines Hypothesis's replay guarantee; should use `hypothesis.strategies` for permutations or seed the RNG from `data.draw()`)

### S3. Parser robustness tests catch `Exception` which is too broad (MEDIUM)
- **File:** `tests/test_parser_robustness.py`, lines 25-26, 30-31, 35-36, 40-41, and throughout
- **What:** Every `pytest.raises` call catches `(UnexpectedInput, Exception)`. Since `Exception` is the base class of nearly all exceptions, this means the tests would pass even if the parser raised `MemoryError` (actually `BaseException`, so this one would escape), `RecursionError`, `TypeError`, `AttributeError`, or any other crash. The test docstrings say "should raise a clean error, not crash" but the assertions cannot distinguish between a clean parser error and an internal crash.
- **How to trigger:** Introduce a bug in the parser that causes `TypeError` on malformed input -- all robustness tests would still pass.
- **Severity:** MEDIUM (false green risk; should catch only `UnexpectedInput` or `LarkError` to prove clean rejection)

### S4. Parser robustness tests 5-7 silently accept any outcome (MEDIUM)
- **File:** `tests/test_parser_robustness.py`, lines 43-84
- **What:** `test_extremely_deeply_nested_input`, `test_very_long_input`, and `test_unicode_input` use try/except that catches `(UnexpectedInput, Exception)` and passes on both success and failure. These tests can literally never fail regardless of what the parser does. They prove only that the parser does not raise `BaseException` subclasses (like `KeyboardInterrupt`), which is trivially true.
- **How to trigger:** Delete the parser entirely and replace `parse_text` with `raise RuntimeError("broken")` -- these three tests would still pass.
- **Severity:** MEDIUM (tautological tests; they prove nothing about parser behavior)

### S5. Determinism tests only run twice (LOW)
- **File:** `tests/test_determinism.py`, all test classes
- **What:** Each determinism test runs the pipeline exactly twice and compares outputs. For truly deterministic code, this is sufficient. However, for code with intermittent nondeterminism (e.g., hash-order-dependent behavior that manifests only with certain data), two runs may not trigger the variance. The test class `TestNormalizerDeterminism` also silently skips cases that raise exceptions (line 90-92), meaning normalization errors are never checked for deterministic error behavior.
- **How to trigger:** Introduce a nondeterminism that triggers 10% of the time -- the two-run test has only a ~19% chance of catching it on any given run.
- **Severity:** LOW (standard practice, but worth noting the limitation)

## Test Gaps

### G1. No property tests for parser or normalizer
The test suite has Hypothesis property tests only for four-valued logic (`_TRUTH_JOIN`, `_aggregate_truth`, `_fold_block_truth`). There are zero property tests for the parser or normalizer, despite these being the most complex components. Fuzz testing the parser with generated strings, or property-testing the normalizer's round-trip stability, would significantly increase confidence.

### G2. Missing `_fold_block_truth` property coverage for B-only and N-only cases
`test_property.py` tests: all-T yields T, presence of F yields F, B+N yields F. But it does not test:
- All-B (no F, no N) yields B
- All-N (no F, no B) yields N
- Mixed T+B (no F, no N) yields B
- Mixed T+N (no F, no B) yields N

These are branches 3 and 4 in `_fold_block_truth` (lines 506-509 of builtins.py) that have no dedicated property test coverage.

### G3. No negative property test for the join lattice
The tests verify algebraic properties (commutativity, associativity, identity, annihilator, idempotency) but do not verify that the lattice is NOT a standard Boolean algebra. Specifically, there is no test confirming that `T JOIN F = B` (the key paraconsistent behavior). While this is implicitly tested through the table, an explicit test documenting this distinguishing property would prevent accidental "simplification" to standard AND/OR.

### G4. `test_join_identity_element_N` tests only right-identity
Line 52: `_TRUTH_JOIN[(a, "N")] == a` tests right-identity only. Left-identity (`_TRUTH_JOIN[("N", a)] == a`) is covered implicitly by the commutativity test, but this depends on commutativity being correct. An explicit left-identity test would be more robust against a table typo that breaks both commutativity and left-identity simultaneously.

## Semantic Drift Risks

### D1. RC Status doc claims "Property tests (Hypothesis) for parser and normalizer robustness" (HIGH)
- **File:** `docs/release_candidate_status.md`, line 88
- **What:** The document states the test suite includes "Property tests (Hypothesis) for parser and normalizer robustness." This is factually incorrect. Hypothesis property tests exist only for four-valued logic in `test_property.py`. The parser robustness tests in `test_parser_robustness.py` are conventional unit tests using handcrafted inputs, not Hypothesis property tests. There are zero Hypothesis-based parser or normalizer tests.
- **Impact:** This misrepresents the test coverage to anyone evaluating the RC for release. A reader would believe the parser has been fuzz-tested when it has not.

### D2. Architecture doc phase numbering matches code
The architecture doc lists 13 phases in the correct order matching the runner. No issues found.

### D3. Version numbers are consistent
All version references are consistent:
- `pyproject.toml`: `version = "0.2.2rc1"`
- `src/limnalis/version.py`: `PACKAGE_VERSION = "0.2.2rc1"`, `SPEC_VERSION = "v0.2.2"`, `SCHEMA_VERSION = "v0.2.2"`, `CORPUS_VERSION = "v0.2.2"`
- `README.md`: `0.2.2rc1` / `v0.2.2`
- `docs/release_candidate_status.md`: `0.2.2rc1` / `v0.2.2`

### D4. ADRs accurately reflect implementation
ADR-001 (Pydantic models), ADR-002 (13-phase runner), ADR-003 (conformance-first), and ADR-004 (API freeze) all accurately describe the current implementation. The public API exports verified to match what ADR-004 and the architecture doc claim.

### D5. Test count claim is accurate
RC status doc claims 308 tests. Actual count: 308 passed. Confirmed.

### D6. Corpus coverage claim is accurate
RC status doc claims 16/16 PASS. Confirmed by running the full suite.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **D1 (HIGH):** `docs/release_candidate_status.md` line 88 falsely claims Hypothesis property tests cover parser and normalizer robustness. This line should be corrected to accurately state that Hypothesis tests cover four-valued logic properties, while parser robustness is covered by conventional unit tests with handcrafted malformed inputs.
- **S3/S4 (MEDIUM):** Parser robustness tests have false-green risk. Tests that catch `Exception` cannot distinguish clean parser errors from internal crashes. Tests 5-7 are tautological and can never fail. These should be tightened to catch only `lark.exceptions.LarkError` (or its subclasses) and the tautological tests should assert specific outcomes.
- **S2 (MEDIUM):** Hypothesis property tests using `random.shuffle` break Hypothesis's reproducibility guarantee. Should use `st.permutations()` or draw from Hypothesis's PRNG.
- **S1 (MEDIUM):** Dead assertion in `test_join_annihilator_B` with misleading docstring. Clean up.
- **G1-G4 (MEDIUM):** Property test coverage gaps for fold_block branches and absence of parser/normalizer property testing.
