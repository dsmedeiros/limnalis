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
