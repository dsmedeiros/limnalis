---
scope: src/limnalis/runtime
governs: "Runtime execution layer: abstract machine models, primitive operations, step runner"
inherits: src/limnalis/agents.md
adrs: []
invariants: [RUNTIME-001, RUNTIME-002, RUNTIME-003, RUNTIME-004]
enforced-by:
  - tests/test_runtime_primitives.py
  - tests/test_runtime_runner.py
persona: implementer
authority: [read, write, test]
restricted: [cross-cutting-changes, model-changes]
---

# Limnalis Runtime

## Overview
Runtime execution scaffolding implementing the Limnalis abstract machine. Contains runtime models (StepContext, MachineState, EvalNode), Protocol definitions for 13 primitive operations, built-in primitive implementations, and a 13-phase step runner.

## Behavioral Directives
- Runtime models use standard Pydantic BaseModel (not LimnalisModel — these are not AST nodes)
- Primitive implementations follow uniform shape: op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)
- Stubbed primitives must raise NotImplementedError with descriptive messages
- Runner must record PrimitiveTraceEvent for each of the 13 phases
- Non-evaluable NoteExpr claims must bypass eval_expr and support synthesis
- PrimitiveSet must accept injected implementations for all 13 primitives

## Change Expectations
- Depends on src/limnalis/models/ for AST node types — do not introduce circular imports
- Phase ordering (1-13) must be preserved unless spec changes
- Existing primitive tests and runner tests must continue to pass
