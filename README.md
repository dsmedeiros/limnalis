# Limnalis Python scaffold (Pydantic-first)

This repo is the starter implementation scaffold for the **Limnalis v0.2.2** parser / normalizer
workstream.

The AST/runtime layer is intentionally **Pydantic-first** rather than plain dataclasses.
That gives you:

- runtime validation via `BaseModel` and `model_validate`,
- stable JSON serialization via `model_dump` / `model_dump_json`,
- and model-emitted JSON Schema via `model_json_schema`, which keeps the design schema-first and
  machine-readable. Pydantic v2 documentation also explicitly treats model validation,
  serialization, and JSON Schema generation as first-class features.

Current scope:

- [x] Canonical AST classes as **Pydantic models**
- [x] Vendored v0.2.2 schemas and fixture corpus
- [x] JSON/YAML loaders
- [x] JSON Schema validation helpers
- [x] Parser / normalizer entry points and CLI stubs
- [x] Surface-language parser implementation (Milestone 1 raw parse tree)
- [x] AST normalizer implementation (Milestone 2 core subset)
- [x] Normalized AST schema validation against the vendored schema package (Milestone 3)
- [ ] Evaluator implementation

## Why Pydantic now?

Moving the AST classes to Pydantic before parser work avoids a churny migration later. The parser,
normalizer, schema-validation layer, and eventual evaluator can all share the same typed runtime
objects and serialization path.

It also keeps a clean path open for later schema-driven work. I am **not** claiming direct LinkML
support here; the point is that the AST is now validated, serializable, and schema-emitting by
construction.

## Current normalized source coverage

The authored-source pipeline now supports parsing, normalizing, and schema-validating the current
Milestone 2 core subset end-to-end.

That subset includes:

- bundle ids and block ordering
- `frame { ... }` blocks and shorthand `frame @System:Namespace::regime` patterns
- `evaluator` blocks
- explicit `resolution_policy` blocks and synthetic single-evaluator defaulting
- `local`, `systemic`, and `meta` claim blocks with synthetic ids like `local#1`
- claim expressions for atomic predicates, predicate calls, logical expressions, `judged_by`, and `note`

The following authored forms are still intentionally out of scope and raise a normalization error:

- baselines, evidence, anchors, joint adequacy, and bridges
- claim metadata such as `refs`, `uses`, `requires`, and `annotations`
- declaration, causal, dynamic, and emergence authored expressions
- inline facet patterns such as `@{...}`

## Known vendored-schema issue

The shipped `limnalis_ast_schema_v0.2.2.json` contains a `$ref` typo: some `time` fields point to
`#/$defs/FixtureTimeSpec`, while the actual definition is `TimeCtxNode`.

The repo keeps the upstream schema file intact, but the runtime loader in `limnalis.schema`
includes an opt-in repair pass so schema validation works in practice.

## Repo layout

```text
limnalis/
  grammar/
    limnalis.lark
  src/limnalis/
    __init__.py
    __main__.py
    cli.py
    diagnostics.py
    loader.py
    normalizer.py
    parser.py
    schema.py
    models/
      __init__.py
      ast.py
      base.py
      conformance.py
  schemas/
    limnalis_ast_schema_v0.2.2.json
    limnalis_conformance_result_schema_v0.2.2.json
    limnalis_fixture_corpus_schema_v0.2.2.json
  fixtures/
    limnalis_fixture_corpus_v0.2.2.yaml
    limnalis_fixture_corpus_v0.2.2.json
  tests/
    ...
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
python -m pytest
```

Normalize authored surface syntax into canonical AST JSON:

```bash
limnalis normalize examples/minimal_bundle.lmn
```

Validate authored surface syntax end to end:

```bash
limnalis validate-source examples/minimal_bundle.lmn
```

Validate the fixture corpus:

```bash
limnalis validate-fixtures fixtures/limnalis_fixture_corpus_v0.2.2.json
```

Validate a canonical AST JSON payload:

```bash
limnalis validate-ast examples/minimal_bundle_ast.json
```

## Next implementation milestones

1. expand parser/normalizer coverage to the remaining authored constructs and inline pattern/object forms
2. wire gold cases A1, A3, A11, A14, B1, and B2 into snapshot tests
3. implement the evaluator and conformance pipeline
