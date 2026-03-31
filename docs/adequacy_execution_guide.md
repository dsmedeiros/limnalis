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

| Strategy | Behavior | Disagreement handling |
|---|---|---|
| `single` | Use first assessment only | Others ignored |
| `paraconsistent_union` | All must agree | Disagree → truth="B", failure_kind="method_conflict" |
| `priority_order` | Assessments in priority order | First adequate wins |
| `adjudicated` | Delegate to adjudicator binding | Falls back to paraconsistent_union |

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
