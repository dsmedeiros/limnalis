# Limnalis v0.2.2 — AST pressure points settled from the corpus

This note records the AST decisions that are now treated as settled for schema drafting, based on the updated conformance corpus (A1–A14, B1–B2).

## ResolutionPolicyNode

Status: **settled**

Canonical shape:

```yaml
node: ResolutionPolicy
id: string
kind:
- single
- paraconsistent_union
- priority_order
- adjudicated
members:
- string
order:
- string
binding: string
```

Validation rules:

```yaml
single:
  members: required, length=1
  order: forbidden
  binding: forbidden
paraconsistent_union:
  members: required, length>=1
  order: forbidden
  binding: forbidden
priority_order:
  members: optional; if present must equal same set as order
  order: required, length>=1
  binding: forbidden
adjudicated:
  members: required, length>=1
  order: forbidden
  binding: required
```

Corpus support: A8, A9, A14

Notes:

- A14 pins down the adjudicated escape hatch at both claim and block level.
- For block adjudication, the binding receives synthetic `EvalNode`s with evaluator-local block truth and `support = inapplicable`.


## TransportNode

Status: **settled**

Canonical shape:

```yaml
node: Transport
mode:
- metadata_only
- preserve
- degrade
- remap_recompute
claimMap: string
truthPolicy: string
preconditions:
- string
dstEvaluators:
- string
dstResolutionPolicy: string
```

Validation rules:

```yaml
metadata_only:
  claimMap: forbidden
  truthPolicy: forbidden
  dstEvaluators: forbidden
  dstResolutionPolicy: forbidden
preserve:
  claimMap: forbidden
  truthPolicy: optional
  preconditions: optional
  dstEvaluators: forbidden
  dstResolutionPolicy: forbidden
degrade:
  claimMap: forbidden
  truthPolicy: optional
  preconditions: optional
  dstEvaluators: forbidden
  dstResolutionPolicy: forbidden
remap_recompute:
  claimMap: required
  truthPolicy: forbidden
  preconditions: optional
  dstEvaluators: optional
  dstResolutionPolicy: optional
```

Corpus support: A7, A10, B1

Notes:

- `truthPolicy` is reserved for `preserve` and `degrade`, where truth carryover/degradation is being customized.
- `remap_recompute` uses `claimMap` and destination evaluator configuration instead.


## AdequacyAssessmentNode.score

Status: **settled**

Canonical shape:

```yaml
node: AdequacyAssessment
id: string
task: string
producer: string
score: number | 'N' | omitted
threshold: number
method: string
basis:
- string
confidence: number
failureModes:
- string
```

Validation rules:

```yaml
score_present: treated as an attested output of method
score_omitted: allowed; method must be executable and compute the score
score_and_method_disagree: assessment -> B[method_conflict]
unresolved_method: assessment -> N[missing_binding]
```

Corpus support: A12, B1, B2

Notes:

- A12 now exercises both the attested-score path and the method-computed-without-score path.
- A numeric score never bypasses method resolvability; unresolved methods still yield `N[missing_binding]`.


## ClaimResult / BlockResult per_evaluator maps

Status: **settled**

Canonical shape:

```yaml
ClaimResult:
  claimId: string
  per_evaluator:
    EvaluatorId: EvalNode
  aggregate: EvalNode
  license: LicenseResult
BlockResult:
  blockId: string
  stratum:
  - local
  - systemic
  - meta
  per_evaluator:
    EvaluatorId: T|F|B|N
  aggregate: T|F|B|N
  claimIds:
  - string
```

Validation rules:

```yaml
evaluable_claims: per_evaluator and aggregate required
note_claims: per_evaluator and aggregate omitted
keys: must match effective evaluator panel after any transport override
```

Corpus support: A8, A9, A14, B1, B2

Notes:

- `per_evaluator` is required for evaluable claims and blocks.
- `aggregate` is required for evaluable claims and blocks.
- `NoteExpr` claims remain non-evaluable and omit these maps.


## Immediate schema implications

- The eventual JSON Schema should treat `ResolutionPolicyNode` and `TransportNode` as discriminated unions with conditional validation.

- `AdequacyAssessmentNode.score` should remain optional.

- `ClaimResult` and `BlockResult` should expose `per_evaluator` maps explicitly rather than burying panel results in provenance.

- The corpus, not the prose alone, should remain the arbiter of which fields are conditionally required.
