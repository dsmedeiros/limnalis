# Armature Governance Journal

This is an append-only log of governance-relevant events. It is committed to version control and provides institutional memory across sessions.

**Do not edit or delete entries.** Only append new entries below.

---

## 2026-03-14 — RUNTIME-001 invariant text update (12 → 13 phases)
**Event:** Invariant text change
**Invariant:** RUNTIME-001 (Phase Ordering)
**Change:** Updated phase count from 12 to 13 across registry.yaml, invariants.md, and runtime/agents.md
**Justification:** Milestone 3B spec requires compose_license integration as phase 5 in the runner pipeline. The phase ordering invariant's intent (strict ascending order) is preserved; only the count changed.
**Approved by:** Orchestrator (spec-driven change)

## 2026-03-14 — Orchestrator protocol violation: self-implemented PR review fixes
**Event:** Protocol violation (self-corrected)
**Rule violated:** "MUST NOT write application code" — orchestrator directly edited builtins.py, models.py, runner.py, compare.py instead of delegating to implementer agents
**Root cause:** Multi-fix scenario (6 issues from PR review) was treated as "quick patches" rather than delegated work. No triage/partition step was performed.
**Remediation:** Added "Multi-Fix and Bug-Fix Delegation" section to orchestrator persona with explicit protocol for batch-fix scenarios. Reinforces that even one-line fixes must be delegated.
**Approved by:** Human (escalation)

## 2026-03-25 — Milestone 3C: BaselineNode validator relocation
**Event:** Invariant-aligned design change
**Invariant:** FIXTURE-001 (Fixture corpus is conformance authority)
**Change:** Removed `_moving_requires_tracked` Pydantic model validator from `BaselineNode` in `models/ast.py`. Moved validation to runtime `resolve_baseline` in `builtins.py`. Invalid baselines now normalize successfully and emit `baseline_mode_invalid` diagnostic at runtime.
**Justification:** Fixture corpus case A4 expects `kind=moving + evaluationMode=fixed` to normalize and produce a runtime diagnostic with state `"unresolved"`. The model-level validator blocked normalization entirely, contradicting the conformance authority.
**Approved by:** Orchestrator (corpus-driven, FIXTURE-001)

## 2026-03-25 — Milestone 3C complete: full conformance pass
**Event:** Milestone completion
**Milestone:** 3C — Full conformance pass, pipeline hardening, evaluator stabilization
**Results:** 16/16 corpus cases PASS, 231 tests passing, schema validation active
**Deliverables:** evaluate CLI, conformance report CLI, schema-validated outputs, diagnostic contract tests, determinism tests, status document at docs/milestone_3c_status.md
**Approved by:** Orchestrator (pending reviewer verdict on T3-T7)

## 2026-03-25 — Milestone 4: RC Hardening complete
**Event:** Milestone completion
**Milestone:** 4 — Release Candidate hardening, interface freeze, packaging, governance
**Results:** 308 tests passing (up from 236), 16/16 conformance PASS (strict mode), package version 0.2.2rc1
**Deliverables:**
- Public API freeze: `limnalis.api.{parser, normalizer, evaluator, conformance}`
- Version/manifest metadata: `limnalis.version`, CLI `--version` and `version` command
- Packaging: pyproject.toml cleaned, extras (dev/test/docs), classifiers, URLs
- CLI stabilization: consistent exit codes, `--json`, `--strict`, `--allowlist`, clean error handling
- Conformance hardening: stable JSON/markdown reports, strict mode, deviation allowlist, version metadata
- Hardening tests: 72 new tests (public API, determinism, property/Hypothesis, parser robustness, CLI, conformance reports)
- Documentation: README quickstart, architecture.md, 4 ADRs, compatibility/deviation policy, RC status report
**Reviews:** Standard reviewer PASS, Red team PASS_WITH_ADVISORIES (all advisories resolved)
**Red team fixes:** S1 (SPEC_VERSION single-sourced), S2 (allowlist error-priority), S3 (test quality)
**Approved by:** Orchestrator (reviewer + red team verdicts received)

## 2026-03-26 — Milestone 5: Defect remediation
**Event:** Milestone completion
**Milestone:** 5 — Defect remediation from deep code review
**Results:** 313 tests passing (up from 308), 16/16 conformance PASS, 8 of 10 defects resolved
**Changes:**
- D1: Deterministic reason ordering in apply_resolution_policy (NORM-001)
- D2: Corrected misleading builtins.py docstring ("7 stubs" → "1 stub")
- D5: Explicit operator precedence in normalizer (dict → list of tuples)
- D6: Removed unreachable dead code in CLI
- D7: Removed unused UniqueStringListModel from models/base.py
- D8: Fixed silent exception skipping in determinism tests
- D9: Strengthened parser robustness test assertions
- D10: Strengthened markdown validation in conformance report tests
**Deferred:**
- D3: Extra-diagnostic blindness fix — correct logic but breaks FIXTURE-001 (exposes pre-existing runtime/fixture mismatch in case A1). Requires coordinated runtime+fixture investigation.
- D4: One-directional evaluator comparison — same FIXTURE-001 risk. Deferred with D3.
**Reviews:** Red team PASS_WITH_ADVISORIES (3 non-blocking: unused import, no precedence test, permissive test guard)
**Approved by:** Orchestrator (red team verdict received)

## 2026-03-26 — Milestone 5 addendum: D3/D4/F1 coordinated fix
**Event:** Deferred tasks resolved
**Tasks:** D3 (extra-diagnostic blindness), D4 (one-directional evaluator comparison), F1 (frame completion in conformance runner)
**Root cause:** Conformance runner injected `frame_pattern_completed` diagnostic but never actually completed the frame using fixture environment's `frame_resolver.bundle_frame_completion` data. Runtime correctly flagged missing scale/task facets. Old comparison logic hid the mismatch.
**Fix:** F1 implements frame completion from fixture environment before running the case. D3 removes the `not expected_diags` guard on extra-diagnostic checks. D4 adds reverse evaluator check.
**Results:** 313 tests passing, 16/16 conformance PASS (A1 and A2 both correct), all 10/10 defects now resolved
**Reviews:** Red team PASS_WITH_ADVISORIES (3 non-blocking: unused imports in runner.py, block-level comparison blindness in _compare_block, no dedicated unit tests for D3/D4/F1)
**Approved by:** Orchestrator (red team verdict received)

## 2026-03-26 — Milestone 5b: Red team advisory remediation
**Event:** Advisory remediation batch
**Scope:** 5-domain red team review produced 9 deduplicated advisories (5 MEDIUM, 4 LOW). User requested all LOW fixes + dedicated unit tests + operator precedence enforcement tests.
**Tasks resolved:**
- R1: Removed unused `field_validator` import in models/base.py (LOW, RT3/RT5)
- R2: Removed 4 unused imports in conformance/runner.py F1 block (LOW, RT2/RT5)
- R3: Fixed inconsistent bracket→dot path notation in compare.py D4 FieldMismatch (LOW, RT2)
- R4: Fixed inaccurate "none expected" → "not expected" message in compare.py D3 (LOW, RT5)
- R5: Added 10 dedicated unit tests for D3 (extra-diagnostic), D4 (reverse evaluator), F1 (frame completion) in test_conformance_comparison.py (MEDIUM, RT2/RT5)
- R6: Added 20 operator precedence enforcement tests covering all 4 operators + full first-match-wins transitivity chain (AND>IFF>IMPLIES>OR) in test_operator_precedence.py (MEDIUM, RT3)
**Results:** 343 tests passing (up from 313), 16/16 conformance PASS
**Reviews:** Red team PASS, then PASS_WITH_ADVISORIES (tautological assertion removed, missing IFF>IMPLIES test added, AND>IMPLIES and AND>OR tests confirmed present)
**Remaining advisories (deferred):**
- (MEDIUM) `_compare_block` missing reverse evaluator check — same D4 gap, low current risk
- (MEDIUM) D8 threshold too permissive + not applied to test_full_pipeline_determinism
- (MEDIUM) D9 assertions unreachable for deeply nested/long parser inputs
**Approved by:** Orchestrator (reviewer verdicts received)

## 2026-03-26 — Milestone 5b Cycle 2: Red team review→fix→review loop
**Event:** Iterative review loop (user-requested)
**Cycle 1 reviewers:** RT-C1a (code) PASS, RT-C1b (tests) PASS_WITH_ADVISORIES
- C1a: All code changes verified correct, no issues
- C1b: 4 advisories — D4 end-to-end test, reverse-order precedence tests, 2 docstring clarifications
**Fix round:** All 4 advisories found already addressed by G8 implementer (files were untracked during C1 review)
**Cycle 2 reviewers:** RT-C2a (tests) PASS, RT-C2b (integration) PASS
- C2a: All 4 claims verified, no tautological assertions, all tests substantive
- C2b: 347 tests pass, 41 conformance cases pass, clean changeset scope, no circular imports
**Result:** Clean PASS from all Cycle 2 reviewers — loop terminates
**Final test count:** 347 tests passing, 16/16 conformance PASS
**Approved by:** Orchestrator (all reviewers PASS)

## 2026-03-27 — Milestone 5c: Final MEDIUM advisory remediation
**Event:** Milestone completion
**Milestone:** 5c — Close remaining 3 MEDIUM advisories from M5/M5b red team reviews
**Tasks resolved:**
- A1: Added reverse evaluator check to `_compare_block` in conformance/compare.py (MEDIUM, one-directional blindness)
- A2: Raised D8 threshold from `> 0` to `>= len(corpus.cases) // 2` across all 3 determinism test functions including `test_full_pipeline_determinism` (MEDIUM, permissive threshold)
- A3: Converted unreachable success-path assertions in `test_extremely_deeply_nested_input` and `test_very_long_input` to explicit `pytest.raises(UnexpectedInput)`; added 2 companion valid-input tests (MEDIUM, unreachable assertions)
- A4: Added reverse evaluator check to `_compare_transport` (reviewer finding during A1 review — same defect class)
**Results:** 349 tests passing (up from 347), 16/16 conformance PASS
**Reviews:** Reviewer PASS_WITH_ADVISORIES (1 finding: `_compare_transport` blindness → immediately fixed as A4)
**Defect class closed:** One-directional per_evaluator comparison blindness now fully remediated across all 3 comparison functions (`_compare_claim`, `_compare_block`, `_compare_transport`)
**All red team advisories resolved:** 0 remaining from M4/M5/M5b/M5c review cycles
**Approved by:** Orchestrator (reviewer verdict received, all tests pass)

## 2026-03-27 — BaselineNode model-schema divergence documentation
**Event:** HIGH advisory closure (documentation)
**Advisory:** Model-schema constraint divergence on BaselineNode (3c-redteam-models, HIGH)
**Resolution:** Documented as intentional — the model omits the schema's `moving → tracked` constraint because FIXTURE-001 requires A4 to normalize so the runtime can emit `baseline_mode_invalid`. The constraint is enforced at two other layers: public API schema validation and runtime `resolve_baseline`.
**Changes:**
- Added 6-line comment above `BaselineNode` in `models/ast.py` explaining the divergence and referencing commit 549e3ce
- Added comment on A4 exclusion from parametrized normalizer test
- Added `test_a4_public_api_rejects_moving_fixed_baseline` proving the public API correctly rejects moving+fixed via schema validation
**Review:** Red team PASS — all claims verified, test exercises correct public API path, no invariant violations
**Test count:** 350 tests passing, 16/16 conformance PASS
**Status:** All HIGH-severity advisories across all review cycles are now resolved or documented
**Approved by:** Orchestrator (red team PASS)

## 2026-03-29 — Milestone 5 (Extension SDK): Complete
**Event:** Milestone completion
**Milestone:** 5 — Extension SDK, downstream integration validation, and example packs
**Results:** 439 tests passing (up from 350), 16/16 conformance PASS, all 4 consumer examples execute successfully, B1+B2 pass through conformance runner
**Deliverables:**
- Public extension SDK: `limnalis.api.{plugins, context, results, models, services}` (5 new modules, all re-export wrappers)
- Plugin registry: `limnalis.plugins.PluginRegistry` with register/get/list/unregister/clear, 8 kind constants, `build_services_from_registry()` helper
- Fixture plugin pack: `limnalis.plugins.fixtures` with `register_fixture_plugins()` helper
- Grid example plugin pack: `limnalis.plugins.grid_example` with `register_grid_plugins()` (3 evaluator bindings, 1 evidence policy, 3 adequacy methods)
- JWT example plugin pack: `limnalis.plugins.jwt_example` with `register_jwt_plugins()` (2 evaluator bindings, 1 evidence policy, 4 adequacy methods)
- Downstream consumer examples: 4 scripts under `examples/` (parse/normalize, fixture conformance, grid B1, JWT B2)
- CLI extension: `limnalis plugins list` and `limnalis plugins show` commands
- Extension author docs: 7 doc files (SDK overview, evaluator/criterion/adequacy/transport binding guides, downstream usage, interop)
- Integration tests: 6 new test files (registry, fixture pack, grid pack, JWT pack, CLI plugins, integration)
**Reviews:** Standard reviewer PASS (3 LOW non-blocking advisories: internal import in fixtures.py, naming overlap, docs accuracy)
**No invariant violations. No core semantic changes. Public API freeze preserved (additive only).**
**Approved by:** Orchestrator (reviewer PASS)

## 2026-03-29 — Milestone 5: Red team advisory remediation
**Event:** Advisory remediation
**Scope:** Red team cycle 1 produced 4 MEDIUM + 1 LOW advisories. All resolved.
**Tasks resolved:**
- S1/D1: Removed buggy `FixtureEvalHandler` from public API (renamed to `_FixtureEvalHandler`)
- S2: Inlined truth join lattice and support aggregation in FixtureAdjudicator, removing private `_aggregate_truth`/`_aggregate_support` imports
- D2: Added ADJUDICATOR wiring to `build_services_from_registry`, documented all 8 plugin kinds (4 auto-wired, 4 registry-only)
- T1: Renamed misleading `TestFixtureEvalHandler` to `TestFixtureEvalHandlerForEvaluator`
- T2: Added mixed-truth non-conflict adjudicator tests (T+N, F+N paths)
- T5: Added `default_synth` fallback tests (tuple and non-tuple paths)
- S3: Documented CLI exit code behavior with tests (list --kind nonexistent exits 0 is intentional)
**Results:** 446 tests passing (up from 439), 16/16 conformance PASS
**Reviews:** Red team cycle 1 PASS_WITH_ADVISORIES → fixes → Red team cycle 2 PASS (3 LOW non-blocking)
**Approved by:** Orchestrator (red team cycle 2 PASS)

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

## 2026-03-30 — Milestone 6B: Semantic Expansion

**Event:** Milestone 6B implementation complete — all 8 tasks implemented, reviewed, committed.

**Scope:** Semantic expansion: advanced transport, summary policies, evidence inference, adequacy execution, stress-test bundles, corpus, docs/ADRs.

**Deliverables:**
- Advanced transport engine: bridge-chain composition, degradation policies, claim-map validation, transport traces, destination completion (5 new functions in builtins.py)
- Summary policy framework: SummaryPolicyProtocol, 3 built-in policies (passthrough_normative, severity_max, majority_vote), execute_summary/run_summaries (7 new symbols)
- Evidence inference layer: EvidenceInferencePolicyProtocol, TransitivityInferencePolicy, build_evidence_view_with_inference, opt-in only (5 new symbols)
- Stronger adequacy execution: execute_adequacy_with_basis, aggregate_contested_adequacy (4 resolution strategies), detect_basis_circularity (3 new functions)
- 16 new model types: 10 AST nodes (ast.py), 6 runtime types (conformance.py)
- 4 new API modules: api/summary.py, api/evidence.py, api/adequacy.py, api/transport.py
- 2 CLI commands: summarize, list-summary-policies
- 2 stress-test bundles: CWT cross-frame transport, governance stack multi-evaluator
- 70 new tests across 7 test files (647 total, up from 577)
- 4 ADRs: 005-008 (summary separation, evidence opt-in, transport chains, contested adequacy)
- 5 semantic guides

**Invariants:** MODEL-001, MODEL-002, SCHEMA-001, RUNTIME-001, RUNTIME-002, RUNTIME-004 verified. No invariant violations.

**Key decisions:**
- Summary policies are non-normative by default, separated from fold_block (ADR-005)
- Evidence inference is opt-in; inferred relations returned separately from declared (ADR-006)
- Name collision fix: summary section uses _SUMMARY_SEVERITY_ORDER to avoid shadowing compose_license's _SEVERITY_ORDER

**Reviews:** 8 reviewer verdicts (7 PASS_WITH_ADVISORIES, 1 initial FAIL remediated to PASS). Non-blocking advisories: BaseModel vs LimnalisModel consistency, duplicate SummaryScope, transport.py import style, API import-only assertions.

**Approved by:** Orchestrator (all reviewer verdicts received, all tests pass)

## 2026-03-31 — Milestone 6B: Red Team Review Cycle

**Event:** Red team adversarial review of full M6B changeset, followed by fix cycle and clean re-review.

**Red team findings:** 1 CRITICAL, 2 HIGH, 4 MEDIUM, 4 LOW.

**Critical fix applied:**
- C1: CLI `summarize` command crashed with TypeError — wrong args to `execute_summary` and missing `model_dump()` on BundleResult

**High fixes applied:**
- H1: `adequate=True` with `failure_kind="method_conflict"` was semantically contradictory — divergence now produces diagnostic warning, not failure_kind
- H2: Added 6 CLI tests for `summarize` and `list-summary-policies` commands

**Low fixes applied:**
- L2: Removed unused `_SUMMARY_SEVERITY_RANK_TO_TRUTH` variable
- L3: Consolidated redundant `Protocol` imports

**Medium findings documented (not fixed — intentional design):**
- M1: Duplicate SummaryScope definition (ast.py + conformance.py) — consolidation deferred
- M2: New conformance.py types use BaseModel not LimnalisModel — intentional for runtime types
- M3: Scope inconsistency between policies for block scope — PassthroughNormative reads per_block_aggregates while others read block_results
- M4: First-trace-only in paraconsistent aggregation — information loss noted

**Re-review verdict:** ALL 5 findings FIXED. 653 tests passing. No new issues introduced.

**Approved by:** Orchestrator (red team cycle 2 PASS)

### 2026-04-02 — backport
Armature framework updated from (unversioned) to 1.0.0.
Source: /c/Users/Administrator/source/repos/armature (canonical Armature repo)
Files updated: 7 (.gitignore, ARMATURE.md, post-stop.sh, orchestrator.md, reviewer.md, reviewer-redteam.md, planner.md)
New files added: 11 (.armature/agents.md, 3 templates, .claude/agents/agents.md, .claude/commands/agents.md, armature-backport.md, armature-extend.md, armature-init.md, armature-update.md, checkpoint.md)
Schema migrations: config.yaml (added armature-version, changeset-budget); registry.yaml (migrated to structured enforced-by with ci/startup/runtime, added name/status/superseded-by/description/exceptions fields)
Invariant migrations: Added SPEC-001, SPEC-002 governance invariants from canonical Armature spec
Validation: PASS

### 2026-04-02 — Milestone 6C: Tooling, UX, Editor Support, Diagnostics, DX

**Event:** Implemented M6C in 3 waves (11 tasks, 3 waves, 4+6+1 parallelization).

**Wave 1 (foundation):**
- T1: Diagnostic formatter with plain/grouped/json modes, ANSI color, remediation hints
- T2: VS Code extension scaffold with TextMate grammar, snippets, language config
- T3: CLI module restructuring — cli.py monolith → cli/ package with extensible registration
- T9: Documentation — getting started, evaluation guide, 4 cookbook recipes, reading guide

**Wave 2 (features):**
- T4: Inspect commands (ast, normalized, trace, machine-state, license)
- T5: Lint/analyze/symbols/explain commands with structural analysis
- T6: Mermaid graph export (frame-graph, evaluator-graph, evidence-graph)
- T7: Doctor command — 7-point environment sanity check
- T8: Template generation (limnalis init bundle/plugin-pack/conformance-case)
- T11: SARIF 2.1.0 export for IDE diagnostics integration

**Wave 3 (integration):**
- T10: CLI flag consistency audit, --no-color propagation, help text snapshot tests

**Reviews:** 2 red team reviews (Wave 1: PASS_WITH_ADVISORIES, Wave 2+3: PASS_WITH_ADVISORIES). All findings fixed.
- Wave 1 fixes: Diagnostic.from_dict() None handling, doc CLI flag accuracy, editor comment note
- Wave 2+3 fixes: Path traversal in init_cmd, hyphenated plugin-pack name sanitization

**Tests:** 833 passed (up from 670 baseline), 163 new tests added, 0 failures.
**Invariants touched:** None — tooling-only milestone, no core semantic changes.
**Approved by:** Orchestrator (both red team cycles PASS)
