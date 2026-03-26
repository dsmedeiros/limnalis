# Red Team Review: m5-rt-integration (Cross-Cutting Integration)

## Summary

This is an adversarial cross-cutting review of the entire Milestone 5 changeset (D1-D10, F1) across two commits. All 313 tests pass, 16/16 conformance cases PASS, and no critical or high-severity issues were found. The changes are well-scoped and do not introduce regressions. The interaction effects between changes are benign. Prior red team reviews (m5-defect-remediation-redteam, m5-d3d4f1-redteam) are consistent with each other and with the actual code. Three non-blocking issues were identified, of which one (the _compare_block consistency gap) is the most significant systemic risk.

## Critical Findings

None.

## Subtle Issues

1. **D3 mismatch message says "none expected" when diagnostics ARE expected (LOW)**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, line 513
   - After D3, the `FieldMismatch` for extra error/fatal diagnostics uses the expected value `"none expected"`. This message was written for the old guard where it only fired when `expected_diags` was empty. Now that D3 removed the `not expected_diags` guard, this message can fire when there ARE expected diagnostics (just not matching this particular extra one). The correct message would be `"not expected"`, consistent with the D4 extra-evaluator message on line 125.
   - No behavioral impact -- FieldMismatch messages are for human debugging. But the text is technically inaccurate in the non-empty-expected-diags case.
   - Severity: LOW

2. **_compare_block lacks D4 reverse-evaluator check (MEDIUM, pre-existing, confirmed)**
   - File: `/home/user/limnal/src/limnalis/conformance/compare.py`, lines 292-315
   - Already flagged by m5-d3d4f1-redteam.md as advisory A2. Confirmed: `_compare_claim` (line 121-126) has the reverse check; `_compare_block` does not. The two functions serve the same structural role but now have asymmetric feature sets. No current fixture exercises the block extra-evaluator path, so there is no active regression, but this is the same class of blindness that D4 was intended to fix.
   - Severity: MEDIUM (consistency gap, latent defect)

3. **Unused `field_validator` import in base.py (LOW, pre-existing, confirmed)**
   - File: `/home/user/limnal/src/limnalis/models/base.py`, line 3
   - Already flagged by m5-defect-remediation-redteam.md as advisory A1. Confirmed: `field_validator` is imported but never used in this file after D7 removed `UniqueStringListModel`. Other files (ast.py, conformance.py) import it directly.
   - Severity: LOW

## Interaction Effects Analysis

1. **D1 (sorted reasons) x D3 (extra diagnostics):** No interaction. D1 changes reason deduplication ordering, but since it only takes effect when `len(unique_reasons) == 1`, ordering is irrelevant. The reason value is identical regardless of sort order for single-element collections. D3 operates on diagnostic comparison, not reason strings.

2. **D5 (operator precedence) x FIXTURE-001:** No interaction. The list-of-tuples preserves the same iteration order as the original dict (AND, IFF, IMPLIES, OR). Python 3.7+ dicts preserve insertion order, so the migration from `dict.items()` to list iteration is a no-op for ordering. All 16 conformance cases pass, confirming no normalized AST change.

3. **F1 (frame completion) x D1 (determinism):** No interaction. F1 operates pre-execution (completing the bundle frame before the runner processes steps). D1 operates during aggregation (sorting reasons in `apply_resolution_policy`). They touch different phases and different data structures.

4. **D7 (UniqueStringListModel removal) x MODEL-001/MODEL-002:** No impact. All AST nodes continue to inherit from LimnalisModel. The removed class was unused -- no subclass exists anywhere in the codebase.

## Invariant Compliance

| Invariant | Status | Evidence |
|-----------|--------|----------|
| SCHEMA-001 | PASS | 313 tests pass including schema validation tests |
| MODEL-001 | PASS | All AST nodes inherit LimnalisModel (verified via grep) |
| MODEL-002 | PASS | LimnalisModel has `extra="forbid"` in ConfigDict |
| NORM-001 | PASS | D1 and D5 strengthen determinism; conformance + determinism tests pass |
| FIXTURE-001 | PASS | 16/16 conformance cases PASS (verified via `pytest tests/test_conformance.py -v`) |

## Scope Compliance

- All changes are within declared scope per the journal entries.
- No unstaged application code changes (`git status` shows only the untracked prior review file `m5-rt-runtime.md`).
- Governance files (.armature/) accurately reflect the current state.

## Test Gaps

1. **No test enforces operator precedence order in `_LOGICAL_OPERATORS` (MEDIUM)**
   - Already flagged by m5-defect-remediation-redteam.md as advisory A2. The comment on line 100 of normalizer.py claims precedence semantics, but no test verifies that AND binds tighter than OR in a mixed expression.

2. **No dedicated unit tests for D3/D4/F1 (MEDIUM)**
   - Already flagged by m5-d3d4f1-redteam.md as advisory A3. These three changes are only exercised through integration (conformance case A1). If A1 changes or is removed, the coverage for these fixes disappears.

3. **D8 guards are permissive (LOW)**
   - Already flagged by m5-defect-remediation-redteam.md as advisory A3. `assert tested > 0` passes if 15 of 16 cases silently throw exceptions.

## Semantic Drift Risks

1. **`_compare_claim` and `_compare_block` are diverging** -- Same structural role, different feature sets. This is the most likely source of a future silent regression in the conformance comparison system.

2. **Unused imports in F1 block** -- `FacetValueMap`, `FrameNode`, `FramePatternNode`, and `_merge_frame_facets` are imported at `/home/user/limnal/src/limnalis/conformance/runner.py` lines 765-766 but unused. These are artifacts of a draft implementation and are dead weight.

## Prior Red Team Review Consistency

Both prior M5 red team reviews (m5-defect-remediation-redteam, m5-d3d4f1-redteam) are:
- Internally consistent with each other
- Accurate in their findings (all confirmed by this integration review)
- Correctly classified by severity
- Their advisories are tracked in `.armature/session/state.md`

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **A1 (MEDIUM):** Apply the D4 reverse-evaluator check to `_compare_block` in `/home/user/limnal/src/limnalis/conformance/compare.py` for consistency with `_compare_claim`. This is the same defect class that D4 was created to fix, applied to a parallel function.
- **A2 (MEDIUM):** Add targeted unit tests for D3 (extra-diagnostic detection when expected is non-empty), D4 (extra-evaluator detection), and F1 (frame completion from fixture environment). Currently these are only exercised through integration test A1.
- **A3 (LOW):** Correct the FieldMismatch expected value on line 513 of compare.py from `"none expected"` to `"not expected"` -- the old message is inaccurate after D3 removed the empty-expected guard.
- **A4 (LOW):** Remove unused imports (`FacetValueMap`, `FrameNode`, `FramePatternNode`, `_merge_frame_facets`) from runner.py lines 765-766.
- **A5 (LOW):** Remove unused `field_validator` import from `/home/user/limnal/src/limnalis/models/base.py` line 3.
