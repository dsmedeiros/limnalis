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

This repo does **not** yet implement the authored surface parser or the canonical normalizer.
It gives those stages a stable target.
