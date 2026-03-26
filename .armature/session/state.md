# Armature Session State

## Current Objective
Milestone 5: Defect remediation — resolve verified issues from deep code review

## Build Candidate
{pending}

## Task Status — Milestone 4 (complete)
| Task | Status | Scope | Wave |
|------|--------|-------|------|
| T1–T12 | ALL DONE | various | W1–W4 |

## Task Status — Milestone 5 (active)
| Task | Status | Scope | Group |
|------|--------|-------|-------|
| D1 M4: determinism fix (sorted reasons) | DONE | runtime | G1 |
| D2 M5: fix misleading docstring (7 stubs) | DONE | runtime | G1 |
| D3 M1: extra-diagnostic blindness | DEFERRED | core | G2 |
| D4 M2: one-directional evaluator comparison | DEFERRED | core | G2 |
| D5 M3: explicit operator precedence | DONE | core | G2 |
| D6 L1: remove dead code (cli return 2) | DONE | core | G2 |
| D7 L2: remove unused UniqueStringListModel | DONE | models | G3 |
| D8 L3: fix silent exception skipping in tests | DONE | tests | G4 |
| D9 L4: strengthen parser robustness assertions | DONE | tests | G4 |
| D10 L5: strengthen markdown validation tests | DONE | tests | G4 |

## Active Delegation
{none — all tasks complete or deferred}

## Pending Reviews
Red team reviewer: PASS_WITH_ADVISORIES (3 non-blocking advisories)

## Invariants Touched
NORM-001 (determinism — D1, D5 strengthen enforcement)

## Test Results
313 tests passing, 16/16 conformance cases PASS (strict mode)

## Reviewer Advisories (non-blocking)
1. (LOW) Unused `field_validator` import in base.py exposed by D7
2. (MEDIUM) No test enforces operator precedence order in normalizer
3. (LOW) `assert tested > 0` guards in test_determinism.py are permissive

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
