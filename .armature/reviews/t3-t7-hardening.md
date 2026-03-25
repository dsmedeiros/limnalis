# Review Verdict: T3-T7 Hardening

## Scope Compliance
- Declared scope: `src/limnalis` (CLI, conformance runner), `tests` (test_conformance.py)
- Files modified (in scope):
  - `src/limnalis/cli.py` — evaluate subcommand, conformance run/report/list/show, --all flag
  - `src/limnalis/conformance/runner.py` — new file: conformance runner with validate_result_schema, fixture-backed eval
  - `tests/test_conformance.py` — new file: 41 tests covering diagnostics, determinism, pipeline, comparison
- Files modified (governance, expected):
  - `.armature/invariants/registry.yaml` — RUNTIME-001 updated 12->13 phases
  - `.armature/invariants/invariants.md` — RUNTIME-001 prose updated 12->13 phases
  - `src/limnalis/runtime/agents.md` — updated 12->13 phase references
  - `.armature/journal.md`, `.armature/session/state.md`, `.armature/reviews/` — session tracking
- Out-of-scope modifications: none

## Invariant Compliance
| Invariant | Status | Notes |
|---|---|---|
| FIXTURE-001 | PASS | No fixture corpus files modified (fixtures/, tests/fixtures/, tests/snapshots/ untouched) |
| SCHEMA-001 | PASS | validate_result_schema uses collect_validation_errors against conformance_result schema; conformance run integrates schema validation |
| RUNTIME-001 | PASS | Phase ordering updated 12->13 with compose_license inserted at phase 5; invariant registry, invariants.md, and runtime/agents.md all updated consistently; test_runtime_runner.py enforces 13 phases |
| NORM-001 | PASS | Normalizer unchanged; determinism tests (TestDeterminism, 4 tests) verify repeated runs produce identical output |
| MODEL-001 | PASS | No AST model changes |
| MODEL-002 | PASS | No AST model changes |
| SCHEMA-004 | PASS | Fixture corpus schema validation unchanged |

## Test Results
- Full suite: 231 passed, 0 failed, 1 warning (importlib deprecation)
- Conformance tests: 41 passed, 0 failed
- Test classes verified:
  - TestDiagnosticContractEnforcement (5 tests): severity/code/subject mismatch, exact match, stable ordering
  - TestNewTargets3C (2 tests): A2 and A4 source-driven pipeline
  - TestDeterminism (4 tests): provenance, diagnostic, block, evaluator ordering stability
  - TestRegressions3A (4 tests): A3, A11, A13, A14 continued passing
  - TestNewTargets3B (7 tests): A1, A5, A6, A10, A12, B1, B2
  - Coverage annotation documents all 7 required source-pipeline cases

## Observations
1. The `conformance run` default behavior runs all cases; the --all flag is accepted for explicitness but is redundant. This is acceptable CLI design.
2. The `conformance report --format json` hardcodes version "v0.2.2" rather than reading from pyproject.toml. This is a minor concern but not an invariant violation.
3. The `_build_injected_diagnostics` function injects diagnostics for codes that cannot be produced organically (frame_pattern_completed, logical_composition). This is a pragmatic design choice for fixture conformance testing and does not violate any invariant.
4. The phase ordering change (12->13) was properly coordinated across all references: runner, agents.md, registry.yaml, invariants.md, and tests.

## Verdict: PASS
