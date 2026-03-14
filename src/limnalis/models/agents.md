---
scope: src/limnalis/models
governs: "Pydantic AST node definitions, conformance result models, base model config"
inherits: src/limnalis/agents.md
adrs: []
invariants: [MODEL-001, MODEL-002, MODEL-003, SCHEMA-001]
enforced-by:
  - tests/test_ast_models.py
  - tests/test_schema_validation.py
persona: implementer
authority: [read, write, test]
restricted: [base-model-config-change, remove-existing-nodes]
---

# Limnalis Models

## Overview
Pydantic model definitions for the canonical AST (~60+ node types), conformance result types, and the LimnalisModel base class. These are the structural foundation of the entire pipeline.

## Behavioral Directives
- All AST node types must inherit from LimnalisModel (MODEL-001)
- All models must use extra='forbid' — unknown fields cause validation errors (MODEL-002)
- Models must remain consistent with vendored JSON Schema (MODEL-003)
- Use discriminated unions with Field(discriminator=...) for union types
- Use field_validator and model_validator for cross-field constraints
- Call model_rebuild() for models with forward references

## Change Expectations
- Changing any model risks breaking normalizer, schema validation, and fixture corpus
- New node types must be added to appropriate union types (ExprNode, TermNode, ArgNode)
- Forward reference resolution block at end of ast.py must be maintained
- base.py LimnalisModel config (extra='forbid', validate_assignment=True) must not be weakened
