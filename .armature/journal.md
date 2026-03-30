# Armature Governance Journal

This is an append-only log of governance-relevant events. It is gitignored and survives code-level rollbacks, providing institutional memory across sessions.

**Do not edit or delete entries.** Only append new entries below.

---

## 2026-03-30 — Milestone 6A: Interoperability Layer

**Event:** Milestone 6A completed — all 10 tasks implemented, reviewed PASS, committed.

**Scope:** New `src/limnalis/interop/` subpackage, `linkml/` projection artifacts, CLI commands, tests, examples, docs.

**Deliverables:**
- Public interop API: envelopes (ASTEnvelope, ResultEnvelope, ConformanceEnvelope), exchange types, export/import functions
- Exchange package format (directory + zip) with manifest and SHA256 checksums
- LinkML projection pipeline with documented lossy mappings (27 AST, 5 results)
- 8 new CLI commands (export-ast, export-result, export-conformance, package-create/inspect/validate/extract, project-linkml)
- Compatibility checking (check_envelope_compatibility)
- 83 new tests (198 total, all passing)
- 4 downstream consumer examples
- 6 interop docs + JSON-LD/RDF note

**Invariants:** MODEL-001, MODEL-002, SCHEMA-001, NORM-001 verified across all tasks. No invariant exceptions.

**Governance files created:** `src/limnalis/interop/agents.md` (new scope)

**Reviews:** 10 reviewer verdicts, all PASS. Written to `.armature/reviews/t{1-10}-*.md`.

## 2026-03-30 — Red Team Review Cycle

**Event:** Red team adversarial review of full M6A changeset, followed by fix cycle and re-review.

**Red team findings:** 2 CRITICAL, 5 HIGH, 7 MEDIUM, 5 LOW, 12 PASS items.

**Critical fixes applied:**
- C1: Path traversal guard added to `extract_package` (zip member validation before extraction)
- C2: Live timestamp removed from LinkML projection output (determinism restored)

**High fixes applied:**
- H1: `_load_data_file` return type validation
- H2: `format` parameter renamed to `output_format`/`input_format` throughout interop API
- H3: `sort_keys=False` documented with rationale comment
- H4: Redundant zip open eliminated in `validate_package`
- H5: Invalid envelope import tests added

**Medium/Low fixes:** M1 (sorting), M3 (variable shadowing), M4-M7 (missing tests), L2 (dead code) — all resolved.

**Re-review verdict:** ALL 14 findings FIXED. 210 tests passing. No new issues introduced.

**Reviews:** `.armature/reviews/red-team-m6a.md`, `.armature/reviews/red-team-m6a-recheck.md`
