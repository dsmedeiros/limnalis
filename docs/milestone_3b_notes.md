# Milestone 3B: Broadened Evaluator + Conformance Harness

## What 3B Delivers

### Evaluator Semantics
- **eval_expr**: Full delegated leaf dispatch for PredicateExpr, DynamicExpr, CausalExpr, EmergenceExpr, CriterionExpr via evaluator binding contract. Internal handling for LogicalExpr (4-valued truth lattice), DeclarationExpr, JudgedExpr.
- **synthesize_support**: Default evidence-based support policy (supported/partial/conflicted/absent) plus evidence_policy override dispatch path for domain-specific handlers.
- **evaluate_adequacy_set**: Multi-assessment aggregation under single/paraconsistent_union/priority_order policies. Basis cycle detection, method conflict detection, threshold handling, score-omitted defaults.
- **compose_license**: Exact-set anchor matching, missing_joint_adequacy vs joint_inadequacy distinction, claim/task resolution via annotation/policy/frame fallback, worst-truth-wins severity ordering (F > B > N > T).
- **execute_transport**: All 5 modes (metadata_only, pattern_only, preserve, degrade, remap_recompute). Precondition evaluation, semantic_requirements/lose intersection, degradation rules, claim mapping dispatch.
- **apply_resolution_policy**: Extended with correct support aggregation priority (conflicted > partial > supported > inapplicable > absent), confidence propagation, deterministic provenance union.
- **fold_block**: Block conjunction semantics (F dominates, B+N=F).

### Diagnostics
- Rule 23: `lint.transport.semantic_requirements_empty` (warning, phase: transport)
- Rule 24: `lint.adequacy.missing_policy_multi_assessment` (warning, phase: license)
- Rule 25: `lint.adequacy.circular_basis` / `circular_dependency` (error, phase: license)
- Deterministic diagnostic ordering via sort_diagnostics (phase, code, subject)

### Result Shaping
- Structured ClaimResult, BlockResult, TransportResult models
- EvaluationResult/SessionResult with baseline_states and adequacy_store
- License results attached to ClaimResult, separate from world truth

### Runner
- 13 phases (compose_license added as phase 5; RUNTIME-001 updated)
- All 13 primitives now implemented (no stubs remaining)

### Conformance Harness
- `src/limnalis/conformance/` module: fixtures.py, runner.py, compare.py
- CLI commands: `conformance list`, `conformance show <case>`, `conformance run [--cases X,Y,Z]`
- Lenient comparison (only declared expectation fields)
- Fixture-backed evaluator bindings, support policies, adjudicators

## Corpus Cases Running End-to-End

| Case | Description | Status |
|------|-------------|--------|
| A1 | Resolved shorthand frame | PASS |
| A3 | 3A regression | PASS |
| A5 | Declared evidence conflict vs partial support | PASS |
| A6 | Exact-set licensing / missing joint adequacy | PASS |
| A10 | Transport warning path, preserve/degrade semantics | PASS |
| A11 | Multi-session with time/history binding | PASS |
| A12 | Multi-assessment + missing policy + circular basis | PASS |
| A13 | Missing binding localization | PASS |
| A14 | Adjudicated resolution policy | PASS |
| B1 | Grid contingency bundle (transport, adequacy, causal/emergence) | PASS |
| B2 | JWT access / judged policy bundle | PASS |

## Test Coverage
- 179 tests total (up from 126 in 3A)
- 85 runtime primitive tests (35 new)
- 15 conformance tests (11 corpus + 3 CLI + 1 mismatch)

## What Remains for 3C / Future Work

### Not Yet Targeted
- A2 (unresolved shorthand frame failure) — nice-to-have, not attempted
- A4, A7, A8, A9 — not in 3B scope
- CWT/B3 and future domain bundles — explicitly out of scope

### Potential 3C Work
- Resolve remaining fixture cases (A2, A4, A7-A9)
- Advanced inferred evidence reasoning
- User-defined block summary policies beyond normative fold
- Performance tuning / optimization
- Fully generic transport theorem/proof logic
- Production-grade adjudicated adequacy aggregation (currently uses injected handler path)
