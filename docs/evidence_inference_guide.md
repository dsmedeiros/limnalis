# Evidence Inference Guide

## Overview

Evidence inference is an opt-in extension that produces inferred evidence relations alongside declared ones. By default, only declared `EvidenceRelationNode` entries are used in evaluation. When an `EvidenceInferencePolicyNode` is provided, additional relations can be inferred.

See [ADR-006](adr/006-evidence-inference-opt-in.md) for the design rationale.

## Key Principle: Opt-In Only

Inferred relations **never** appear unless explicitly requested via an inference policy. The default evidence view contains only declared relations.

## Inferred vs Declared Relations

| Property | Declared (`EvidenceRelationNode`) | Inferred (`InferredEvidenceRelation`) |
|---|---|---|
| Source | Authored in .lmn surface syntax | Computed by inference policy |
| `declared` field | N/A (always declared) | Always `False` |
| `confidence` | N/A | [0-1], policy-computed |
| `method` | N/A | Inference method name |
| `provenance` | N/A | Traces source relations |
| In `ClaimEvidenceView.relations` | Yes | **No** (returned separately) |

## Built-in Policy: Transitivity

The `TransitivityInferencePolicy` applies two rules:

1. **Conflict transitivity:** If A conflicts with B and B conflicts with C, infer A *corroborates* C (enemy-of-my-enemy)
2. **Corroboration transitivity:** If A corroborates B and B corroborates C, infer A *corroborates* C

Confidence is the product of the source relation scores (default 0.5 if scores are None).

## Usage

```python
from limnalis.api.evidence import (
    build_evidence_view_with_inference,
    get_evidence_view_combined,
    TransitivityInferencePolicy,
)

# Build evidence view with inference
policy = TransitivityInferencePolicy()
view, inferred, diagnostics = build_evidence_view_with_inference(
    claim_id="c1",
    evidence_nodes=evidence_list,
    declared_relations=declared_rels,
    inference_policy=policy,
    services={},
)

# Get combined perspective
combined = get_evidence_view_combined(view, inferred)
# combined["declared_only"] — the original evidence view
# combined["inferred"] — list of InferredEvidenceRelation
# combined["combined_relations"] — declared + inferred together
```

## Inferred Relation Kinds

| Kind | Meaning |
|---|---|
| `conflicts` | Evidence items contradict each other |
| `corroborates` | Evidence items support each other |
| `depends_on` | One evidence item depends on another |
| `duplicate_of` | Evidence items are duplicates |

## Writing Custom Inference Policies

Implement `EvidenceInferencePolicyProtocol`:

```python
class MyInferencePolicy:
    def infer(self, evidence, declared_relations, services):
        inferred = []
        # Your inference logic
        return inferred
```
