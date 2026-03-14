---
scope: src/limnalis
governs: "Core package: parser, normalizer, loader, schema validation, CLI, diagnostics"
inherits: agents.md
adrs: []
invariants: [PARSER-001, PARSER-002, PARSER-003, NORM-001, NORM-002, NORM-003, SCHEMA-001]
enforced-by:
  - tests/test_parser.py
  - tests/test_normalizer.py
  - tests/test_cli_smoke.py
  - tests/test_loader.py
  - tests/test_schema_validation.py
persona: implementer
authority: [read, write, test]
restricted: [cross-cutting-changes, schema-migration, model-changes]
---

# Limnalis Core Package

## Overview
Core package containing the parse-normalize-validate pipeline. Parser uses Lark grammar for permissive surface syntax parsing. Normalizer converts raw parse trees to canonical AST. Loader provides high-level file operations. Schema module validates against vendored JSON Schemas.

## Behavioral Directives
- Parser must remain permissive; normalizer enforces constraints (PARSER-001)
- Grammar must be the single source of truth — no inline grammar definitions (PARSER-002)
- Normalizer must be deterministic (NORM-001)
- Every non-trivial normalization decision must produce a diagnostic (NORM-002)
- All outputs must validate against vendored schema (SCHEMA-001)

## Change Expectations
- Grammar changes must not alter parse trees for existing valid inputs (PARSER-003)
- Normalizer changes must maintain fixture corpus conformance (FIXTURE-001)
- CLI interface must remain backward-compatible
