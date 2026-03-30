# Limnalis Architecture Overview

This document describes the high-level architecture of the Limnalis v0.2.2 reference implementation.

## Pipeline

The core data flow is a linear pipeline:

```
Surface Source (.lmn)
    |
    v
[Parser] -- Lark/Earley grammar --> Raw Parse Tree
    |
    v
[Normalizer] -- Tree-walking transforms --> Canonical AST (Pydantic BundleNode)
    |
    v
[Schema Validation] -- vendored JSON Schema --> Validated AST
    |
    v
[Evaluator] -- 13-phase step runner --> Evaluation Result
    |
    v
[Conformance Harness] -- fixture corpus comparison --> Pass/Fail per case
```

## Module Boundaries

### `limnalis.parser` (parser.py)

Wraps a Lark `Earley` parser with the grammar defined in `grammar/limnalis.lark`. Produces a permissive raw parse tree from authored surface syntax. No semantic interpretation occurs at this stage.

Key type: `LimnalisParser` with `parse_text()` and `parse_file()` methods.

### `limnalis.normalizer` (normalizer.py)

Walks the raw parse tree and produces a canonical `BundleNode` AST. Handles:

- Bundle metadata, frame resolution, evaluator panels
- Claim blocks (local, systemic, meta) with synthetic ID generation
- Claim expressions (predicates, logical operators, judged-by, causal, emergence, declarations)
- Evidence, evidence relations, anchors, baselines, bridges, transport, adequacy, assessment
- Resolution policy extraction and defaulting
- Compatibility diagnostics for authored forms that don't map 1:1 to the canonical schema

Output: `NormalizationResult` containing a `BundleNode` and a list of diagnostics.

### `limnalis.models` (models/)

All AST nodes are Pydantic models inheriting from `LimnalisModel`, which enforces `extra='forbid'` and provides `to_schema_data()` for JSON-schema-friendly serialization. The model hierarchy includes `BundleNode`, `FrameNode`, `EvaluatorNode`, `ClaimBlockNode`, `ClaimNode`, and all expression/term node types.

Conformance-specific models (`FixtureCase`, `ExpectedResult`) live in `models/conformance.py`.

### `limnalis.runtime` (runtime/)

The evaluation engine. The step runner (`runner.py`) executes the normative 13-phase evaluation order:

| Phase | Primitive | Purpose |
|-------|-----------|---------|
| 1 | `build_step_context` | Construct step context from bundle, session, and step config |
| 2 | `resolve_ref` | Resolve references and policies |
| 3 | `resolve_baseline` | Initialize or reuse baseline state |
| 4 | `evaluate_adequacy_set` | Evaluate adequacy constraints |
| 5 | `compose_license` | Compute per-claim license results |
| 6 | `build_evidence_view` | Construct claim-evidence views |
| 7 | `classify_claim` | Classify each claim |
| 8 | `eval_expr` | Evaluate claim expressions per evaluator |
| 9 | `synthesize_support` | Synthesize support from evaluator results |
| 10 | `assemble_eval` | Assemble per-evaluator evaluation nodes |
| 11 | `apply_resolution_policy` | Apply resolution policy to produce aggregated results |
| 12 | `fold_block` | Fold claim-block-level results |
| 13 | `execute_transport` | Execute transport queries |

All primitives are injectable via `PrimitiveSet` for testing and extension. Stubbed primitives raise `NotImplementedError`, which the runner catches and records as diagnostics.

Runtime models (`MachineState`, `StepContext`, `EvalNode`, `TruthCore`, etc.) are defined in `runtime/models.py`.

### `limnalis.conformance` (conformance/)

The fixture-based conformance harness. Loads the vendored fixture corpus, runs each case through the full pipeline (parse if source is available, normalize, evaluate), and compares results against expected outputs.

Key operations: `load_corpus`, `run_case`, `compare_case`.

Comparison checks sessions, step results, block results, claim results, diagnostics (severity, code, subject), baseline states, and adequacy expectations.

### `limnalis.schema` (schema.py)

Loads vendored JSON Schemas and validates AST payloads. Includes an opt-in repair pass for the known `$ref` typo in the shipped schema. Provides `collect_validation_errors()` for structured error reporting.

### `limnalis.cli` (cli.py)

The command-line interface built on `argparse`. Provides commands for all pipeline stages plus conformance harness operations. Supports `--json` output, `--strict` mode, `--allowlist` for known deviations, and consistent exit codes.

## Public API Surface

The stable public API is exposed through `limnalis.api.*`:

| Module | Exports |
|--------|---------|
| `limnalis.api.parser` | `LimnalisParser` |
| `limnalis.api.normalizer` | `Normalizer`, `NormalizationResult`, `NormalizationError`, `normalize_surface_file`, `normalize_surface_text` |
| `limnalis.api.evaluator` | `run_bundle`, `run_session`, `run_step`, `PrimitiveSet`, `BundleResult`, `SessionResult`, `StepResult`, `EvaluationResult` |
| `limnalis.api.conformance` | `load_corpus`, `load_corpus_from_default`, `run_case`, `compare_case`, `FixtureCase` |

Internal module paths (e.g., `limnalis.normalizer`, `limnalis.runtime.runner`) are implementation details and may change without notice.

## Extension Points

### Evaluator bindings (PrimitiveSet)

All 13 phase primitives can be replaced by injecting a custom `PrimitiveSet` into `run_step` / `run_session` / `run_bundle`. This enables fixture-driven testing, mock evaluation, and custom evaluation strategies.

### Criterion bindings

Claim expressions are evaluated via `eval_expr`, which dispatches on expression node type. New expression types can be supported by extending the expression evaluator.

### Adjudicated resolution

The runner accepts an optional `adjudicator` callable for adjudicated resolution policies. When the resolution policy is `adjudicated`, the runner delegates to this callable to determine the final evaluation result across evaluators.

### Transport handlers

Transport execution (`execute_transport`, phase 13) is currently stubbed. Implementations can inject custom transport handlers via `PrimitiveSet.execute_transport` to support different transport modes (metadata_only, preserve, etc.).
