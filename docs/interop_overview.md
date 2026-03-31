# Limnalis Interoperability Layer -- Overview

This document describes the Limnalis interop layer for downstream tool authors,
CI pipelines, and any consumer that needs to read, write, or exchange Limnalis
artifacts without depending on Limnalis internals.

## What the interop layer provides

The interop layer is a stable public API surface (`limnalis.interop`) that lets
external tools:

- **Export** normalized ASTs, evaluation results, and conformance reports as
  versioned JSON or YAML envelopes.
- **Import** those envelopes back into validated Pydantic models.
- **Package** multiple artifacts into self-describing exchange packages (directory
  or zip) with SHA-256 integrity checksums.
- **Project** canonical Pydantic models into LinkML schema artifacts for use in
  documentation and external toolchains.
- **Check compatibility** of an envelope against the local implementation version.

All of this is accessible through both a Python API (`from limnalis.interop
import ...`) and the `limnalis` CLI.

## Canonical vs projected models -- a critical distinction

Limnalis maintains two categories of model representation. Understanding the
difference is essential.

### Canonical models (source of truth)

- Defined as **Pydantic v2 models** in `src/limnalis/models/`.
- Validated against **vendored JSON Schemas** in `schemas/`.
- Deterministic: the same surface input always produces the same canonical AST.
- Every envelope payload (`normalized_ast`, `evaluation_result`, `report`) is
  a serialization of these canonical models.
- Stability guarantee: the canonical models and their JSON Schema are versioned
  by `spec_version` and `schema_version`.

### Projected models (derived, approximate)

- Generated from canonical models via the **LinkML projection pipeline**
  (`project_linkml_schema`).
- The projection is **lossy**: discriminated unions, open dicts, cross-field
  validators, and nested tuples cannot be fully represented in LinkML.
- Projections carry a header comment stating they are derived artifacts.
- Projections are useful for documentation, RDF interop, and toolchains that
  consume LinkML -- but they are never the authority on what is valid Limnalis.

**Rule of thumb:** if you need to validate data, use the canonical JSON Schemas.
If you need to feed a documentation generator or an RDF pipeline, use the LinkML
projection.

## What is guaranteed stable

| Item | Stability |
|------|-----------|
| Envelope field names and structure | Stable within a `spec_version` |
| JSON Schema for AST payloads | Stable within a `schema_version` |
| `limnalis.interop` public API names | Stable (listed in `__all__`) |
| Exchange package manifest format | Stable at `format_version` 1.0 |
| LinkML projection shape | Not stable -- derived, may change |
| Internal modules (`limnalis.models`, `limnalis.normalizer`, etc.) | Not stable for external use |

## Architecture

```
                        .lmn source files
                              |
                    +---------v----------+
                    |   Parser / Lark    |
                    +---------+----------+
                              |
                    +---------v----------+
                    |    Normalizer      |
                    +---------+----------+
                              |
                    +---------v----------+
                    | Canonical Pydantic |----> JSON Schema validation
                    |      Models        |
                    +---------+----------+
                              |
              +---------------+----------------+
              |               |                |
     +--------v-------+ +----v-----+  +-------v--------+
     | Export (JSON/   | | Package  |  | LinkML         |
     | YAML envelopes)| | (dir/zip)|  | Projection     |
     +--------+-------+ +----+-----+  +-------+--------+
              |               |                |
              v               v                v
        Envelope files   Exchange packages  .linkml.yaml
        (consumable)     (manifest +        (derived,
                          checksums)         lossy)
```

## Quick start for consumers

### Install limnalis

```bash
pip install limnalis
```

### Export an AST envelope from the CLI

```bash
limnalis export-ast examples/minimal_bundle.lmn --format json > bundle_ast.json
```

### Read an envelope in Python

```python
from limnalis.interop import import_ast_envelope, check_envelope_compatibility

envelope = import_ast_envelope("bundle_ast.json")

# Inspect the payload
print(envelope.spec_version)
print(envelope.normalized_ast["id"])

# Check version compatibility
issues = check_envelope_compatibility(envelope)
if issues:
    print("Warnings:", issues)
```

### Create an exchange package from the CLI

```bash
limnalis package-create my_package/ \
    --source examples/minimal_bundle.lmn \
    --ast bundle_ast.json \
    --format directory
```

### Project to LinkML

```bash
limnalis project-linkml --target ast --output limnalis_ast.linkml.yaml
```

## Further reading

- [Exchange Package Format](exchange_package_format.md) -- package structure,
  manifest specification, checksum verification.
- [Export Formats](export_formats.md) -- envelope specification, serialization
  details, programmatic API.
- [LinkML Projection](linkml_projection.md) -- what is projected, lossy
  mappings, regeneration.
- [Downstream Artifact Consumption](downstream_artifact_consumption.md) --
  consumer guide with code examples.
