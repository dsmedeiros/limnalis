# Red Team Review: 3c-redteam-conformance-r2 (Round 2)

## Summary

All five Round 1 findings have been addressed. Tests pass (41/41), all 16 conformance cases pass, and fixture files are untouched. The fixes are structurally sound: `_compare_diagnostics` returns unmatched actuals, `_build_conformance_result_payload` uses the union of claim keys, `_extract_extra_resolution_policies` uses `warnings.warn` instead of bare except, and `internal_diagnostics` correctly isolates schema-fallback warnings from comparison. One medium-severity observation about the `[]`-diagnostics semantics is noted below but does not block.

## Critical Findings

None.

## Subtle Issues

### S1: `_compare_diagnostics` return value is unused (MEDIUM)

**File:** `src/limnalis/conformance/compare.py`, line 499
**What:** `_compare_diagnostics` now returns a `list[dict[str, Any]]` of unmatched actual diagnostics (the Round 1 fix), but the only call site at line 499 discards the return value. The return type change is correct in isolation, but no code path currently uses it.
**Impact:** The fix is technically complete (the function *can* report extras), but no consumer acts on it. If a future caller needs extra-detection, the plumbing exists. As-is, extra actual diagnostics beyond expected are silently accepted even when `expected_diags` is non-empty.

### S2: `diagnostics: []` means "don't care" masks runtime noise (MEDIUM)

**File:** `src/limnalis/conformance/compare.py`, line 498 (`if expected_diags:`)
**What:** Seven fixture cases (A5, A7, A8, A9, A10, A11, A14, B1, B2) have `diagnostics: []`. The truthiness guard skips comparison entirely. Empirically, cases A5, A7, A11, B1, B2 produce actual diagnostics (info-level `stubbed_primitive`, `history_binding_used`, and one warning `lint.transport.semantic_requirements_empty`).
**Impact:** The Round 1 resolution explicitly declared `[]` as "don't care" because the schema requires the field. This is defensible since the actual diagnostics are fixture-infrastructure artifacts. However, if a code change introduces a genuine error-level diagnostic in one of these cases, it will go undetected by comparison. The design trades strictness for tolerance of implementation noise.

## Test Gaps

### T1: No unit test for `_compare_diagnostics` return value

The four tests in `TestDiagnosticContractEnforcement` check the `mismatches` side-effect but never assert on the returned unmatched-actuals list. A test like "given expected=[X] and actual=[X, Y], return value is [Y]" would confirm the Round 1 fix.

### T2: No test for `internal_diagnostics` isolation

No test verifies that `CaseRunResult.internal_diagnostics` entries do not appear in `_collect_all_diagnostics(bundle_result)`. This is the core claim of the A4 schema-divergence fix.

## Semantic Drift Risks

### D1: `_build_conformance_result_payload` block per_evaluator serializes truth only

Line 129: `block_entry["per_evaluator"] = {ev_id: ev_node.truth for ev_id, ev_node in block_per_ev.items()}` discards reason, support, confidence, and provenance from block-level per-evaluator results. This is asymmetric with claim-level serialization (lines 91-100) which preserves all fields. If fixtures later expect block-level reason/support, the payload will silently omit them.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- S1: Consider consuming the `_compare_diagnostics` return value in `compare_case` to flag unexpected extra diagnostics when `expected_diags` is non-empty
- T1: Add a unit test asserting the return value of `_compare_diagnostics` for unmatched extras
- T2: Add a unit test confirming `internal_diagnostics` do not leak into `_collect_all_diagnostics`
- D1: Align block-level per_evaluator serialization with claim-level (include reason/support/confidence/provenance) in `_build_conformance_result_payload`
