# Release Candidate Status Report: Limnalis v0.2.2rc1

**Date:** 2026-03-25
**Package version:** 0.2.2rc1
**Spec version:** v0.2.2
**Schema version:** v0.2.2
**Corpus version:** v0.2.2

## What Is Implemented

### Parser
Surface-language parser using Lark/Earley grammar. Produces permissive raw parse trees from authored `.lmn` files. Supports the full authored subset exercised by the fixture corpus.

### Normalizer
Tree-walking normalizer that transforms raw parse trees into canonical Pydantic-validated `BundleNode` ASTs. Handles all authored forms including frames, evaluator panels, claim blocks, claim expressions, evidence, baselines, bridges, transport, adequacy, assessment, and resolution policies. Emits compatibility diagnostics for forms that don't map 1:1 to the canonical schema.

### Evaluator
13-phase step runner with injectable primitive operations. Executes the normative evaluation order: context construction, reference resolution, baseline management, adequacy evaluation, license composition, evidence views, claim classification, expression evaluation, support synthesis, evaluation assembly, resolution policy application, block folding, and transport execution.

### Conformance Harness
Fixture-based conformance runner that loads the vendored corpus, executes cases through the full pipeline, and compares results against expected outputs with field-level granularity. Supports allowlists, strict mode, and JSON/Markdown report generation.

### Schema Validation
Validates normalized ASTs against the vendored `limnalis_ast_schema_v0.2.2.json`. Validates evaluation results against the conformance result schema. Includes opt-in repair pass for the known `$ref` typo in the shipped schema.

## Corpus Coverage

**16/16 cases PASS**

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

## Public APIs Frozen

The following modules constitute the stable public API surface:

| Module | Key Exports |
|--------|-------------|
| `limnalis.api.parser` | `LimnalisParser` |
| `limnalis.api.normalizer` | `Normalizer`, `NormalizationResult`, `NormalizationError`, `normalize_surface_file`, `normalize_surface_text` |
| `limnalis.api.evaluator` | `run_bundle`, `run_session`, `run_step`, `PrimitiveSet`, `BundleResult`, `SessionResult`, `StepResult`, `EvaluationResult` |
| `limnalis.api.conformance` | `load_corpus`, `load_corpus_from_default`, `run_case`, `compare_case`, `FixtureCase` |

Internal module paths are not part of the stable surface.

## CLI Commands

| Command | Status |
|---------|--------|
| `parse` | Stable |
| `normalize` | Stable |
| `validate-source` | Stable |
| `validate-ast` | Stable |
| `validate-fixtures` | Stable |
| `evaluate` | Stable |
| `print-schema` | Stable |
| `conformance list` | Stable |
| `conformance show` | Stable |
| `conformance run` | Stable |
| `conformance report` | Stable |
| `version` | Stable |

All commands support `--version` (global) and `--json` (where applicable). Conformance commands support `--strict` and `--allowlist`.

## Test Coverage

**309 tests total**, comprising:

- Unit tests for parser, normalizer, models, schema validation, loader, diagnostics
- Integration tests for the full source pipeline (parse, normalize, evaluate)
- Conformance tests for all 16 fixture corpus cases
- Property tests (Hypothesis) for four-valued logic lattice properties (commutativity, associativity, idempotency, annihilation, block fold order-independence)
- Determinism tests verifying normalization and evaluation produce identical results across runs
- Parser robustness tests for edge cases and malformed input

## Deferred to Future Milestones

- LSP / editor integration
- Performance tuning and benchmarks
- New language features beyond the v0.2.2 authored subset
- CWT/B3 and future domain bundles not in the current fixture corpus
- Advanced theorem/proof machinery for transport
- User-defined block summary policies beyond the normative fold
- Advanced anchor matching beyond exact-set
- Production-grade adjudicated adequacy aggregation (current: injected handler path)
- Authored source backfill for cases that currently only have canonical fixture form
- CI integration with conformance report artifact generation

## Known Deviations

None. All 16 corpus cases pass without allowlist entries.

## Recommendation

**RC Ready.**

All release criteria are met:
- Full corpus conformance (16/16 PASS)
- Public API frozen and documented
- CLI command set stable with consistent flags and exit codes
- 309 tests passing (unit, integration, property, determinism, robustness)
- No known deviations from the v0.2.2 spec
- Schema validation operational with known upstream typo repaired at runtime
