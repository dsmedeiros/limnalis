# Implementation notes

## Why Pydantic over dataclasses here?

The canonical AST is now both:

- a runtime contract for the parser / normalizer boundary, and
- a serialization contract for schema validation and future evaluator inputs.

Plain dataclasses are fine for passive structure, but Pydantic gives you three things immediately:

1. runtime validation at construction time,
2. stable JSON serialization / deserialization,
3. schema emission from the runtime model layer.

That is the right trade-off at the current Limnalis stage.

## Scope of this scaffold

This repo now implements the authored surface parser at a permissive Milestone 1 level, a
Milestone 2 normalizer for the authored subset exercised by the vendored fixture corpus, and a
Milestone 3 schema-validation pass over normalized AST payloads.

The validated source pipeline now covers frame blocks and shorthand frame patterns, inline facet
patterns, evaluator panels, explicit or synthetic single resolution policies, baselines, evidence,
evidence relations, anchors, joint adequacies, bridges, transport blocks, and `local` /
`systemic` / `meta` claim blocks with claim metadata and authored expression forms for
`judged_by`, `note`, `declare ... within ...`, causal `=>[...]`, and `EMRG ... --> ...`.

A few authored forms still require compatibility diagnostics because the canonical v0.2.2 bundle
schema is narrower than the authored surface. Extra `resolution_policy` blocks are omitted beyond
the single bundle-level slot, authored evaluator `kind audit` is canonicalized to `process`, and
missing adequacy / assessment ids are synthesized during normalization. Semantically invalid
surface input still fails fast; fixture case `A4` remains the concrete moving-baseline example.
Schema validation failures continue to raise a structured `SchemaValidationError` with path-aware
violations.
