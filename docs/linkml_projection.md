# LinkML Projection

The Limnalis interop layer can project canonical Pydantic models into LinkML
schema artifacts. This document describes what is projected, what is lost, and
how to use the generated artifacts.

**Important:** LinkML projections are DERIVED artifacts. They are not the
canonical source of truth. The canonical models live in the Pydantic model layer
under `src/limnalis/models/`. See the [Interop Overview](interop_overview.md)
for why this distinction matters.

## What is projected

The projection pipeline (`project_linkml_schema`) introspects the Pydantic
models' JSON Schema representation and converts it into a LinkML YAML schema
document. Three source models can be projected:

| Source model | Pydantic root class | Generated filename |
|---|---|---|
| `ast` | `BundleNode` from `limnalis.models.ast` | `limnalis_ast.linkml.yaml` |
| `evaluation_result` | `ExpectedResult` from `limnalis.models.conformance` | `limnalis_results.linkml.yaml` |
| `conformance_report` | `ExpectedResult` from `limnalis.models.conformance` | `limnalis_results.linkml.yaml` |

The generated LinkML document includes:

- **Classes** -- one per Pydantic model that has an `"object"` type with
  `"properties"` in the JSON Schema.
- **Enums** -- one per Pydantic field that uses `Literal` with string values.
- **Attributes** -- one per model field, with `range`, `required`, and
  `multivalued` annotations where applicable.
- **Metadata** -- schema `id`, `name`, `title`, `description`, and `prefixes`.

## What is NOT projected (lossy mappings)

The following Pydantic/JSON Schema constructs cannot be represented faithfully
in LinkML. The projection records these as warnings and lossy fields in the
returned `ProjectionResult`.

| Construct | Projection behavior |
|---|---|
| **Discriminated unions** (`anyOf`/`oneOf` with multiple `$ref` variants) | Projected as the first variant class. A `description` note lists all variants. |
| **Mixed unions** (union of refs and primitive types) | Projected as `string` range. |
| **Open dict types** (`dict[str, Any]`) | Projected as `string` range. |
| **Nested arrays / tuples** (`list[tuple[...]]`) | Projected as multivalued `string`. |
| **Pydantic validators** (field validators, model validators) | Not represented. |
| **Cross-field constraints** | Not represented. |
| **`extra='forbid'`** | Not represented (LinkML classes are open by default). |
| **Default values** | Not represented in the projection. |

Every lossy mapping is recorded in the `ProjectionResult`:

- `warnings` -- human-readable descriptions of what was lost.
- `lossy_fields` -- qualified field names (e.g. `BundleNode.steps`) affected.

## How to regenerate projection artifacts

### CLI

```bash
# Generate AST projection, write to file
limnalis project-linkml --target ast --output limnalis_ast.linkml.yaml

# Generate results projection, print to stdout
limnalis project-linkml --target evaluation_result

# Generate conformance projection
limnalis project-linkml --target conformance_report --output report.linkml.yaml
```

The CLI prints a summary including warning and lossy field counts:

```json
{
  "status": "ok",
  "target_format": "linkml",
  "source_model": "ast",
  "artifact_path": "limnalis_ast.linkml.yaml",
  "warnings_count": 5,
  "lossy_fields_count": 5,
  "warnings": [
    "BundleNode.steps: array of union type; projected as multivalued string (lossy)"
  ],
  "lossy_fields": [
    "BundleNode.steps"
  ]
}
```

### Programmatic API

```python
from limnalis.interop import project_linkml_schema

# Write to file
result = project_linkml_schema("ast", output_path="limnalis_ast.linkml.yaml")
print(f"Warnings: {len(result.warnings)}")
print(f"Lossy fields: {result.lossy_fields}")

# In-memory only (no file output)
result = project_linkml_schema("evaluation_result")
# result.artifact_path is None when no output_path is given
```

The `project_linkml_schema` function returns a `ProjectionResult`:

| Field | Type | Description |
|-------|------|-------------|
| `target_format` | string | Always `"linkml"`. |
| `source_model` | string | The model that was projected (e.g. `"ast"`). |
| `artifact_path` | string or null | Path to the written file, or null if not written. |
| `warnings` | list of strings | Human-readable lossy mapping descriptions. |
| `lossy_fields` | list of strings | Qualified names of fields with lossy projections. |

## Scope and limitations

1. **One-way projection.** There is no import path from LinkML back to canonical
   Pydantic models. LinkML artifacts are read-only outputs.

2. **No round-trip guarantee.** Data validated against the LinkML projection may
   not be valid against the canonical JSON Schema, and vice versa. The
   projection is a structural approximation.

3. **Regeneration required after model changes.** If the canonical Pydantic
   models change, the LinkML projection must be regenerated. Old projections
   become stale.

4. **Union types are the main source of loss.** Limnalis makes heavy use of
   discriminated unions. LinkML has no native equivalent, so these are reduced
   to the first variant or to `string`.

## Using projection artifacts in downstream tools

The generated `.linkml.yaml` files are standard LinkML schema documents. They
can be consumed by any tool that reads LinkML:

- **gen-json-schema** -- generate a JSON Schema from the LinkML (note: this
  will differ from the canonical vendored JSON Schema).
- **gen-python** -- generate Python dataclasses from the LinkML.
- **gen-markdown** / **gen-doc** -- generate human-readable documentation.
- **LinkML-store** -- load instances into a LinkML-backed data store.

Example: reading a projection artifact with plain PyYAML (no Limnalis runtime
needed):

```python
import yaml
from pathlib import Path

schema = yaml.safe_load(Path("limnalis_ast.linkml.yaml").read_text())
print(schema["name"])        # e.g. "limnalis_ast"
print(schema["title"])       # e.g. "Limnalis Ast Schema (Projected)"
for cls_name, cls_def in schema.get("classes", {}).items():
    attrs = cls_def.get("attributes", {})
    print(f"  {cls_name}: {len(attrs)} attributes")
```

See `examples/consumers/linkml_consumer.py` for a complete working example.

## Further reading

- [Interop Overview](interop_overview.md) -- canonical vs projected distinction.
- [Export Formats](export_formats.md) -- envelope formats (canonical).
- [Downstream Artifact Consumption](downstream_artifact_consumption.md) --
  consumer guide.
