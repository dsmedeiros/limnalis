---
scope: tests
governs: "Pytest test suite: parser, normalizer, AST models, schema validation, CLI, packaging, runtime"
inherits: agents.md
adrs: []
invariants: [FIXTURE-001, FIXTURE-002, FIXTURE-003]
enforced-by:
  - .github/workflows/ci.yml
persona: implementer
authority: [read, write, test]
restricted: [modify-fixtures, modify-schemas]
---

# Test Suite

## Overview
Pytest test suite providing regression, conformance, and smoke testing for the full Limnalis pipeline. Uses snapshot testing for normalizer output comparison and fixture corpus as conformance authority.

## Behavioral Directives
- Fixture corpus expected outputs are the conformance authority (FIXTURE-001)
- Tests must be deterministic and order-independent
- Use existing helper patterns (minimal model construction, snapshot comparison)
- Gold case snapshots live in tests/snapshots/gold_cases/
- Test file naming: test_{component}.py or test_{component}_{aspect}.py

## Change Expectations
- Do not modify fixture files or schema files from tests
- Snapshot files may be updated when normalizer behavior changes intentionally
- New test files must follow existing import and naming conventions
