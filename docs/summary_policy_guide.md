# Summary Policy Guide

## Overview

Summary policies produce non-normative aggregation views of evaluation results. They sit **beside** the normative fold semantics — they never alter `ClaimResult`, `BlockResult`, or `EvalNode` normative outputs.

See [ADR-005](adr/005-summary-policy-separation.md) for the design rationale.

## Built-in Policies

### passthrough_normative
Exposes existing canonical fold/aggregate results as a summary without transformation. Useful for uniform summary interfaces that want to include the normative result alongside alternative views.

### severity_max
Returns the worst truth value across scoped results using severity ordering: **F > B > N > T**. Useful for worst-case dashboards where any failure should dominate.

### majority_vote
Counts truth values and returns the most common one. Ties are broken by severity ordering (worst wins). Includes vote counts in the `detail` field. Useful for multi-evaluator or multi-claim aggregation where democratic consensus is desired.

## Summary Scopes

| Scope | Aggregates over |
|---|---|
| `claim_collection` | Specified claim IDs |
| `block` | All evaluable claims in a block |
| `bundle` | All blocks in a bundle |
| `session` | All blocks across sessions |

## Usage

```python
from limnalis.api.summary import (
    SummaryRequest, SummaryResult,
    run_summaries, get_builtin_summary_policies,
)

# After running evaluation...
policies = get_builtin_summary_policies()
requests = [
    SummaryRequest(policy_id="severity_max", scope="bundle"),
    SummaryRequest(policy_id="majority_vote", scope="bundle"),
]
results = run_summaries(requests, eval_results, services={}, policies=policies)
```

## CLI

```bash
# Summarize with default passthrough policy
python -m limnalis summarize examples/minimal_bundle.lmn

# Use severity_max policy
python -m limnalis summarize examples/minimal_bundle.lmn --policy severity_max --json
```

## Writing Custom Policies

Implement the `SummaryPolicyProtocol`:

```python
class MySummaryPolicy:
    def summarize(self, request, eval_results, services):
        # Your aggregation logic here
        return SummaryResult(
            policy_id="my_policy",
            scope=request.scope,
            normative=False,
            summary_truth="T",
            provenance=["custom policy"],
        )
```

## Key Invariant

All `SummaryResult` instances must have `normative=False` unless the policy explicitly and intentionally sets `normative=True`. The built-in policies never produce normative summaries.
