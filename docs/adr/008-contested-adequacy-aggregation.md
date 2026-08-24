# ADR-008: Contested Adequacy Aggregation

**Status:** Accepted
**Date:** 2026-03-30
**Context:** Milestone 6B — Stronger Adequacy Execution

## Decision

Multi-producer adequacy disagreements are resolved through four aggregation strategies: `single`, `paraconsistent_union`, `priority_order`, and `adjudicated`. The `AdequacyExecutionTrace` distinguishes failure kinds (`threshold`, `method_conflict`, `basis_failure`, `policy_failure`, `circular_basis`) to enable precise diagnostics.

## Context

The existing adequacy system supports declared assessments with optional executable methods. In practice, multiple producers (auditors, automated checkers, self-assessments) may assess the same task and disagree on the score. The system needs a principled way to handle disagreement without silently dropping minority assessments.

## Rationale

- **Multi-producer reality:** Real governance scenarios involve multiple assessors with different methodologies and thresholds.
- **Explicit disagreement:** Rather than silently averaging or picking one, the system names the aggregation strategy and records the outcome.
- **Failure classification:** Distinguishing threshold failure from method conflict from basis failure enables targeted remediation.
- **Basis-driven computation:** `execute_adequacy_with_basis` resolves basis claims/evidence and computes scores from actual results, not just declared values.

## Aggregation Strategies

| Strategy | Behavior |
|---|---|
| `single` | Use first assessment only; ignore others |
| `paraconsistent_union` | All must agree; disagreement produces `truth="B"`, `failure_kind="method_conflict"` |
| `priority_order` | Assessments in priority order; first adequate one wins |
| `adjudicated` | Delegate to an adjudicator binding; fall back to `paraconsistent_union` if none available |

## Consequences

- `aggregate_contested_adequacy` returns a consolidated `AdequacyExecutionTrace` with full provenance.
- `execute_adequacy_with_basis` provides basis resolution with `BasisResolutionEntry` per basis item.
- Score divergence (`|computed - declared|`) is tracked for monitoring purposes.
- Circularity detection prevents self-referencing basis chains.
- The existing `evaluate_adequacy_set` primitive is unchanged — new functions are standalone helpers.

## Alternatives Considered

1. **Simple averaging:** Rejected — loses information about disagreement and doesn't respect different assessment methodologies.
2. **Voting only:** Rejected — too simplistic for nuanced adequacy scores; a 0.71 vs 0.69 disagreement across a 0.70 threshold is fundamentally different from a 0.9 vs 0.3 disagreement.

---

## Amendment — 2026-08-24 (Milestone 8 documentation remediation)

The **Aggregation Strategies** table above defines `paraconsistent_union` as "all must agree; disagreement produces `truth="B"`, `failure_kind="method_conflict"`" and `priority_order` as "first adequate one wins". Those definitions do not match spec v0.2.2 §8.3/§9.3 or the spec's own case A12:

- Spec `paraconsistent_union` is a pairwise union of truth values (T with F → B; a member-level B — e.g. `B[method_conflict]` — propagates into the aggregate; T with N → T). In A12, `aa1 = B[method_conflict]` with `aa2 = T` aggregates to B because the union carries aa1's B forward, not because the producers disagree.
- Spec `priority_order` selects the first assessment in the declared order whose truth is **not N** — an early F or B result is decisive — rather than hunting for the first adequate one.

Status of the code at the time of this amendment: the normative Phase-4 aggregation (`evaluate_adequacy_set` → `_aggregate_adequacy_by_policy` in `src/limnalis/runtime/builtins.py`) implements the spec semantics and is what corpus case A12 exercises. The standalone helper `aggregate_contested_adequacy` (exposed via `limnalis.api.adequacy`) still implements this ADR's original divergent definitions; that divergence is now recorded as a known implementation deviation to be remediated (no `src/` changes were permitted in the milestone that added this note). `docs/adequacy_execution_guide.md` has been corrected to the spec's definitions.

This note records the correction; the ADR body above is preserved unchanged as a historical record.
