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
Milestone 2 normalizer for the current core authored subset, and a Milestone 3 schema-validation
pass over normalized AST payloads.

The validated source pipeline covers frame blocks and shorthand frame patterns, evaluator panels,
explicit or synthetic single resolution policies, and `local` / `systemic` / `meta` claim blocks
containing atomic predicates, predicate calls, logical expressions, `judged_by`, and `note`.

Remaining authored constructs such as baselines, evidence, anchors, bridges, inline facet patterns,
and claim metadata are still intentionally unsupported and fail fast during normalization. Schema
validation failures now raise a structured `SchemaValidationError` with path-aware violations.
