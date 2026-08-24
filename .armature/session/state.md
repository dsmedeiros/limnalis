# Armature Session State

## Current Objective
Milestone 7: Spec-conformance remediation + Track C paradox corpus. PRD: `.taskmaster/docs/milestone-7-remediation-track-c.md`. (M6C completed; see journal.)

## Build Candidate
{M6C ready for tagging; M7 in progress}

## Task Status
| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| T1 | Belnap–Dunn pair algebra in runtime (B∧N=F) | completed — reviewer PASS | wave-1 |
| T2 | Normalizer precedence/recursion/aliases/judged_by per EBNF | completed — reviewer PASS_WITH_ADVISORIES | wave-1 |
| T2b | Advisory follow-up: note/declare pipeline parity, malformed-operator handling | delegated | wave-2 |
| T3 | EvaluationStep.claim_subset (§16.2.1) | completed — reviewer PASS_WITH_ADVISORIES | wave-2 |
| T4 | EvaluationSession.shared_state (§16.6.3) | completed — reviewer PASS_WITH_ADVISORIES | wave-2 |
| T5 | Extension corpus: connective/precedence coverage + spec-A11 case | pending | wave-3 |
| T6 | Extension corpus: Track C paradox bundles (C1–C4) | pending | wave-3 |
| T7 | Paradox gallery doc | pending | wave-3 |

## Active Delegation
T2b remediation cycle 1/3: reviewer found one confirmed regression (unshielded |...| ref spans in the new marker scan) — implementer resumed with fix brief; re-verification pending. T3+T4 complete and committed (reviewer PASS_WITH_ADVISORIES: frame-overlay test gap, missing conformance agents.md, pre-existing phase-type inconsistency — logged for follow-up). Combined tree verified by orchestrator: 988 tests passing, 16/16 vendored conformance.

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
