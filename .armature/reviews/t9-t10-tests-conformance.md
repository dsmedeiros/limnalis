# Review Verdict: T9 + T10 (Unit Tests + Corpus Conformance Execution)

## Scope Compliance

### T9 -- Unit Tests for Primitives
- Declared scope: `tests/`
- Files modified: `tests/test_runtime_primitives.py`
- Out-of-scope modifications: none

### T10 -- Corpus Conformance Execution
- Declared scope: `tests/` + `src/limnalis/conformance/` + `src/limnalis/runtime/`
- Files modified:
  - `src/limnalis/runtime/builtins.py` (within runtime scope)
  - `src/limnalis/conformance/runner.py` (within conformance scope)
  - `src/limnalis/conformance/compare.py` (within conformance scope)
  - `tests/test_conformance.py` (within tests scope)
  - `tests/test_runtime_primitives.py` (within tests scope)
- Out-of-scope modifications: none

### Scope Concern: T10 Modified builtins.py

T10 modified `src/limnalis/runtime/builtins.py`, which is within `src/limnalis/runtime/` scope. The changes are:

1. **Block fold semantics**: Changed from `_aggregate_truth` (paraconsistent union) to `_fold_block_truth` (conjunction semantics). Conjunction semantics: F dominates, B+N=F, B without N stays B, N without B stays N. This is a new function that did not exist on main.

2. **Support aggregation priority reordering**: Changed from `supported > partial > conflicted > absent` to `conflicted > partial > supported > inapplicable > absent`. Also added `aggregate_truth` parameter so B-truth forces conflicted support.

3. **Resolution policy conflict support**: Removed inline `agg_support = "conflicted"` override in evaluator_conflict case; now handled uniformly through the updated `_aggregate_support` function.

4. **New primitive implementations**: Added `execute_transport`, `synthesize_support`, `evaluate_adequacy_set`, `compose_license`, and `apply_resolution_policy_metadata` -- these are new code, not modifications to existing behavior.

**Assessment**: These changes are fixture-conformance-driven bug fixes justified by FIXTURE-001 (corpus authority). The fixture corpus defines correctness; the implementation must conform to fixtures, not the reverse. All 11 required fixture cases now pass, confirming alignment. The scope is within `src/limnalis/runtime/` which T10 declared.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 | PASS | Phase ordering preserved (1-13). Runner executes all phases in order. |
| RUNTIME-002 | PASS | New primitives follow uniform shape: op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics). 35 new tests verify primitive behavior. |
| RUNTIME-003 | PASS | NoteExpr bypass maintained. Tests verify non-evaluable claims skip eval_expr. |
| RUNTIME-004 | PASS | PrimitiveSet accepts injected implementations. Conformance runner injects fixture-backed eval_expr and synthesize_support. |
| FIXTURE-001 | PASS | All 11 corpus cases pass conformance: A1, A3, A5, A6, A10, A11, A12, A13, A14, B1, B2. Fixture expected outputs are the authority; implementation was corrected to match. |

## Test Verification

- **Full test suite**: 179 tests, all passing (`python -m pytest tests/ -q`)
- **Conformance run**: 11/11 cases PASS (`python -m limnalis conformance run --cases A1,A3,A5,A6,A10,A11,A12,A13,A14,B1,B2`)

### T9 Test Coverage
- TestExecuteTransport: 11 tests covering metadata_only, full transport, missing queries, multi-query
- TestSynthesizeSupport: 8 tests covering truth-to-support mapping, provenance, NoteExpr bypass
- TestEvaluateAdequacySet: 8 tests covering threshold evaluation, method conflict, circularity detection
- TestComposeLicense: 7 tests covering individual/joint adequacy, overall license derivation
- TestApplyResolutionPolicyMetadata: 4 tests covering confidence propagation, provenance sorting

### T10 Test Coverage
- 11 corpus conformance tests (4 regression + 7 new targets)
- 3 CLI tests (list, show, run)
- 1 mismatch detection test

## Key Semantic Changes Verified

1. **Block fold conjunction**: `_fold_block_truth` uses conjunction (F dominates) rather than paraconsistent union. This matches fixture expectations for block-level truth aggregation.

2. **Support priority reordering**: `conflicted > partial > supported` (was `supported > partial > conflicted`). Verified against fixture expectations -- the old ordering was incorrect per corpus authority.

3. **Reason codes**: `method_conflict` used for adequacy method disagreements; `evaluator_conflict` preserved for resolution policy evaluator disagreements. Test updates align with these fixture-defined codes.

## Verdict: PASS

All invariants satisfied. Scope compliance verified. Test suite and conformance suite both fully passing. The builtins.py changes are fixture-conformance-driven corrections within the declared T10 scope, justified by FIXTURE-001 corpus authority.
