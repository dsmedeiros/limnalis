---
scope: src/limnalis/conformance
governs: "Conformance harness: corpus loading, case execution, result comparison, reporting"
inherits: src/limnalis/agents.md
adrs: []
invariants: [FIXTURE-001, SCHEMA-001]
enforced-by:
  - tests/test_conformance.py
  - tests/test_conformance_comparison.py
  - tests/test_extension_corpus.py
persona: implementer
authority: [read, write, test]
restricted: [cross-cutting-changes, model-changes, vendored-corpus-changes]
---

# Limnalis Conformance Harness

## Overview
Runs corpus cases (parse → normalize → evaluate) and compares actual results against
corpus-pinned expectations. The vendored corpus (`fixtures/limnalis_fixture_corpus_v0.2.2.*`)
is the conformance authority (FIXTURE-001) and is immutable upstream material; the
project-authored extension corpus (`fixtures/limnalis_extension_corpus_v0.1.*`) extends
coverage and validates against the same vendored schema.

## Behavioral Directives
- Never modify the vendored corpus or schemas; extension coverage goes in the extension
  corpus, which must validate against `schemas/limnalis_fixture_corpus_schema_v0.2.2.json`
  with zero errors (track is schema-pinned to A|B; extension cases use track A, ids D*/C*).
- The fixture-echo evaluation path (claim-id-keyed expectation maps) is the vendored
  default; the live-services path (real primitives + plugin-pack bindings) activates only
  when every bundle evaluator binds to a live-pack URI (`build_live_fixture_services`).
  Changes must keep vendored case behavior byte-identical — prove with a before/after
  `conformance report --format json` diff when touching `run_case`.
- The live/echo gate is FAIL-CLOSED (m7 red-team HIGH-1): there is NO silent live→echo
  fallback. Partial live-pack coverage (some evaluator URIs live, some not) raises
  `LiveFixturePackCoverageError`, which `run_case` converts into a loud
  `CaseRunResult.error`; under a live corpus (one whose fixture manifest declares
  live-pack URIs — the extension corpus), an evaluator URI the manifest does not declare
  (e.g. a typo of a live URI) is also a loud error instead of a self-fulfilling echo.
  `CaseRunResult.eval_path` records which path served the case ("live"/"echo") and
  `tests/test_extension_corpus.py` asserts "live" for every extension case.
- Comparison functions must check both directions (expected-vs-actual and
  actual-vs-extra) — one-directional blindness is a previously remediated defect class.
  Step-level reverse checks (extra actual claims/blocks/transports under a pinned map)
  carry exactly two exemptions: non-evaluable note claims (the vendored convention omits
  them from expected claims — e.g. vendored B1 `c5`) and per-bridge transport
  scaffolding entries keyed by a declared bundle bridge id (e.g. vendored A7
  `b_pattern`/`b_exec`). Pinned `claimIds` are compared order-sensitively against
  `BlockResult.claims` (declaration order).
- Expectations are partial matchers (spec §18.2): an under-specified pin is never a
  failure. The one surfaced under-pin — a B/N truth pinned without a reason while the
  actual result carries one (§8.5 makes B/N reasons mandatory on the result side) — is
  reported through `CaseComparison.warnings`, which never affects `passed`.
- Evaluator output must validate against the vendored conformance-result schema.
- Runner-injected diagnostics (`frame_pattern_completed`, `logical_composition`) are a
  known comparator limitation documented in `docs/compatibility_and_deviations.md`;
  do not widen the injected set.

## Change Expectations
- Depends on runtime/ for execution and plugins/ for fixture bindings; no circular imports.
- YAML and JSON corpus twins must stay parse-identical (enforced by parity test).
- Determinism: identical corpus runs must produce identical results (NORM-001-adjacent).
