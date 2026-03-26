# Limnalis v0.2.2 Reference Implementation

Limnalis is a Python reference implementation for parsing authored Limnalis surface syntax (`.lmn` files) into permissive raw parse trees, normalizing them into canonical Pydantic-validated AST nodes, and validating against vendored JSON Schemas. The runtime layer provides execution scaffolding with primitive operations and a phase-ordered step runner.

**Package version:** 0.2.2rc1 | **Spec version:** v0.2.2

## Quickstart

### Installation

```bash
# Standard install
pip install .

# Development install with test dependencies
pip install -e ".[dev,test]"
```

### Quick usage

Parse surface syntax into a raw parse tree:

```bash
limnalis parse examples/minimal_bundle.lmn
```

Normalize into canonical AST JSON:

```bash
limnalis normalize examples/minimal_bundle.lmn
```

Run the full evaluation pipeline:

```bash
limnalis evaluate examples/minimal_bundle.lmn
```

Run conformance against the fixture corpus:

```bash
limnalis conformance run --all
```

### Public API

```python
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)

result = normalize_surface_file("examples/minimal_bundle.lmn")
bundle = result.canonical_ast
sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
env = EvaluationEnvironment()
evaluation = run_bundle(bundle, sessions, env)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `parse` | Parse a `.lmn` file and print the raw parse tree |
| `normalize` | Normalize a `.lmn` file into canonical AST JSON |
| `validate-source` | Parse, normalize, and schema-validate a `.lmn` file |
| `validate-ast` | Validate a canonical AST JSON/YAML payload against the schema |
| `validate-fixtures` | Validate a fixture corpus JSON/YAML file |
| `evaluate` | Run the full evaluation pipeline and output JSON result |
| `print-schema` | Print a vendored JSON Schema (`ast`, `fixture_corpus`, `conformance_result`) |
| `conformance list` | List all available fixture cases |
| `conformance show` | Show details for a fixture case |
| `conformance run` | Run conformance cases and report pass/fail |
| `conformance report` | Generate a conformance report (JSON or Markdown) |
| `version` | Print version info as JSON |

Global flags: `--version`, `--json` (on applicable commands), `--strict`, `--allowlist` (on conformance commands).

## Design Principles

The AST layer is **Pydantic-first**: all AST nodes inherit from `LimnalisModel` (a strict `BaseModel` with `extra='forbid'`), providing runtime validation, stable JSON serialization via `model_dump`, and model-emitted JSON Schema via `model_json_schema`.

## Repo Layout

```text
limnalis/
  grammar/limnalis.lark          # Lark grammar for surface syntax
  src/limnalis/
    api/                          # Stable public API surface
    models/                       # Pydantic AST models
    runtime/                      # 13-phase step runner and builtins
    conformance/                  # Fixture-based conformance harness
    parser.py, normalizer.py, loader.py, schema.py, cli.py, diagnostics.py
  schemas/                        # Vendored JSON Schemas (v0.2.2)
  fixtures/                       # Vendored fixture corpus (v0.2.2)
  tests/                          # Unit, integration, property, and conformance tests
  docs/                           # Architecture, ADRs, and status documents
```

## Running Tests

```bash
python -m pytest tests/ -q
```

## Known Vendored-Schema Issue

The shipped `limnalis_ast_schema_v0.2.2.json` contains a `$ref` typo where some `time` fields point to `#/$defs/FixtureTimeSpec` instead of `TimeCtxNode`. The runtime loader in `limnalis.schema` includes an opt-in repair pass so schema validation works in practice.
