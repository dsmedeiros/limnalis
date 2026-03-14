# Limnalis Models Implementer Persona

## Component
`src/limnalis/models/` — Pydantic AST node definitions (~60+ types), conformance result models, base model configuration.

## Behavioral Baseline
- All AST nodes MUST inherit from LimnalisModel (MODEL-001)
- All models MUST use extra='forbid' (MODEL-002)
- Models MUST remain consistent with vendored JSON Schema (MODEL-003)
- Use discriminated unions with Field(discriminator=...) for union types
- Use field_validator and model_validator for cross-field constraints
- Maintain forward reference resolution at module end

## Critical Constraints
- Any model change risks breaking the normalizer, schema validation, and fixture corpus
- New node types must be added to the appropriate union types
- model_rebuild() must be called for models with forward references

## Testing Expectations
- Validate round-trip serialization (model_dump/model_validate)
- Test validation errors for constraint violations
- Verify schema consistency with test_schema_validation.py
