# Milestone 3C: Full Conformance Pass and Pipeline Hardening

## Summary

Milestone 3C brings the Limnalis v0.2.2 reference implementation to full corpus conformance. All 16 fixture cases pass end-to-end, the evaluator outputs validate against the conformance-result schema, and the CLI supports standalone evaluation and machine-consumable reporting.

## Conformance Results

| Case | Name | Status |
|------|------|--------|
| A1 | Resolved shorthand frame | PASS |
| A2 | Unresolved shorthand frame | PASS |
| A3 | Logical composition and block folding | PASS |
| A4 | Baseline modes | PASS |
| A5 | Evidence conflict vs partial support | PASS |
| A6 | Individual and joint adequacy | PASS |
| A7 | Bridge transport: metadata_only vs preserve | PASS |
| A8 | Multi-evaluator conflict | PASS |
| A9 | Priority-order resolution | PASS |
| A10 | Transport truth modes | PASS |
| A11 | Session-based baseline timing | PASS |
| A12 | Adequacy method conflict and circularity | PASS |
| A13 | Core JudgedExpr | PASS |
| A14 | Adjudicated resolution | PASS |
| B1 | Grid contingency bundle | PASS |
| B2 | JWT access / adequacy bundle | PASS |

**16 passed, 0 failed, 0 errors**

## What 3C Delivers

### Full Corpus Conformance (A2, A4 fixed)
- **A2 (Unresolved shorthand frame):** Conformance runner now respects `sessions: []` in fixture expectations and emits `frame_unresolved_for_evaluation` diagnostic at the bundle level.
- **A4 (Baseline modes):** Moved baseline `kind=moving` + `evaluationMode` validation from model layer (Pydantic validator) to runtime `resolve_baseline` (phase 3). Invalid baselines now normalize successfully and are marked `"unresolved"` with a `baseline_mode_invalid` diagnostic at runtime, matching the corpus expectation.

### CLI Enhancements
- `python -m limnalis evaluate <path>` — full source pipeline (parse -> normalize -> evaluate), JSON output
- `python -m limnalis evaluate --normalized <path>` — skip parsing, evaluate from normalized AST
- `python -m limnalis conformance report --format json` — machine-consumable JSON report
- `python -m limnalis conformance report --format markdown` — readable summary table

### Schema Validation Hardening
- Evaluator outputs are validated against `limnalis_conformance_result_schema_v0.2.2.json` after each case run
- Schema violations surfaced in conformance run output and reports
- Malformed results fail loudly with path and message details

### Diagnostic Contract Enforcement
- Diagnostic comparison checks severity, code, and subject fields
- Deterministic diagnostic ordering via `sort_diagnostics` (phase, code, subject)
- Tests verify mismatch detection for severity, code, and subject individually

### Test Coverage
- 231 tests total (up from 224 pre-3C)
- 11 new tests:
  - 5 diagnostic contract enforcement tests
  - 2 source-driven pipeline tests (A2, A4)
  - 4 determinism/stability tests
- Source-pipeline coverage for all 9 required cases: A1, A2, A3, A4, A11, A13, A14, B1, B2

## Deviations and Design Decisions

### BaselineNode Validation Relocation
The `_moving_requires_tracked` Pydantic model validator was removed from `BaselineNode` in `models/ast.py`. This is a corpus-driven decision (FIXTURE-001: fixture corpus is the conformance authority). The corpus expects A4 to normalize successfully and produce a runtime diagnostic, not fail at model construction. The constraint is now enforced at runtime in `resolve_baseline` (builtins.py).

### No Spec Contradictions Found
No contradictions between the v0.2.2 spec/corpus and the implementation were discovered during 3C. All 16 cases conform without deviation notes.

## What Remains for Future Work

### Not Implemented (Intentionally Deferred)
- New language features
- Major AST/schema redesign
- Performance tuning
- CWT/B3 and future domain bundles not in the fixture corpus
- Advanced theorem/proof machinery
- User-defined block summary policies beyond the normative fold
- `compose_license` advanced anchor matching (current implementation handles exact-set)
- Production-grade adjudicated adequacy aggregation (uses injected handler path)

### Potential Future Improvements
- Authored source backfill for cases that currently only have canonical fixture form
- Snapshot regression tests for normalized AST intermediate outputs
- CI integration with conformance report artifact generation
- Extended transport theorem/proof logic
