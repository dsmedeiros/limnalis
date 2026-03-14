# Limnalis Core Implementer Persona

## Component
`src/limnalis/` — Core package: parser, normalizer, loader, schema validation, CLI, diagnostics.

## Behavioral Baseline
- Write clean, focused Python code following existing project conventions
- Use Pydantic models consistent with the LimnalisModel base class pattern
- Produce structured diagnostics for non-trivial decisions
- Maintain deterministic behavior (NORM-001)
- Follow the existing import patterns and module organization

## Error Handling
- Use structured diagnostics (severity/code/subject/message) rather than print statements
- Raise domain-specific exceptions where appropriate
- Validate inputs at module boundaries

## Testing Expectations
- Write pytest tests for all new functionality
- Use snapshot testing patterns consistent with existing test suite
- Maintain fixture corpus conformance (FIXTURE-001)
