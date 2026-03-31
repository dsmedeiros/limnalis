# Armature Session State

## Current Objective
Milestone 6B: Semantic expansion, advanced transport reasoning, summary policies, richer evidence inference, and new stress-test bundles for Limnalis v0.2.2+

## Build Candidate
{pending — ready for tagging after red team review}

## Task Status
| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| T1 | Foundation model extensions (Transport, Summary, Evidence, Adequacy types) | completed | 29894d3 |
| T2 | Advanced transport engine (bridge-chain, degradation, claim-map, trace, destination-completion) | completed | 2f0e24a |
| T3 | Summary policy framework (protocol, execution path, 3 built-in policies) | completed | b0808c2 |
| T4 | Evidence inference + adequacy execution (inference policy, basis-driven adequacy, contested aggregation) | completed | 1845c84 |
| T5 | CLI/API extensions (summary/inference CLI, 4 API re-export modules) | completed | 8ab1e02 |
| T6 | Stress bundles + corpus (CWT transport + governance stack bundles) | completed | 110a440 |
| T7 | Comprehensive tests (70 new tests across 7 test files) | completed | 1102dbb |
| T8 | ADRs and documentation (4 ADRs, 5 semantic guides) | completed | 312ca52 |

## Active Delegation
{none — all tasks complete}

## Pending Reviews
{none — all tasks reviewed PASS or PASS_WITH_ADVISORIES}

## Invariants Touched
MODEL-001, MODEL-002, MODEL-003, SCHEMA-001, RUNTIME-001, RUNTIME-002, RUNTIME-004

## Test Results
647 tests passing (up from 577 baseline), 0 failures

---
<!-- APPEND-ONLY BELOW THIS LINE -->

## Decisions Log
- Summary policies are non-normative by default (ADR-005)
- Evidence inference is opt-in only (ADR-006)
- Transport chains use explicit TransportPlan with fail_fast/best_effort modes (ADR-007)
- Contested adequacy supports 4 aggregation strategies (ADR-008)
- Summary section uses _SUMMARY_SEVERITY_ORDER/_summary_worst_truth to avoid shadowing existing _SEVERITY_ORDER/_worst_truth (name collision fix in T3)
- conformance.py runtime types use BaseModel not LimnalisModel (intentional — they are runtime types, not AST nodes)

## Discovered Context
- SummaryScope is duplicated in ast.py and conformance.py (noted for consolidation)
- transport.py API module imports from runtime.builtins/runtime.models directly (transport symbols not re-exported from runtime/__init__.py)
