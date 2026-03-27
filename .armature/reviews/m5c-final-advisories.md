# Red Team Review: m5c-final-advisories

## Summary

The three advisory fixes are well-executed. A1 (reverse evaluator check in `_compare_block`) correctly mirrors the existing pattern from `_compare_claim`. A2 (determinism threshold) adds meaningful skip-tracking and a proportional floor assertion. A3 (parser robustness) replaces unreachable assertions with explicit `pytest.raises` blocks and adds companion success-path tests with valid syntax. All 349 tests pass, including 41 conformance tests. One residual issue carries forward from the original advisory scope: `_compare_transport` has the same one-directional per_evaluator blindness that was just fixed in `_compare_claim` and `_compare_block`.

## Critical Findings

None.

## Subtle Issues

### S1: `_compare_transport` retains one-directional evaluator blindness (MEDIUM)

**File:** `/home/user/limnal/src/limnalis/conformance/compare.py`, lines 397-408

The A1 fix added reverse evaluator checks to both `_compare_claim` (line 121-126) and `_compare_block` (line 317-322). However, `_compare_transport` at lines 397-408 has an identical `per_evaluator` comparison loop that only iterates `per_ev_exp.items()` and never checks for extra evaluators present in actual but absent from expected. This is the same one-directional blindness pattern. If a transport produces an unexpected evaluator result, the comparison will silently pass.

This was not in the declared advisory scope (A1 targeted `_compare_block` specifically), but it is the same class of defect in the same file. Noting for tracking.

### S2: `_compare_eval_snapshot` only compares expected keys (LOW)

**File:** `/home/user/limnal/src/limnalis/conformance/compare.py`, lines 62-85

The leaf-level comparison function `_compare_eval_snapshot` iterates `expected.items()` (line 82) and never checks for extra keys in `actual`. This is arguably by design for snapshot comparisons (allow superset), but it means extra fields in actual eval snapshots are universally invisible to the comparison framework. This is a design-level concern, not a bug in this changeset.

## Test Gaps

### TG1: No test for reverse check in `_compare_block` specifically

The new reverse evaluator check in `_compare_block` is exercised indirectly through the conformance suite (41 tests pass), but there is no dedicated unit test that constructs a `StepResult` with an extra block-level evaluator and asserts a `FieldMismatch` is produced. The analogous reverse check in `_compare_claim` does have dedicated test coverage in `tests/test_conformance_comparison.py`. Consider adding a parallel test for `_compare_block`.

### TG2: Companion parser tests use generic syntax, not domain syntax

**File:** `/home/user/limnal/tests/test_parser_robustness.py`, lines 58-73 and 90-103

`test_deeply_nested_valid_input` uses `level0 { level1 { ... leaf "value"; ... } }` and `test_very_long_valid_input` uses `section cb1 { entry0 "value_0"; ... }`. Both parse successfully, confirming the parser accepts these constructs. However, neither uses actual Limnalis domain constructs (like `claim_block`, `claim`, `evaluator`, etc.), so they test grammar acceptance of generic block/statement syntax rather than domain-specific syntax. This is not wrong -- the purpose is to test parser robustness at scale -- but it limits the value of the structural assertions.

## Semantic Drift Risks

None identified.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **S1 (MEDIUM):** `_compare_transport` per_evaluator comparison has the same one-directional blindness that A1 fixed in `_compare_claim` and `_compare_block`. This was out of scope for this changeset but should be tracked as a follow-up.
- **TG1 (LOW):** No dedicated unit test for the `_compare_block` reverse evaluator check. The fix is correct and covered indirectly by conformance tests.
- **TG2 (LOW):** Companion parser tests use generic syntax rather than domain constructs. Acceptable for robustness testing but limits domain coverage.

## Verification

- `python -m pytest tests/ -q`: 349 passed
- `python -m pytest tests/test_conformance.py -v`: 41 passed
- A1 reverse check pattern in `_compare_block` exactly mirrors `_compare_claim` pattern
- A1 uses dot notation throughout (no bracket access)
- A2 threshold is `>= len(corpus.cases) // 2` in all three determinism test classes
- A2 `test_full_pipeline_determinism` now tracks `skipped` and `tested` counters correctly
- A2 remaining `except Exception` at line 100 tracks skip reason and is guarded by threshold
- A3 fixed tests use `pytest.raises(UnexpectedInput)` explicitly
- A3 companion tests exercise success path with `isinstance(result, Tree)`, `result.data == "start"`, and `len(result.children) > 0` assertions
- A3 companion test inputs confirmed as valid Limnalis syntax via direct parser execution
