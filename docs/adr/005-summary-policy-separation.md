# ADR-005: Summary Policy Separation from Normative Fold

**Status:** Accepted
**Date:** 2026-03-30
**Context:** Milestone 6B — Summary Policy Framework

## Decision

Summary policies are implemented as a **separate post-evaluation layer** that sits beside, not inside, the normative block folding semantics. Summaries never alter `ClaimResult`, `BlockResult`, or `EvalNode` normative outputs.

## Context

Limnalis produces normative evaluation results through a well-defined 13-phase pipeline culminating in `fold_block` (Phase 12) and `apply_resolution_policy` (Phase 11). Users and downstream systems often want alternative views of the same evaluation data — for example, a "worst-case" summary, a majority-vote dashboard, or a passthrough of canonical results in a simplified format.

The risk of embedding summaries inside the normative pipeline is that summary logic could silently alter or replace canonical fold results, violating NORM-001 (deterministic normalization) and FIXTURE-001 (corpus authority).

## Rationale

- **Separation of concerns:** Normative semantics are authoritative; summaries are informational.
- **Additive safety:** New summary policies cannot break existing evaluation behavior.
- **Plugin-friendly:** Third parties can implement `SummaryPolicyProtocol` without touching the core pipeline.
- **Non-normative by default:** All `SummaryResult` instances carry `normative=False` unless explicitly overridden.

## Consequences

- Summary execution happens **after** the normal evaluation pipeline completes.
- `run_summaries()` reads evaluation results without mutating them.
- Built-in policies (`passthrough_normative`, `severity_max`, `majority_vote`) are reference implementations.
- CLI `summarize` command runs the full eval pipeline first, then applies the requested summary policy.
- Downstream consumers must check `SummaryResult.normative` to distinguish authoritative from informational results.

## Alternatives Considered

1. **Embed summaries in fold_block:** Rejected — violates separation of concerns and risks normative contamination.
2. **Add a 14th phase for summaries:** Rejected — summaries are not part of the normative pipeline; adding a phase would falsely elevate their status.
