# ADR-003: Conformance-First Workflow

## Status

Accepted

## Context

The Limnalis v0.2.2 spec ships with a vendored fixture corpus containing 16 test cases (A1-A14, B1-B2). Each case defines input (surface source and/or canonical AST) and expected output (sessions, step results, block results, claim results, diagnostics, baseline states, adequacy expectations).

The implementation needs a development methodology that ensures correctness against the spec and catches regressions as new features are added.

## Decision

The fixture corpus is the conformance authority (invariant FIXTURE-001). Development follows a conformance-first workflow:

1. **Fixture corpus expected outputs are the ground truth.** When the implementation disagrees with a fixture expectation, the implementation is wrong unless a formal deviation is filed.

2. **The conformance harness runs all 16 cases end-to-end.** Each case goes through the full pipeline: parse (if source available), normalize, evaluate, then compare results field-by-field against expectations.

3. **Comparison is structural.** Sessions, steps, blocks, claims, diagnostics, baseline states, and adequacy expectations are compared with field-level granularity. Diagnostic comparison checks severity, code, and subject.

4. **Deviations are explicit.** If a case cannot pass due to a known limitation, it must be recorded in an allowlist with a case ID, reason, and severity. The `--allowlist` CLI flag and `--strict` mode control how deviations affect the exit code.

5. **All 16 cases must PASS for an RC release.** The conformance report (`limnalis conformance report`) is the release gate.

This workflow drove several design decisions during implementation, including relocating the `BaselineNode` mode validation from the Pydantic model layer to the runtime (because the corpus expected A4 to normalize successfully and produce a runtime diagnostic, not fail at model construction).

## Consequences

**Positive:**
- High confidence that the implementation matches the spec across all documented scenarios
- Regressions are caught immediately by the conformance harness
- The allowlist mechanism provides a structured way to track known limitations without blocking development
- Fixture-driven development naturally exercises the full pipeline end-to-end

**Negative:**
- Development velocity is constrained by the corpus: features not exercised by fixtures may have less coverage
- Corpus updates from upstream require re-running and potentially adjusting the implementation
- The conformance harness itself must be carefully maintained to avoid false passes

**Neutral:**
- The corpus currently contains 16 cases; future spec versions may add more
