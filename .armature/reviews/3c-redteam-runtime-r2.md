# Red Team Review: 3c-redteam-runtime-r2

## Summary

Round 1 identified two issues in `resolve_baseline`: (1) silent unresolved when baseline not found, and (2) zero unit tests. Both are now fixed. The `baseline_not_found` diagnostic is correctly shaped and the 5 new tests cover the primary code paths. No new bugs introduced. One minor test gap identified (no test for missing `__bundle__` key in services). Overall: solid fix.

## Critical Findings

None.

## Subtle Issues

**Diagnostic shape inconsistency across the file (pre-existing, not introduced by this fix):**
The diagnostic dicts in `builtins.py` do not follow a single schema. Some use `subject` (lines 620, 642, 706), some use `step_id` (line 146), some use `evaluator_id` (lines 1401, 1530), and some use `bridge_id`+`claim_id` (lines 2304, 2329). The `sort_diagnostics` helper in `models.py` compensates by falling back through `subject` -> `claim_id` -> `block_id` -> `primitive`, but this is fragile. The two new `resolve_baseline` diagnostics correctly use `subject`, which is the preferred key. This is not a regression -- it is pre-existing technical debt.

## Test Gaps

**Missing test: services dict with no `__bundle__` key.**
The `resolve_baseline` function handles `bundle is None` (line 612: `services.get("__bundle__")`), but this path is only exercised when the bundle contains no matching baseline (test at line 2278 passes `_services_with_baselines([])`). There is no test where the `services` dict itself lacks the `__bundle__` key entirely, i.e. `resolve_baseline("x", ctx, ms, {})`. The code would still produce `baseline_not_found`, but the path is untested. Severity: LOW.

**No test for `moving` + `on_reference` combination.**
The five tests cover: point/fixed (ready), point/on_reference (deferred), moving/tracked (ready), moving/fixed (unresolved), and not-found. The combination `kind=moving, evaluationMode=on_reference` is not tested. Per the code, `on_reference` is checked first (line 636) and would produce `deferred` regardless of kind, which is correct. But there is no test proving this. Severity: LOW.

## Semantic Drift Risks

None introduced by this change.

## Verdict: PASS

Both round 1 issues are properly resolved:
1. `baseline_not_found` diagnostic (lines 620-626) emits correct shape: `severity=warning`, `code=baseline_not_found`, `subject=<id>`, `phase=baseline`, `message=<descriptive>`.
2. Five tests at lines 2219-2292 cover the five primary code paths with correct assertions on both `status` and `diags`.

Tests confirmed passing: 110 passed in 0.29s.

## Advisories:
- Consider adding a test for `services={}` (no `__bundle__` key) to cover the `bundle is None` path explicitly.
- Consider adding a test for `moving` + `on_reference` to confirm deferred status takes precedence over kind-based logic.
