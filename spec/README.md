# Limnalis Specification

This directory contains the upstream specification documents that the reference implementation is based on.

| Document | Description |
|----------|-------------|
| [Limnalis-v0.2.1.pdf](Limnalis-v0.2.1.pdf) | Consolidated specification (v0.2.1) covering the four-layer architecture, canonical kernel, expression forms, four-valued logic, evaluation semantics, transport, adequacy, the 13-phase pipeline, and conformance rules. |
| [Limnalis_conformance_matrix_v0.2.1.xlsx](Limnalis_conformance_matrix_v0.2.1.xlsx) | Conformance matrix with golden-bundle cases (Track A: core semantics A1-A13, Track B: domain bundles B1-B2), expected AST/evaluation/diagnostic outputs, fixture bindings, and feature coverage grid. |

## Version note

These documents are v0.2.1. The reference implementation targets v0.2.2, which includes incremental patches on top of this spec. Deviations and extensions are documented in [docs/compatibility_and_deviations.md](../docs/compatibility_and_deviations.md).
