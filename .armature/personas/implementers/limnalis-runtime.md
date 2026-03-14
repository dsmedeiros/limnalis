# Limnalis Runtime Implementer Persona

## Component
`src/limnalis/runtime/` — Runtime execution layer: abstract machine models, primitive operations, step runner.

## Behavioral Baseline
- Runtime models use standard Pydantic BaseModel (not LimnalisModel, since these are not AST nodes)
- Primitive implementations follow the uniform shape: op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)
- Stubbed primitives raise NotImplementedError with descriptive messages
- The runner must record PrimitiveTraceEvent for each phase
- Non-evaluable NoteExpr claims must bypass eval_expr and support synthesis

## Dependencies
- Depends on `src/limnalis/models/ast.py` for AST node types
- Depends on `src/limnalis/models/conformance.py` for TruthValue, SupportValue types
- Must not introduce circular imports back to core limnalis modules

## Testing Expectations
- Test all implemented primitives with focused unit tests
- Test phase ordering in the runner
- Use fake/stub implementations for unimplemented primitives in tests
- Verify NoteExpr bypass behavior
