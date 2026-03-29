# Red Team Review: m5-rt-tests

## Summary

The three test-hardening changes (D8, D9, D10) are directionally correct and improve test quality over the prior state. However, D8 has a meaningful threshold weakness (`tested > 0` is too permissive for a 16-case corpus) and D9's strengthened assertions are dead code in 2 of 3 modified tests because those inputs currently take the `except UnexpectedInput` path. D10 is the strongest of the three changes with no blocking issues. Overall verdict is PASS_WITH_ADVISORIES.

## Critical Findings

None.

## Subtle Issues

### D8: `assert tested > 0` is a weak threshold (MEDIUM)

- **File:** `/home/user/limnal/tests/test_determinism.py`, lines 99 and 138
- **What:** The guard `assert tested > 0` permits 1 of 16 cases to be tested while 15 are silently skipped. Currently all 16 cases succeed (0 are skipped), but if a future change causes normalization failures in 15 of 16 cases, this test would still pass -- providing false confidence that normalizer determinism is verified.
- **How to trigger:** Introduce a regression that causes `normalize_surface_text` to throw for 15 of 16 fixture cases. The test still passes.
- **Recommendation consideration:** A threshold such as `assert tested >= len(corpus.cases) // 2` or `assert tested >= 10` would provide a meaningful safety margin. The exact threshold is an implementation decision.

### D8: `skipped` list is collected but never surfaced on success (LOW)

- **File:** `/home/user/limnal/tests/test_determinism.py`, lines 86 and 113
- **What:** The `skipped` list is only visible in the assertion message when ALL cases are skipped. If 14 of 16 cases are skipped but 2 pass, the test passes silently and the operator has no visibility into the skip rate. A `warnings.warn()` or pytest marker when skipped cases exceed a threshold would provide observability.

### D9: Strengthened assertions are unreachable in 2 of 3 modified tests (MEDIUM)

- **File:** `/home/user/limnal/tests/test_parser_robustness.py`, lines 58-59 and 78-79
- **What:** `test_extremely_deeply_nested_input` and `test_very_long_input` both construct syntactically invalid Limnalis input (using `claim c0 { predicate "test0" }` which is not valid surface syntax). The parser raises `UnexpectedInput` for these inputs, so execution always goes to the `except UnexpectedInput: pass` branch. The `assert result.data == "start"` and `assert len(result.children) > 0` lines are dead code -- they are never executed.
- **How to verify:** Run these tests with `--tb=short` and add a print inside the `try` block after the assertions; it will never print.
- **Impact:** The assertions create a false impression that parse-tree structure is being validated for large/complex inputs. In reality, these tests only verify that the parser raises a clean `UnexpectedInput` rather than crashing -- which is the same behavior they had before the change.
- **Root cause:** The test inputs are not valid Limnalis surface syntax. The deeply-nested test uses bare `{ }` blocks inside claims, which the grammar does not support (statements require `;` terminators, and `claim` is just an ATOM token in the grammar). To make these assertions reachable, the test inputs would need to produce valid parse trees.

### D9: `test_unicode_input` assertion `len(result.children) > 0` works but is fragile (LOW)

- **File:** `/home/user/limnal/tests/test_parser_robustness.py`, line 90
- **What:** `bundle uoa { }` parses to a tree with `start` root and 1 child (the `bundle` node). The bundle's `block` child has 0 `block_item` children. `len(result.children) > 0` passes because the `start` node has the `bundle` child, but if the test intent is to verify meaningful content, checking `result.children[0].data == "bundle"` would be more precise.

## Test Gaps

### `test_full_pipeline_determinism` has no tested-count guard (MEDIUM)

- **File:** `/home/user/limnal/tests/test_determinism.py`, lines 40-72
- **What:** The D8 fix added `assert tested > 0` to `test_normalizer_diagnostics_ordering_stable` and `test_provenance_ordering_stable`, but `test_full_pipeline_determinism` has similar `continue` branches (lines 57 and 65) without any count guard. If all 16 cases return errors, the test passes having never reached the JSON comparison at line 70. This is a less severe variant because the error-path `continue` is guarded by assertions, but a `tested` counter for the JSON comparison branch would be consistent.

### `test_markdown_report_includes_version` was not strengthened (LOW)

- **File:** `/home/user/limnal/tests/test_conformance_reports.py`, lines 196-203
- **What:** This test still uses weak substring checks (`"limnalis" in captured.out.lower()`, `"Spec:" in captured.out`). It does not verify that version strings contain actual version numbers (e.g., a semver pattern). This is consistent with D10 being scoped to the summary/table tests, but it is a gap.

## Semantic Drift Risks

### D10 `re` import at function scope (LOW)

- **File:** `/home/user/limnal/tests/test_conformance_reports.py`, line 116
- **What:** The `import re` is inside `test_markdown_report_has_summary`. This is functional but unconventional -- the standard Python convention is module-level imports. If another test in the same class later needs `re`, the import will be duplicated or inconsistently placed.

### D10 header assertion redundancy (LOW)

- **File:** `/home/user/limnal/tests/test_conformance_reports.py`, lines 110-113
- **What:** `assert lines[0].startswith("# ")` followed by `assert lines[0].startswith("# Conformance Report")`. The second assertion strictly subsumes the first. The first assertion is dead weight.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

1. **D9 dead assertions (MEDIUM):** 2 of 3 strengthened parser robustness tests have unreachable assertions because the test inputs are invalid Limnalis syntax. The assertions provide no value in their current form. Either fix the test inputs to be valid, or remove the assertions from those two tests to avoid false confidence.
2. **D8 weak threshold (MEDIUM):** `assert tested > 0` should be raised to a meaningful minimum (e.g., `>= len(corpus.cases) // 2`) to prevent silent degradation of test coverage.
3. **D8 missing guard on `test_full_pipeline_determinism` (MEDIUM):** The same pattern that D8 fixed in T7.2 and T7.3 exists in T7.1 -- `continue` branches that skip the deep comparison without tracking how many cases reached it.
