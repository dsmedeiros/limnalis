# ADR-001: Pydantic BaseModel for AST Nodes

## Status

Accepted

## Context

The Limnalis reference implementation needs a runtime representation for AST nodes that supports validation, serialization, and JSON Schema generation. The v0.2.2 spec defines a canonical AST schema, and the implementation must produce AST payloads that validate against it.

Options considered:
- Plain Python dataclasses with manual validation
- Pydantic BaseModel with strict configuration
- attrs with cattrs for serialization

Key requirements:
- All AST payloads must validate against the vendored JSON Schema (SCHEMA-001)
- Serialization to JSON must be stable and deterministic (NORM-001)
- Unknown fields must be rejected to catch schema drift early (MODEL-002)
- The model layer should be able to emit its own JSON Schema for cross-checking

## Decision

All AST nodes inherit from `LimnalisModel`, a Pydantic `BaseModel` subclass configured with `extra='forbid'`. This base class also provides `to_schema_data()` for JSON-schema-friendly serialization that omits `None` optional fields.

The `extra='forbid'` setting means that any field not declared in the model class will raise a `ValidationError` at construction time. This catches mismatches between the implementation and the spec schema early, during normalization rather than at schema validation time.

## Consequences

**Positive:**
- Runtime validation is automatic on model construction; malformed AST nodes fail fast
- `model_dump(mode="json", by_alias=True)` produces canonical JSON payloads ready for schema validation
- `model_json_schema()` enables cross-checking between the Pydantic models and the vendored spec schema
- `extra='forbid'` prevents silent data loss from typos or schema drift

**Negative:**
- Pydantic v2 is a required dependency (adds to install footprint)
- `extra='forbid'` means any upstream schema addition requires a corresponding model change before data can round-trip
- Model validators that enforce semantic constraints (e.g., baseline mode checks) may need relocation to runtime when the conformance corpus expects different behavior (see ADR for BaselineNode validation relocation in milestone 3C notes)

**Neutral:**
- All AST models must use `extra='forbid'` (invariant MODEL-002); this is enforced by test
