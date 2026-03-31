# ADR-006: Evidence Inference as Opt-In Extension

**Status:** Accepted
**Date:** 2026-03-30
**Context:** Milestone 6B — Evidence Inference Layer

## Decision

Evidence inference is implemented as an **opt-in extension** controlled by an `EvidenceInferencePolicyNode`. By default, only declared `EvidenceRelationNode` entries count. Inferred relations are always distinguishable from declared ones via the `declared=False` flag and explicit provenance.

## Context

Limnalis supports declared evidence relations (`corroborates`, `conflicts`, `depends_on`, `duplicate_of`) between evidence items. In many evaluation scenarios, additional relations can be logically inferred — for example, if A conflicts with B and B conflicts with C, then A may corroborate C (transitivity).

However, silently injecting inferred relations into the evidence view would violate the principle that evaluation results are traceable to declared inputs.

## Rationale

- **Opt-in safety:** No inferred relations appear unless an inference policy is explicitly provided.
- **Provenance transparency:** Every inferred relation carries `method`, `confidence`, and `provenance` fields explaining how it was derived.
- **Separation:** Inferred relations are returned as a separate list from `build_evidence_view_with_inference`, not mixed into `ClaimEvidenceView.relations` (which remains declared-only).
- **Combined views available:** `get_evidence_view_combined()` provides both perspectives in a single dict for consumers who want the full picture.

## Consequences

- Default behavior is unchanged — `build_evidence_view` (Phase 6) sees only declared relations.
- `build_evidence_view_with_inference` is an extended version that accepts an optional inference policy.
- The built-in `TransitivityInferencePolicy` provides a deterministic reference implementation.
- Third parties can implement `EvidenceInferencePolicyProtocol` for custom inference strategies.
- Support synthesis can consume either declared-only or declared+inferred views depending on configuration.

## Alternatives Considered

1. **Always infer:** Rejected — would change existing evaluation semantics silently.
2. **Merge inferred into ClaimEvidenceView.relations:** Rejected — makes it impossible to distinguish declared from inferred without checking every relation's provenance.
