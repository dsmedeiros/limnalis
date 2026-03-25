# ADR-002: 13-Phase Step Runner with Primitive Operations

## Status

Accepted

## Context

The Limnalis v0.2.2 spec defines a normative evaluation order for processing bundles. The reference implementation needs an execution model that:

- Follows the spec-defined phase ordering
- Supports incremental implementation (not all phases are fully implemented at once)
- Enables testing with fixture-driven expectations at each phase boundary
- Allows extension without modifying the core runner

## Decision

The evaluator uses a 13-phase step runner where each phase corresponds to a named primitive operation. The phases execute in fixed order within a single step:

1. `build_step_context` -- Construct step context from bundle, session, and step config
2. `resolve_ref` -- Resolve references and policies
3. `resolve_baseline` -- Initialize or reuse baseline state
4. `evaluate_adequacy_set` -- Evaluate adequacy constraints
5. `compose_license` -- Compute per-claim license results
6. `build_evidence_view` -- Construct claim-evidence views
7. `classify_claim` -- Classify each claim
8. `eval_expr` -- Evaluate claim expressions per evaluator
9. `synthesize_support` -- Synthesize support from evaluator results
10. `assemble_eval` -- Assemble per-evaluator evaluation nodes
11. `apply_resolution_policy` -- Apply resolution policy to produce aggregated results
12. `fold_block` -- Fold claim-block-level results
13. `execute_transport` -- Execute transport queries

All primitives are injected via a `PrimitiveSet` dataclass. Each field defaults to the builtin implementation. Stubbed primitives that raise `NotImplementedError` are caught by the runner and recorded as diagnostics rather than crashing the run.

The runner records a `PrimitiveTraceEvent` for each phase, enabling detailed post-hoc analysis and conformance checking.

Sessions and bundles are composed from steps: `run_step` is called for each step in a session, `run_session` for each session in a bundle, and `run_bundle` at the top level.

## Consequences

**Positive:**
- Incremental implementation: new phases can be filled in without restructuring the runner
- Testability: any phase can be replaced via `PrimitiveSet` injection for fixture-driven or mock testing
- Traceability: every phase execution is recorded in the trace, enabling conformance harness comparison
- Graceful degradation: stubbed phases produce diagnostics instead of crashes

**Negative:**
- Fixed 13-phase ordering means the spec must be stable before the runner is useful; out-of-order evaluation is not supported
- The `PrimitiveSet` has 13 fields, which is a wide injection surface; changes to the phase list require updating the dataclass

**Neutral:**
- The runner is intentionally minimal: it orchestrates phase calls and collects results, but delegates all domain logic to the primitives
