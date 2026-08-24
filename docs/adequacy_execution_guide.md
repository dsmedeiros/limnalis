# Adequacy Execution Guide

## Overview

Milestone 6B extends adequacy from declared assessments toward real basis-driven execution with contested multi-producer aggregation. The existing `evaluate_adequacy_set` primitive is unchanged; the new functions are standalone helpers.

See [ADR-008](adr/008-contested-adequacy-aggregation.md) for the design rationale.

## Basis-Driven Adequacy

`execute_adequacy_with_basis` resolves each basis item against actual claim/evidence results and computes an adequacy score:

```python
from limnalis.api.adequacy import (
    execute_adequacy_with_basis,
    BasisResolutionEntry, AdequacyExecutionTrace,
)

trace, diagnostics = execute_adequacy_with_basis(
    assessment=adequacy_assessment,
    basis_claims={"c1": claim_result_1},
    basis_results={"c1": eval_node_1},
    services={},
)

# trace.adequate — bool
# trace.failure_kind — None, "threshold", "basis_failure", "circular_basis", etc.
# trace.basis_resolution — list of BasisResolutionEntry
# trace.score_divergence — |computed - declared| if both exist
```

## Failure Kinds

| Kind | Meaning |
|---|---|
| `threshold` | Score below threshold |
| `method_conflict` | Computed and declared scores diverge beyond tolerance |
| `basis_failure` | One or more basis items could not be resolved |
| `circular_basis` | Self-referencing basis chain detected |
| `policy_failure` | Aggregation policy could not produce a result |

## Contested Adequacy

When multiple producers assess the same task, `aggregate_contested_adequacy` resolves disagreements:

```python
from limnalis.api.adequacy import aggregate_contested_adequacy

trace, diagnostics = aggregate_contested_adequacy(
    assessments=[assessment_1, assessment_2, assessment_3],
    basis_results={"c1": eval_node},
    resolution_kind="paraconsistent_union",
    services={},
)
```

### Resolution Strategies

The strategy names are the spec's resolution-policy kinds, and their semantics are defined by spec §8.3 applied to the assessments' truth-valued results (§9.3 aggregates multiple same-task assessments under the anchor's `adequacy_policy`):

| Strategy | Behavior (spec §8.3 / §9.3) |
|---|---|
| `single` | The designated member's assessment (or the first, absent member configuration) is the aggregate; others are ignored |
| `paraconsistent_union` | Pairwise union of assessment truth values: one T and one F yield `B`; an assessment-level `B` (e.g. `B[method_conflict]`) propagates into the aggregate; T with N yields T |
| `priority_order` | First assessment in the declared order whose truth is **not N** -- including an F or B result; all-N yields N |
| `adjudicated` | Delegate to an adjudicator binding; falls back to `paraconsistent_union` when none is available |

The spec's own case A12 pins this down: with `aa1 = B[method_conflict]` and `aa2 = T` under `adequacy_policy: paraconsistent_union`, the aggregate is `B` because the union **carries aa1's B forward** -- not because the producers "disagree". Note in particular that `priority_order` is *not* "first adequate wins": an inadequate (F) assessment earlier in the order is decisive and stops the walk.

> **Implementation status:** the normative Phase-4 path (`evaluate_adequacy_set`, exercised by conformance case A12) implements the spec semantics above. The standalone helper `aggregate_contested_adequacy` shown in this guide currently retains older divergent behavior ("all must agree; disagreement → adequate=False with `failure_kind="method_conflict"`" for `paraconsistent_union`, and "first adequate wins" for `priority_order`). That divergence is a known implementation deviation slated for remediation; until then, rely on the runner's Phase-4 aggregation -- not this helper -- for spec-conformant contested adequacy.

## Circularity Detection

```python
from limnalis.api.adequacy import detect_basis_circularity

is_circular, diagnostics = detect_basis_circularity(assessment)
```

Detects when an assessment's basis list references its own ID or task, which would create an infinite evaluation loop.

## Key Design Properties

- Existing `evaluate_adequacy_set` (Phase 4) is unchanged
- New functions are standalone helpers, not runner phases
- `AdequacyExecutionTrace` provides full provenance for debugging
- Circularity detection is a shallow check complementing the existing deep `_detect_basis_cycles`
