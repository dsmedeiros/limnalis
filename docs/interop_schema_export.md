# Interoperability: Exporting Public Models for Downstream Schema Tooling

Limnalis AST models are Pydantic v2 `BaseModel` subclasses, which means they
can be exported to JSON Schema for consumption by downstream schema-generation
toolchains (LinkML, JSON-LD, OpenAPI, dataclasses-json, etc.).

## Exporting JSON Schema from Public Models

```python
from limnalis.api.models import BundleNode

# Single model schema
schema = BundleNode.model_json_schema()

# Write to file
import json
with open("bundle_schema.json", "w") as f:
    json.dump(schema, f, indent=2)
```

## Inspecting All Public AST Types

```python
from limnalis.api import models

# List all exported AST types
for name in models.__all__:
    cls = getattr(models, name)
    if hasattr(cls, "model_json_schema"):
        schema = cls.model_json_schema()
        print(f"{name}: {len(schema.get('properties', {}))} properties")
```

## Exporting Result Types

```python
from limnalis.api.results import StepResult, TruthCore, EvalNode

# Result schemas for downstream consumers
for cls in [StepResult, TruthCore, EvalNode]:
    schema = cls.model_json_schema()
    print(f"{cls.__name__}: {json.dumps(schema, indent=2)}")
```

## LinkML Mapping Path

For teams using LinkML for semantic data modeling:

1. Export Pydantic models to JSON Schema (as above)
2. Use `linkml-schema-fixer` or `schema-automator` to convert JSON Schema to LinkML YAML
3. Annotate with semantic URIs as needed

```bash
# Example using schema-automator (if installed)
pip install linkml-schema-automator
schemauto import-json-schema bundle_schema.json -o bundle.linkml.yaml
```

This is a one-way export path. Limnalis models remain the source of truth;
LinkML schemas are derived artifacts for interop purposes.

## Vendored JSON Schemas

Limnalis also ships vendored JSON Schemas under `schemas/`:

- `limnalis_ast_schema_v0.2.2.json` — canonical AST validation
- `limnalis_conformance_result_schema_v0.2.2.json` — evaluation result validation
- `limnalis_fixture_corpus_schema_v0.2.2.json` — fixture corpus validation

These are the authoritative schemas for AST validation. The Pydantic model
schemas above are derived and may include additional Python-specific type
information.

## Limitations

- Pydantic discriminated unions (`ExprNode`, `TermNode`) export as `anyOf`
  schemas, which some tools handle differently.
- Pydantic's `extra="forbid"` maps to `additionalProperties: false`.
- Custom validators (e.g., `BaselineNode` cross-field rules) are not captured
  in the JSON Schema export — they exist only in the Python runtime.
- The vendored schemas under `schemas/` are hand-curated and may differ
  slightly from Pydantic's auto-generated output.
