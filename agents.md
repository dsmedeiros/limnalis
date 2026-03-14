---
scope: /
governs: "Repository-wide coding standards and cross-cutting invariants"
inherits: null
adrs: []
invariants: [SCHEMA-001, SCHEMA-002, SCHEMA-003, SCHEMA-004, MODEL-001, MODEL-002, MODEL-003, NORM-001, NORM-002, NORM-003, FIXTURE-001, FIXTURE-002, FIXTURE-003, PARSER-001, PARSER-002, PARSER-003]
enforced-by:
  - .github/workflows/ci.yml
  - tests/
persona: orchestrator
authority: [read, delegate, review, commit]
restricted: [write-application-code]
---

# Global Repository Directives

## Coding Standards
- Python 3.11+ with type annotations
- Pydantic 2.x for all data models
- Use `from __future__ import annotations` in all modules
- Follow existing import patterns (relative imports within package)
- No print statements in library code; use structured diagnostics

## Testing
- All new functionality must have corresponding pytest tests
- Tests must pass before any commit is accepted
- Fixture corpus is the conformance authority (FIXTURE-001)
- Use snapshot testing for regression protection

## Commit Protocol
- Per-task commits after reviewer PASS
- Commit message format: `task-{id}: {title}\n\nScope: {scope}\nInvariants: {ids}\nReviewer: PASS`
- Do not batch changes across tasks

## Documentation
- Do not create documentation files unless explicitly requested
- Inline comments only where logic is non-obvious
- ADRs for architectural decisions (docs/adr/)

## Dependencies
- No new runtime dependencies without explicit approval
- Dev dependencies: pytest, ruff, mypy
