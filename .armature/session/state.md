# Armature Session State

## Current Objective
Milestone 4: Release Candidate hardening, interface freeze, packaging, and implementation governance for Limnalis v0.2.2

## Build Candidate
{pending commit}

## Task Status
| Task | Status | Scope | Wave |
|------|--------|-------|------|
| T1 Public API freeze | DONE | core | W1 |
| T2 Version/manifest metadata | DONE | core | W1 |
| T3 Packaging cleanup | DONE | core | W1 |
| T4 CLI stabilization | DONE | core | W2 |
| T5 Conformance runner hardening | DONE | core | W2 |
| T6 Public API + packaging tests | DONE | tests | W3 |
| T7 Determinism + property tests | DONE | tests | W3 |
| T8 Parser robustness + CLI tests | DONE | tests | W3 |
| T9 Conformance report tests | DONE | tests | W3 |
| T10 Docs/ADR cleanup | DONE | docs | W4 |
| T11 Deviation/compatibility policy | DONE | docs | W4 |
| T12 RC status report | DONE | docs | W4 |

## Active Delegation
{none — all tasks complete}

## Pending Reviews
Standard reviewer: PASS
Red team reviewer: PASS_WITH_ADVISORIES (all advisories resolved)

## Invariants Touched
None violated. All changes additive.

## Test Results
308 tests passing (baseline was 236), 16/16 conformance cases PASS (strict mode)

---
<!-- APPEND-ONLY BELOW THIS LINE -->

## Decisions Log
- SPEC_VERSION single-sourced in version.py (red team S1 fix)
- Allowlist error-priority reordered in conformance run (red team S2 fix)
- TestExactSetMatching removed (tested Python builtins, not limnalis code)

## Discovered Context
- Runtime __init__.py is intentionally minimal; evaluator API re-exports come from runtime.runner
- Adjudicator callable is a separate injection point on run_step, not part of PrimitiveSet
- Exact-set matching for joint adequacy is inline in _compute_license_result, no standalone function
