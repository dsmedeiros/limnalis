# Limnalis Specification

This directory contains the upstream specification documents that the reference implementation is based on.

| Document | Description |
|----------|-------------|
| [Limnalis-v0.2.2.md](Limnalis-v0.2.2.md) | Canonical consolidated specification (v0.2.2, with reader's guide) — the current normative reference, superseding the v0.2.1 edition. Defines the execution model (13 primitive operations, session/step semantics, machine state), the normative phase order, the reference evaluator, conformance corpus cases A1-A14 and B1-B2, and the schema package description. |
| [Limnalis-v0.2.1.pdf](Limnalis-v0.2.1.pdf) | Prior spec edition, retained for history. Consolidated specification (v0.2.1) covering the four-layer architecture, canonical kernel, expression forms, four-valued logic, evaluation semantics, transport, adequacy, the 13-phase pipeline, and conformance rules. |
| [Limnalis_conformance_matrix_v0.2.1.xlsx](Limnalis_conformance_matrix_v0.2.1.xlsx) | Prior spec edition, retained for history. Conformance matrix with golden-bundle cases (Track A: core semantics A1-A13, Track B: domain bundles B1-B2), expected AST/evaluation/diagnostic outputs, fixture bindings, and feature coverage grid. |

## Version note

The current normative reference is v0.2.2 ([Limnalis-v0.2.2.md](Limnalis-v0.2.2.md)); the v0.2.1 documents are the prior spec edition, retained for history. Note that the full expression grammar (Appendix A.8) is still defined by reference to the v0.2 specification, which is not vendored in this repository. Deviations and extensions are documented in [docs/compatibility_and_deviations.md](../docs/compatibility_and_deviations.md).
