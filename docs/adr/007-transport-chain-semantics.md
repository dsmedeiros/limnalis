# ADR-007: Transport Chain Semantics

**Status:** Accepted
**Date:** 2026-03-30
**Context:** Milestone 6B — Advanced Transport Engine

## Decision

Transport chains are modeled as a `TransportPlan` containing an ordered sequence of `TransportHop` entries, each referencing a `BridgeNode`. Chain execution is sequential with two failure modes: `fail_fast` (stop on first failure) and `best_effort` (continue, recording failures per hop).

## Context

The existing transport system executes a single bridge at a time via `execute_transport` (Phase 13). Real cross-frame reasoning often requires multi-hop transport — for example, transporting a claim from a physical measurement frame through a theoretical model frame to a policy compliance frame.

## Rationale

- **Explicit chaining:** A `TransportPlan` makes the hop sequence declarative and inspectable, rather than relying on ad hoc sequential calls.
- **Per-hop provenance:** Each hop records its own loss, gain, risk, and status, enabling failure localization.
- **Failure modes:** `fail_fast` is appropriate when any hop failure invalidates the chain; `best_effort` is appropriate for diagnostic or exploratory transport where partial results are useful.
- **Additive:** `execute_transport_chain` is a new helper function, not a replacement for `execute_transport`. The existing Phase 13 primitive is unchanged.

## Consequences

- `TransportChainResult` consolidates per-hop results with a `TransportTrace`.
- `TransportTrace` records hops, precondition outcomes, mapping steps, and accumulated loss/gain.
- Degradation policies can be applied per-hop via `execute_transport_with_degradation_policy`.
- Destination completion policies can be applied after the final hop.
- Claim-map validation (`validate_claim_map_result`) catches invalid mappings before they propagate through the chain.

## Design Details

### Chain execution flow:
```
for each hop in plan.hops:
  1. Look up bridge by bridge_id
  2. Execute transport for this hop
  3. Record hop result, loss, gain, risk
  4. If failure and fail_fast: stop, return partial chain result
  5. If success: feed destination aggregate as next hop's source
```

### Transport trace structure:
- `hops`: per-hop details (bridge_id, src/dst frames, status, loss, gain, risk)
- `precondition_outcomes`: which preconditions passed/failed
- `mapping_steps`: claim-map transformations applied
- `total_loss` / `total_gain`: accumulated across all hops

## Alternatives Considered

1. **Implicit chaining via frame graph traversal:** Rejected — too complex for the current scope, and explicit plans are more debuggable.
2. **Parallel hop execution:** Rejected — transport is inherently sequential (each hop depends on the previous hop's output).
