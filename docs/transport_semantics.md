# Transport Semantics Guide

## Overview

Limnalis transport moves claims across frames via bridges. Milestone 6B extends the basic single-bridge execution into a richer cross-frame reasoning engine with chain composition, configurable degradation, claim-map validation, transport traces, and destination completion policies.

## Core Concepts

### Transport Modes

| Mode | Behavior |
|---|---|
| `metadata_only` | Transport header metadata only; no truth/support |
| `preserve` | Truth and support transported unchanged |
| `degrade` | Support reduced; truth unchanged |
| `remap_recompute` | Claims remapped to destination frame and recomputed |

### Bridge-Chain Composition

A `TransportPlan` defines an ordered sequence of hops through intermediate frames:

```
claim → bridge_1 → intermediate_frame → bridge_2 → destination_frame
```

Each hop preserves per-hop provenance (loss, gain, risk, status). Two failure modes are supported:

- **fail_fast**: Stop on first hop failure; return partial chain result
- **best_effort**: Continue through failures; record all hop outcomes

### Degradation Policies

Override the default degradation behavior via `DegradationPolicyNode`:

- `kind="default"`: Use existing built-in degradation
- `kind="custom"`: Delegate to a binding in services
- `preserve_fields`: List of fields to keep unchanged during degradation
- `max_loss`: Maximum acceptable confidence loss; exceeding this blocks the transport

### Claim-Map Validation

For `remap_recompute` mode, claim-map outputs are validated against:
- Non-empty result requirement
- Destination evaluator compatibility (if `dstEvaluators` specified)
- Produces `transport_mapping_missing` or `transport_mapping_invalid` diagnostics on failure

### Transport Trace

A `TransportTrace` provides a rich inspection record:
- Per-hop details (bridge_id, frames, status, loss, gain, risk)
- Precondition outcomes (pass/fail per precondition)
- Mapping steps applied
- Accumulated total loss and gain

### Destination Completion

After transport, a `DestinationCompletionPolicy` can fill omitted destination facets:

| Strategy | Behavior |
|---|---|
| `none` | No completion |
| `infer_defaults` | Fill from policy.defaults dict |
| `require_explicit` | Error if any facets missing |
| `binding` | Delegate to a service binding |

## Public API

```python
from limnalis.api.transport import (
    execute_transport_chain,
    execute_transport_with_degradation_policy,
    validate_claim_map_result,
    apply_destination_completion_policy,
    TransportHop, TransportPlan,
    DegradationPolicyNode, DestinationCompletionPolicy,
    TransportTrace, TransportChainResult,
)
```

## Normative vs Optional

- The existing `execute_transport` (Phase 13) remains the normative transport primitive
- Chain composition, degradation policies, and destination completion are optional extensions
- Transport traces are additive metadata attached to `TransportResult.metadata`
