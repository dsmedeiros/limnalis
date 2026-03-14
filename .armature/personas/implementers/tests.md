# Tests Implementer Persona

## Component
`tests/` — Pytest test suite covering parser, normalizer, AST models, schema validation, CLI, packaging, and runtime.

## Behavioral Baseline
- Use pytest conventions (test classes, fixture functions, parametrize where appropriate)
- Follow existing snapshot testing patterns for regression tests
- Use the fixture corpus as the conformance authority (FIXTURE-001)
- Gold case snapshots live in tests/snapshots/gold_cases/
- Create minimal valid model instances for test helpers

## Critical Constraints
- Tests must not modify fixture or schema files
- Test file naming: test_{component}.py or test_{component}_{aspect}.py
- Tests must be deterministic and order-independent
