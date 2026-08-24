# Milestone 8 — Documentation Remediation

**Status:** Approved by human ("Docs remediation", 2026-08-23). PRD authored by orchestrator from the documentation usability audit, the spec-set consistency review, and the spec↔schema seam audit (journal entries of 2026-08-23), updated for post-M7 reality.

## Objective

Make the documentation layer internally consistent and truthful: every runnable snippet executes, every cross-doc contradiction is resolved in the spec's favor, every orphaned doc is reachable, the canonical spec's known errors are recorded in an errata companion (never by editing vendored artifacts), and the deviation-filing process the docs establish is actually used. Add cheap drift canaries so the fixed state stays fixed.

## Hard constraints

- Vendored artifacts immutable: `spec/Limnalis-v0.2.2.md`, `spec/Limnalis-v0.2.2-reconstructed.*`, `spec/Limnalis-v0.2.1.pdf`, the conformance matrices, `schemas/`, `fixtures/limnalis_fixture_corpus_v0.2.2.*`. Spec corrections go in a NEW errata doc.
- No changes to `src/` except NONE — this milestone is docs + tests only. (If a doc fix reveals a code bug, report it; do not patch.)
- ADRs are historical records: never rewritten. Corrections land as clearly marked dated amendment notes appended to the ADR.
- Re-verify every audit claim against the CURRENT tree before editing — M7 changed reality (new docs, new corpus, 1094 tests, new CLI behavior is unchanged but counts/links are not).

## Checkpoints (Incremental Review Protocol; one implementer; reviewer + commit per checkpoint)

### Checkpoint 1 — Executable truth (the broken last mile)

1. Fix every broken runnable snippet identified by the audit, re-verifying each against current source first:
   - `docs/downstream_usage_examples.md` (~12 sites): `.bundle` → `.canonical_ast`; `run_bundle(bundle, services=...)` → the real signature with sessions/env; `bundle.claims` → `claimBlocks`; `comparison.differences` → `.mismatches`; `run_case(case, services=...)` → real signature; the non-iterable `for case in corpus:` loop; the `tests/fixtures/*` paths (real fixtures live in `fixtures/`); the brace-less/semicolon-less surface-syntax block (lines ~31-38) → valid grammar.
   - `docs/plugin_sdk_overview.md:146,148` and `docs/cookbook/custom_plugin.md:53`: same `.bundle`/`run_bundle` fixes; `custom_plugin.md:65`'s "complete example" pointer corrected (the cited script uses run_case, not run_bundle) or a real run_bundle example referenced.
2. Honest installation everywhere (5 docs carry `pip install limnalis  # from PyPI`): first CHECK whether the package now exists on PyPI (it 404'd at audit time); if absent, replace with `pip install -e .` (and `.[dev]`) plus the from-source invocation `PYTHONPATH=src python -m limnalis …`, and list the four runtime dependencies.
3. Integrator field contract: `node_type` → `node` with PascalCase values (`export_formats.md:32,200`, `downstream_artifact_consumption.md:41`); `package_version: "0.1.0"` → the real value (6 places; verify against `version.py`).
4. NEW: `tests/test_doc_snippets.py` — extract and execute the Python snippets from the three wiring docs (mark extractable blocks with a stable convention, e.g. a `<!-- doc-snippet: runnable -->` marker or fenced-block indexing; choose the least intrusive mechanism and document it in `tests/agents.md`-consistent style). The fixed snippets must pass; the old broken forms must be unrepresentable or failing. This is the recurrence gate.

### Checkpoint 2 — Contradictions and staleness

5. Resolution policies: `how_evaluation_works.md:70` and `README.md:8` list `unanimous`/`majority` which do not exist — correct to `single | paraconsistent_union | priority_order | adjudicated` (README:69 already correct; make it consistent).
6. `degrade` transport: `transport_semantics.md:15` and `cookbook/transport_chains.md:13` ("support reduced; truth unchanged") and `writing_a_transport_handler.md`'s example (confidence-scaled copy + invented `degraded_transport` reason) all contradict spec §10.2 — align all three to the spec's degradation table; the handler-guide example becomes a custom truth_policy illustration explicitly labeled as overriding the default.
7. `cookbook/transport_chains.md:26,37`: bridge `preserve`/`lose` populated with evidence ids — correct to properties matched against `semantic_requirements`.
8. Adequacy-policy semantics: `adequacy_execution_guide.md:62` redefines `paraconsistent_union` ("all must agree; disagreement → B") and `priority_order` ("first adequate wins") differently from spec §4.3/§8.3 and the spec's own A12 usage — fix the guide to the spec's definitions; append a dated amendment note to `docs/adr/008-contested-adequacy-aggregation.md` recording the correction (never rewrite the ADR body).
9. Staleness: `architecture.md:124` ("transport … currently stubbed" — false) and `:91` + `README.md:196` (stale `cli.py` refs → the `cli/` package); `plugin_sdk_overview.md:35` phase-1 row (build step context is phase 1, resolve refs phase 2) and its API-module table (add summary/evidence/adequacy/transport); "Historical — superseded" banners with dates on `release_candidate_status.md`, `milestone_3b_notes.md`, `milestone_3c_status.md`, `m6b_stress_bundles.md`, `implementation_notes.md`.
10. SARIF: document the `sarif` output format on `lint`/`analyze` (a short `docs/sarif_export.md` or a section in an existing tooling doc — implementer picks the natural home; it is currently documented nowhere).
11. NEW drift canary: a test asserting README's CLI command table names a subset of `build_parser()`'s real commands and contains no command that does not exist (subset, not equality — README may legitimately stay curated; nonexistent commands are the bug class).

### Checkpoint 3 — Navigation, errata, deviations

12. `docs/README.md` index: purpose-grouped listing of all docs (including `paradox_gallery.md` and the M7 additions), a reading-order section promoting `reading_limnalis.md`, and adoption of every orphan (18 at audit time — recount). Root `README.md` gains links to `docs/README.md`, `examples/`, `editor/`, `docs/adr/`, and the interop cluster entry point.
13. `interop_overview.md:49-51`: soften the "RDF pipeline" overpromise into a pointer at `jsonld_rdf_note.md` (which stays the honest authority).
14. NEW `spec/Limnalis-v0.2.2-errata.md` (companion, vendored files untouched): the three hard A.9 errors (ClaimNode.eval/EvalNode; TermSpecNode orphan vs the schema's AnchorTermNode incl. its unwarranted `expr` variant; Bundle.frame optionality — schema and reconstruction agree against the canonical text); glyph-table conflicts between editions; lint rules 11/15 wording; §10.3-vs-§18.2 `sourceAggregate`; rule 21's `note(…)` notation vs the grammar; the dimensioned-literal grammar gap (corpus B1's `0.02_pu_per_min`); the A11 narrative-vs-vendored-corpus divergence WITH the note that extension case D5 now realizes the narrative; the reconstruction's degrade-precondition omission. Each entry: claim, evidence (file/line/section), which artifact is correct, status.
15. `spec/README.md`: precedence note nuanced per the seam audit — for AST shapes, the schemas then the reconstruction are more faithful than consolidated A.9; link the errata doc.
16. `docs/compatibility_and_deviations.md`: FILE the known deviations using the doc's own process — the `not_yet_applicable`/`no_adequacy_result` vocabulary divergence (score-N path now conformant post-M7; no-record path still divergent), unbound-reference surface syntax unsupported, assumption declarations unsupported, intervention-clause syntax mismatch, hysteresis/witness unimplemented — each with spec citation, current behavior, and status. Remove or annotate its now-stale "extra diagnostics may go undetected" limitation if M7's comparator work changed it (verify against compare.py's current behavior first).

## Acceptance criteria

1. `tests/test_doc_snippets.py` green; all previously broken snippets now execute against the real API.
2. Zero docs contradict the spec on resolution-policy kinds, degrade semantics, preserve/lose typing, or adequacy aggregation; grep-verifiable.
3. Every doc under `docs/` reachable from `docs/README.md`; root README links the index.
4. Errata + deviations filed; vendored artifacts byte-unchanged; full suite green.

## Out of scope

Any `src/` change; the advisory backlog (NEW-1..5, MEDIUM-4..7); CLI-table codegen; the A.9-vs-schema CI differ (errata records content; tooling deferred); PyPI publishing.
