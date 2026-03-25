# Red Team Review: 3c-redteam-conformance

## Summary

The conformance module is well-structured and functionally correct for the current corpus. All 16 fixture cases pass, tests pass, and the CLI commands (`conformance run`, `conformance report --format json`, `conformance report --format markdown`) produce correct output. Schema validation of result payloads works correctly. However, there are several subtle issues around diagnostic comparison leniency, payload builder information loss, and a type annotation deficiency. No critical or high-severity bugs were found.

## Critical Findings

None.

## Subtle Issues

### S1: `_build_conformance_result_payload` silently drops claims with aggregate-only (MEDIUM)
- **File:** `src/limnalis/conformance/runner.py`, line 80
- The payload builder iterates `step.per_claim_per_evaluator` to build the claims section. Claims that exist only in `step.per_claim_aggregates` (but not in `per_claim_per_evaluator`) are silently omitted from the payload. This is coincidentally schema-compliant (the schema requires `per_evaluator` when `aggregate` is present), but it means claims resolved through a policy path that produces aggregates without per-evaluator entries will be invisible in the conformance result payload.
- **How to trigger:** A claim processed by a resolution policy that aggregates without retaining per-evaluator entries.
- **Impact:** The conformance result would underreport claims. Currently no corpus case triggers this.

### S2: `_compare_diagnostics` is lenient on extra actual diagnostics (MEDIUM)
- **File:** `src/limnalis/conformance/compare.py`, lines 397-437
- The comparison only checks that each expected diagnostic has a match in actuals. Extra actual diagnostics are silently ignored. This means a regression that introduces spurious error-level diagnostics would not be caught by conformance tests.
- **How to trigger:** A code change that adds unintended diagnostics to the runtime output.
- **Impact:** Conformance would still report PASS despite behavioral regression. This is by design for fixture-based conformance, but there is no complementary strict-mode check.

### S3: `_compare_eval_snapshot` partial-field matching can mask real mismatches (LOW)
- **File:** `src/limnalis/conformance/compare.py`, lines 62-85
- The function only checks fields present in the `expected` dict. If a fixture case omits `support` or `provenance` from its expected values, actual mismatches in those fields are invisible. This is intentional "don't care" semantics, but relies on fixture authors being comprehensive in their expectations. A fixture that declares `{"truth": "T"}` will pass regardless of what support/provenance/confidence values the runtime produces.
- **Impact:** Low -- the fixture corpus is the conformance authority, and this is the designed behavior. However, if a fixture case intends to test support values but forgets to include them in expected, the omission would not be caught.

### S4: `_extract_extra_resolution_policies` silently swallows all exceptions (LOW)
- **File:** `src/limnalis/conformance/runner.py`, line 675
- The bare `except Exception: pass` on line 675 means any failure in re-parsing source for extra resolution policies is silently ignored. If a bug in the parser or normalizer causes extraction to fail, the conformance run would proceed without the extra policies, potentially producing wrong results that differ from what the fixture expects. This would eventually surface as a comparison mismatch, but the root cause would be obscured.
- **How to trigger:** A parser/normalizer bug that only manifests during the second parse pass.
- **Impact:** Debugging difficulty when extra policy extraction fails silently.

## Test Gaps

### G1: No test for `validate_result_schema` with a real corpus case payload
The tests verify `validate_result_schema` returns `[]` for None bundle_result and use it in the CLI run flow, but there is no dedicated unit test that builds a payload from a real corpus case result and validates it against the schema. The current coverage is indirect (via CLI tests that check pass/fail counts).

### G2: No negative test for malformed evaluate CLI inputs
The evaluate command handles `UnexpectedInput`, `NormalizationError`, `SchemaValidationError`, and generic `Exception`, but no test verifies these error paths. The code was manually tested above and works correctly, but there is no regression protection.

### G3: No test for `conformance report --format markdown` output
`TestConformanceCLI` tests `list`, `show`, `run --cases`, and `run` (default), but does not test `report --format json` or `report --format markdown`. The markdown format was manually verified to produce correct output, but has no automated regression test.

### G4: No test for `_build_conformance_result_payload` edge cases
No test verifies the payload builder's behavior with empty sessions (dummy step0 insertion at line 147), diagnostics missing severity/code (filter at line 163), or the block per_evaluator truth-only serialization (line 123).

## Semantic Drift Risks

### D1: `_run_conformance_report` parameter typed as `object`
- **File:** `src/limnalis/cli.py`, line 368
- The `corpus` parameter is typed as `object` but the function accesses `.cases` on it. This should be typed as `FixtureCorpus` for static analysis and IDE support. Currently harmless but will obscure type errors if the corpus interface changes.

### D2: Diagnostic payload filter silently drops diagnostics without both severity and code
- **File:** `src/limnalis/conformance/runner.py`, line 163
- The condition `if diag_entry.get("severity") and diag_entry.get("code")` acts as a filter that drops diagnostics missing either field. This is correct for schema compliance (the schema requires both), but it means runtime diagnostics that lack a code or severity are silently removed from the conformance result. If the runtime starts emitting diagnostics with only a severity or only a code, these would be invisible in conformance results.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:
- **S1:** `_build_conformance_result_payload` should iterate the union of `per_claim_per_evaluator` and `per_claim_aggregates` keys to avoid silently dropping aggregate-only claims from the payload
- **S2:** Consider adding an optional `strict_diagnostics` mode to `_compare_diagnostics` that flags extra actual diagnostics, for use in CI regression detection
- **G2/G3:** Add test coverage for evaluate CLI error paths and conformance report formats
- **D1:** Fix `_run_conformance_report` parameter type annotation from `object` to `FixtureCorpus`
