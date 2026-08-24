# Milestone 7 — Spec-Conformance Remediation + Track C Paradox Corpus

**Status:** Approved by human ("Go for it", 2026-08-23). PRD authored by orchestrator from the session's validated gap ledger (see `.armature/journal.md` entries of 2026-08-23).

## Objective

Bring the implementation into conformance with the now-complete v0.2.2 specification set (canonical consolidated spec + recovered EBNF grammar), close the corpus blind spots that masked the divergences, and add a project-authored **extension corpus** containing connective-coverage cases and the four "Track C" paradox-forensics bundles (liar, Schwarzschild, decoherence cat, Banach–Tarski) that will serve as the paper's evaluation gallery.

## Authority and provenance constraints

- The vendored artifacts are **immutable upstream references**: `fixtures/limnalis_fixture_corpus_v0.2.2.{yaml,json}`, all of `schemas/`, all of `spec/`. No task in this milestone may modify them. The 16/16 vendored conformance result must remain green throughout.
- New corpus content goes in a NEW file: `fixtures/limnalis_extension_corpus_v0.1.yaml` (+ generated `.json`), validating against the vendored fixture-corpus schema, run by the same conformance machinery, clearly labeled project-authored.
- Where a current unit test asserts behavior that contradicts the spec (documented cases: `tests/test_operator_precedence.py` asserts inverted precedence trees), the test is REWRITTEN to assert the spec-mandated behavior, with the spec/EBNF citation in the test docstring. Tests are never deleted or weakened without a cited spec justification.

## Tasks

### Wave 1 — core semantic fixes (parallel: two scopes)

**T1 — True Belnap–Dunn pair algebra in the runtime** (scope: `src/limnalis/runtime/`, est. 80–150 LOC)
Replace the `_TRUTH_ORDER` linearization (`builtins.py:1427`) with the spec §4 pair algebra: T=(1,0), F=(0,1), B=(1,1), N=(0,0); AND = (t1∧t2, f1∨f2); OR = (t1∨t2, f1∧f2); NOT = swap; IMPLIES = ¬X∨Y; IFF = (X→Y)∧(Y→X). Verification targets (all from spec §4/reconstruction): B∧N=F, N∧B=F, B∨N=T, ¬B=B, ¬N=N, B→N=T, B↔N=T, full 16-entry conjunction table matches the spec table exactly. Licensing severity (F>B>N>T) and summary `_SUMMARY_SEVERITY_ORDER` are DIFFERENT, correct orderings — do not touch. Audit and fix any unit tests asserting the old linearized results (cite §4 in docstrings). Invariants: RUNTIME-*, FIXTURE-001 (vendored 16/16 must stay green — expected, since the fixture evaluator keys by claim id).

**T2 — Normalizer expression parsing to the recovered EBNF** (scope: `src/limnalis/normalizer.py` + its tests, est. 150–300 LOC)
Per `spec/Limnalis-v0.2.2-reconstructed.md` A.9 (EBNF lines ~1232–1281): binding tightest→loosest is NOT > AND > OR > IMPLIES > IFF. Under the first-match-splits algorithm the operator list must be loosest-first: `[IFF, IMPLIES, OR, AND]` (currently `[AND, IFF, IMPLIES, OR]` — inverted for AND). Additionally: (a) recurse on split remainders whether or not parenthesized — `b OR c` must never become an atomic PredicateExpr named "b OR c"; (b) unparenthesized top-level logical expressions must parse with structure; (c) separate NOT handling as a prefix unary that consumes only its operand per `UnaryExpr ::= [NotOp] CoreExpr`; (d) accept the spec's canonical operator spellings `->` and `<=>` (and Unicode ¬ ∧ ∨ → ↔ if straightforward) as aliases; retain the existing word forms NOT/AND/OR/IMPLIES/IFF for backward compatibility (permissive-parser philosophy), noting IMPLIES/IFF-as-words are legacy; (e) fix `judged_by` nesting: JudgedExpr is OUTERMOST (`Expr ::= JudgedExpr`), so `a =>[obs] b judged_by X` must yield Judged(Causal(a,b), X) — currently causal/EMRG are tested first. Rewrite `tests/test_operator_precedence.py` to assert the EBNF-mandated trees (e.g. `(a AND b OR c)` → OR(AND(a,b), c); `(a IFF b AND c)` → IFF(a, AND(b,c)); `(NOT a AND b)` → AND(NOT(a), b)), citing the EBNF. NORM-001 determinism must hold. Vendored 16/16 must stay green (corpus uses only parenthesized two-operand ANDs, which are precedence-invariant).

### Wave 2 — session semantics (after Wave 1 review PASS)

**T3 — `EvaluationStep.claim_subset`** (scope: `runtime/models.py`, `runtime/runner.py`, `conformance/runner.py`, est. 80–150 LOC): per spec §16.2/16.2.1 — limits which claims are evaluated in a step; excluded claims absent from results and block folding; no eager baseline forcing. PR #7 (commit c964192, unmerged) is prior art to consult for pitfalls, not to cherry-pick.

**T4 — `EvaluationSession.shared_state`** (scope: `runtime/`, est. 80–150 LOC): per §16.6.3 — fixed-baseline cache key (session_id, baseline_id) when true (default), (session_id, step_id, baseline_id) when false.

### Wave 3 — extension corpus (after Wave 2 review PASS)

**T5 — Coverage cases (Track D)** (scope: new `fixtures/limnalis_extension_corpus_v0.1.yaml` + fixture bindings in `src/limnalis/plugins/fixtures.py` + tests): cases exercising every connective through REAL sub-expression evaluation (per-atom fixture bindings, not claim-id keying): B∧N=F computed live; OR/NOT/IMPLIES/IFF tables on mixed inputs; unparenthesized precedence cases matching T2's trees; the consolidated spec §17.2 A11 narrative case (`test://baseline/by_context_v1` fixture, sessions s_shared/s_isolated) exercising shared_state=true AND false per the spec's stated expectations (closes the spec-vs-corpus A11 divergence as an extension case).

**T6 — Track C paradox bundles** (scope: extension corpus + `examples/` + fixture bindings): four cases with deterministic fixtures and pinned expectations —
- **C1 liar_forensics**: meta stratum; l0 note (non-evaluable, excluded); l1 `false(liar_sentence)` with placeholder anchor carrying no assessments → truth N[undefined_term], license N[not_yet_applicable], lint-13 warning; l3 self-referential judged claim, criterion fixture detects self-reference → B[self_reference]/absent; block(meta) = N∧B = **F** (flagship rule, computed live).
- **C2 schwarzschild_forensics**: per the session design — c1 geodesic incompleteness T/licensed (anchor prediction assessment 0.99≥0.95); c2 `curvature --> |inf:finite_time|` T (declared unboundedness, lint-11 satisfied); c3 `infinite_density` with semantic_requirements=[semiclassical_validity], degrade bridge losing that property → transport status degraded, dstAggregate N[transport_loss]; anchor description-task assessment score N → N[not_yet_applicable].
- **C3 decoherence_cat**: micro-frame superposition claim T; transport across amplification bridge (lose=[phase_coherence], mode degrade) → N[transport_loss]; two-evaluator panel (unitary fixture: T; collapse fixture: F) under paraconsistent_union → aggregate B[evaluator_conflict]/conflicted; block fold per-evaluator-first.
- **C4 banach_tarski**: ZFC-frame duplication theorem claim T (zfc fixture); volume-preservation claim using volume anchor unlicensed outside measurable-sets frame → license N; AC declared as an active Assumption record; second evaluator bound to ZF fixture → N[missing_binding]; aggregate under declared policy documented in expectations.
All Track C fixture bindings live under `test://paradox/...`, deterministic with stated outputs, following the vendored corpus's fixture conventions.

**T7 — Gallery documentation** (scope: `docs/paradox_gallery.md`, small): one doc explaining Track C's purpose, the layer-taxonomy reading (notation artifacts / fiction overreach / knowledge conflicts), and per-case verdict tables. No other docs work (the broad docs-remediation is a separate future milestone).

## Review protocol

Standard reviewer after each wave (verdicts to `.armature/reviews/m7-*.md`). Red team over the full milestone changeset at the end (critical invariants touched: NORM-001, FIXTURE-001-adjacent test rewrites, RUNTIME-*). Circuit breaker: 3 rejection cycles per checkpoint → escalate to human.

## Acceptance criteria

1. Full test suite green; vendored conformance 16/16 green and vendored files byte-unchanged.
2. Extension corpus validates against the vendored fixture-corpus schema and passes through the conformance runner with all pinned expectations met.
3. `(a AND b OR c)` and friends normalize to the EBNF-mandated trees; B∧N=F computed by the live truth algebra in at least one extension case.
4. claim_subset and shared_state observable behavior matches spec §16.2.1/§16.6.3, exercised by extension cases.

## Out of scope (explicitly deferred)

Intervention-clause grammar reconciliation; EmergenceExpr hysteresis/witness; Unicode-only operator forms beyond best-effort; the broad docs-remediation milestone (orphans, errata doc, matrix re-rendering); LinkML/interop changes; any modification to vendored spec/schema/corpus artifacts.
