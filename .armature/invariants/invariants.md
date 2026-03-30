# Limnalis Invariants

This document is the human-readable companion to `.armature/invariants/registry.yaml`. It provides prose descriptions of every hard constraint in the system, grouped by category.

**This file is the canonical reference in degraded mode** (when no agentic tooling is active). For machine-readable enforcement data, see the registry.

---

## How to Read This Document

Each invariant has:
- **ID** — Unique identifier matching the registry (`{CATEGORY}-{NNN}`)
- **Severity** — critical / high / standard
- **Rule** — The invariant stated as an absolute constraint
- **Rationale** — Why this invariant exists
- **Enforcement** — How compliance is verified

---

## Schema Governance

**SCHEMA-001 — AST Schema Validation Required** (critical)
Rule: Every normalized AST must validate against the vendored `limnalis_ast_schema` before acceptance.
Rationale: Schema validation is the final correctness gate. An AST that passes normalization but fails schema validation indicates a model/schema drift.
Enforcement: `schema.py` validate calls, `test_schema_validation.py`, CI.

**SCHEMA-002 — Schema Version Pinning** (critical)
Rule: Vendored schemas in `schemas/` must be version-pinned. Schema filename must include the version string (e.g., `limnalis_ast_schema_v0.2.2.json`).
Rationale: Version-pinned schemas prevent silent drift between the models and the validation surface.
Enforcement: `schema.py` resource loading, `test_packaging_resources.py`.

**SCHEMA-003 — Schema Change Is Normative** (critical)
Rule: Any change to a vendored JSON Schema requires a version bump in `pyproject.toml` and updated filenames in `schemas/`.
Rationale: Silent schema modification breaks downstream consumers and fixture corpus validity.
Enforcement: Review process.

**SCHEMA-004 — Fixture Corpus Schema Compliance** (high)
Rule: The fixture corpus must validate against `limnalis_fixture_corpus_schema`. Fixtures that fail schema validation are not valid test inputs.
Rationale: Invalid fixtures produce misleading test results.
Enforcement: `test_schema_validation.py`, CI.

---

## Grammar & Parser

**PARSER-001 — Grammar Permissiveness** (critical)
Rule: The Lark grammar in `grammar/limnalis.lark` must accept all valid Limnalis surface syntax. The parser is permissive; the normalizer enforces constraints.
Rationale: Rejecting valid syntax at the parser level prevents the normalizer from producing diagnostics about structural issues.
Enforcement: `test_parser.py`, fixture corpus parse pass.

**PARSER-002 — Grammar File Authority** (high)
Rule: `grammar/limnalis.lark` is the single source of truth for surface syntax. No inline grammar definitions.
Rationale: Duplicate grammar definitions drift. A single file is auditable and testable.
Enforcement: `parser.py` loads from `grammar/limnalis.lark`, `test_packaging_resources.py`.

**PARSER-003 — Parse Tree Stability** (high)
Rule: Grammar changes must not silently alter the parse tree structure for existing valid inputs. Structural changes require normalizer updates and fixture corpus review.
Rationale: The normalizer depends on specific parse tree node names and structure. Silent grammar changes break normalization.
Enforcement: `test_parser.py`, `test_normalizer.py`, review process.

---

## AST Models

**MODEL-001 — Pydantic Model Authority** (critical)
Rule: All AST node types must be Pydantic BaseModel subclasses inheriting from `LimnalisModel`. No raw dicts or ad-hoc classes for AST nodes.
Rationale: Pydantic models provide runtime validation, JSON serialization, and schema generation. Bypassing them breaks the validation pipeline.
Enforcement: `models/base.py`, `models/ast.py`, `test_ast_models.py`.

**MODEL-002 — Extra Fields Forbidden** (critical)
Rule: All AST models must use `extra="forbid"` in their Pydantic config. Unknown fields must cause validation errors, not silent acceptance.
Rationale: Silent acceptance of unknown fields masks schema drift and normalization bugs.
Enforcement: `models/base.py` `LimnalisModel` config, `test_ast_models.py`.

**MODEL-003 — Model-Schema Consistency** (critical)
Rule: Pydantic model definitions in `models/ast.py` must remain consistent with the vendored JSON Schema in `schemas/`. A model that produces JSON the schema rejects (or vice versa) is a defect.
Rationale: Model and schema are two representations of the same contract. Divergence breaks the pipeline.
Enforcement: `test_schema_validation.py`, CI.

---

## Normalization

**NORM-001 — Normalization Determinism** (critical)
Rule: The normalizer must be deterministic — identical parse trees must produce identical canonical AST output across runs.
Rationale: Non-deterministic normalization makes fixture-based testing impossible and breaks conformance.
Enforcement: `test_normalizer.py`, fixture corpus round-trip.

**NORM-002 — Diagnostic Completeness** (high)
Rule: Every non-trivial normalization decision (defaults applied, values canonicalized, elements omitted) must produce a structured diagnostic.
Rationale: Silent normalization hides intent. Diagnostics make the normalizer's decisions auditable.
Enforcement: `normalizer.py` diagnostic emission, `test_normalizer.py`.

**NORM-003 — Canonical Output Only** (critical)
Rule: The normalizer must produce canonical AST output. No optional formatting, no alternate representations. One input, one output.
Rationale: Canonical output is required for fixture comparison and cross-implementation conformance.
Enforcement: `test_normalizer.py`, fixture expected output comparison.

---

## Fixture Corpus

**FIXTURE-001 — Corpus Authority** (critical)
Rule: Fixture corpus expected outputs are the conformance authority. The normalizer must match them exactly.
Rationale: Expected outputs define correctness. Implementation must conform to fixtures, not the other way around.
Enforcement: `test_normalizer.py` fixture-driven tests, CI.

**FIXTURE-002 — Corpus Version Alignment** (high)
Rule: Fixture corpus version must match the schema version and the project version. Version misalignment is a release-blocking defect.
Rationale: Misaligned versions produce false test results.
Enforcement: `test_packaging_resources.py`, review process.

**FIXTURE-003 — JSON Mirror Equivalence** (high)
Rule: JSON fixture files must be equivalent representations of their YAML counterparts. Format drift is a defect.
Rationale: Both formats must be usable interchangeably for testing.
Enforcement: `test_loader.py`, review process.

---

## Runtime Execution

**RUNTIME-001 — Phase Ordering** (high)
Rule: The step runner must execute all 13 phases in strict ascending order (1-13). Phase ordering must not be altered without a spec change.
Rationale: The evaluation model depends on phase ordering — evidence views must exist before claim classification, classification before expression evaluation, etc. Out-of-order execution produces incorrect results.
Enforcement: `test_runtime_runner.py` phase trace assertions.

**RUNTIME-002 — Primitive Uniform Shape** (high)
Rule: All primitive operations must follow the uniform shape: `op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)` where practical.
Rationale: Uniform shape enables injectable primitives, consistent tracing, and predictable error handling. Deviations create special cases in the runner.
Enforcement: `primitives.py` Protocol definitions, `test_runtime_primitives.py`.

**RUNTIME-003 — NoteExpr Bypass** (high)
Rule: Non-evaluable NoteExpr claims must bypass eval_expr and support synthesis phases. The runner must not attempt to evaluate them.
Rationale: NoteExpr claims are annotations, not truth-bearing claims. Evaluating them wastes resources and produces meaningless results.
Enforcement: `test_runtime_runner.py` NoteExpr bypass tests, `test_runtime_primitives.py` classify_claim tests.

**RUNTIME-004 — Injectable Primitives** (standard)
Rule: PrimitiveSet must accept injected implementations for all 13 primitives. Stubbed primitives must raise NotImplementedError, not return silently.
Rationale: Silent stubs mask missing implementations. NotImplementedError makes the gap visible in diagnostics and traces.
Enforcement: `test_runtime_runner.py` custom injection tests.
