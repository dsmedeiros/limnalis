---
scope: src/limnalis/interop
governs: "Interoperability layer: envelopes, exchange format, export/import, projections"
inherits: src/limnalis/agents.md
adrs: []
invariants: [SCHEMA-001, MODEL-001, MODEL-002]
enforced-by: []
persona: implementer
authority: [read, write, test]
restricted: [cross-cutting-changes, schema-migration]
---

# Limnalis Interop Subpackage

## Overview
Interoperability layer providing typed envelopes for wrapping AST, evaluation result,
and conformance report artifacts with version and provenance metadata. Also defines the
exchange package manifest and projection result types for cross-tool data exchange.

## Behavioral Directives
- All models inherit from LimnalisModel (MODEL-001) and use extra='forbid' (MODEL-002)
- Envelope payloads (normalized_ast, evaluation_result, report) are opaque `dict[str, Any]`
  at the envelope level; schema validation of inner content is handled by the schema module
- Version constants (SPEC_VERSION, SCHEMA_VERSION) must stay synchronized with vendored
  schema filenames in `src/limnalis/schema.py`
- Envelopes are data containers only; serialization and I/O belong in separate modules

## Change Expectations
- Adding new envelope types requires corresponding schema support
- Version constant updates must be coordinated with schema vendoring
