# Armature Session State

## Current Objective
Milestone 8: Documentation remediation. PRD: `.taskmaster/docs/milestone-8-docs-remediation.md`. Three checkpoints (executable truth → contradictions/staleness → navigation/errata/deviations), docs+tests only. (M7 complete; see journal.)

## Build Candidate
{M7 ready for tagging — 1094 tests, extension corpus 11/11 live-path, vendored 16/16 echo-path byte-unchanged}

## Task Status
| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| T1 | Belnap–Dunn pair algebra in runtime (B∧N=F) | completed — reviewer PASS | wave-1 |
| T2 | Normalizer precedence/recursion/aliases/judged_by per EBNF | completed — reviewer PASS_WITH_ADVISORIES | wave-1 |
| T2b | Advisory follow-up: note/declare pipeline parity, malformed-operator handling, ref-span shielding | completed — reviewer PASS (after 1 remediation cycle) | wave-2 |
| T3 | EvaluationStep.claim_subset (§16.2.1) | completed — reviewer PASS_WITH_ADVISORIES | wave-2 |
| T4 | EvaluationSession.shared_state (§16.6.3) | completed — reviewer PASS_WITH_ADVISORIES | wave-2 |
| T5 | Extension corpus: connective/precedence coverage + spec-A11 case | completed — reviewer PASS_WITH_ADVISORIES (ckpt 1) | wave-3 |
| T6 | Extension corpus: Track C paradox bundles (C1–C4) | completed — reviewer PASS_WITH_ADVISORIES (ckpt 2) | wave-3 |
| T7 | Paradox gallery doc | completed — reviewer PASS_WITH_ADVISORIES (ckpt 3; required 2-cell fix applied) | wave-3 |

## Active Delegation
M8 checkpoint 1 (executable truth: broken snippets, install instructions, integrator field contract, doc-snippet test gate) — single implementer, Incremental Review Protocol. Advisory backlog unchanged (NEW-4+MEDIUM-7, then NEW-1/2/3; vocabulary alignment) for a future milestone.

## Pending Reviews
Wave 1 reviewer after T1+T2 complete. Red team over full M7 changeset at milestone end (required: NORM-001/FIXTURE-001-adjacent).

## Invariants Touched
NORM-001 (normalizer determinism — T2), FIXTURE-001 (vendored corpus immutable; extension corpus is a new file; precedence tests rewritten to spec with citations), RUNTIME-* (T1 truth algebra), SCHEMA-001 (extension corpus must validate against vendored schema).

## Test Results
Baseline entering M7: 833 tests passing, 16/16 vendored conformance PASS

---
<!-- APPEND-ONLY BELOW THIS LINE -->

## Decisions Log
- CLI module restructuring (T3) converts cli.py monolith to cli/ package
- Diagnostic formatting (T1) bridges raw dicts to typed Diagnostic instances
- Editor support (T2) uses TextMate grammar derived from limnalis.lark
- Documentation (T9) creates getting started, evaluation guide, and cookbook
- Visualization (T6) uses Mermaid-only; DOT deferred
- SARIF (T11) uses lightweight builder, no external dependency
- Template names sanitized: hyphens→underscores, path traversal prevented (red team fix)
- Upstream v0.2.2 consolidated spec vendored into spec/ (reviewer PASS); three spec-vs-impl gaps logged in journal: B∧N=F truth table, claim_subset, shared_state=false
- v0.2.2 recovery package vendored (reconstructed spec + recovered EBNF expression grammar + v0.2.2 matrix md); reviewer PASS_WITH_ADVISORIES; grammar-vs-implementation validation sweep delegated
- Validation sweep complete: reconstruction trustworthy (grammar corroborated by usage); CRITICAL normalizer operator-precedence inversion found (corpus-invisible); full gap ledger in journal; remediation milestone proposed to human
- Spec↔schema seam audit complete: machine edges strong; 3 hard A.9 errors in consolidated spec (schema+reconstruction agree against it — precedence partially inverted for AST appendix); A4 seam consistent-but-uncomfortable; docs-layer consistency review now covers all seams
