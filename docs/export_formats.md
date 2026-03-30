# Export Formats

This document specifies the envelope formats produced by the Limnalis interop
layer. Each exported artifact is wrapped in a typed envelope carrying version
metadata and optional provenance information.

## Envelope types

There are three envelope types, each corresponding to a distinct artifact kind.

### ASTEnvelope

Wraps a normalized canonical AST.

| Field | Type | Description |
|-------|------|-------------|
| `spec_version` | string | Limnalis specification version (e.g. `"0.2.2"`). |
| `schema_version` | string | JSON Schema version for AST validation (e.g. `"0.2.2"`). |
| `package_version` | string | Version of the `limnalis` package that produced this envelope. |
| `artifact_kind` | string | Always `"ast"`. |
| `source_info` | object or null | Provenance metadata (see below). |
| `normalized_ast` | object | The canonical AST payload as a JSON object. |

Example:

```json
{
  "artifact_kind": "ast",
  "normalized_ast": {
    "claimBlocks": [],
    "id": "minimal_bundle",
    "node_type": "bundle",
    "version": "0.2.2"
  },
  "package_version": "0.1.0",
  "schema_version": "0.2.2",
  "source_info": {
    "path": "examples/minimal_bundle.lmn",
    "sha256": null,
    "timestamp": null
  },
  "spec_version": "0.2.2"
}
```

### ResultEnvelope

Wraps an evaluation result.

| Field | Type | Description |
|-------|------|-------------|
| `spec_version` | string | Limnalis specification version. |
| `schema_version` | string | JSON Schema version. |
| `package_version` | string | Package version that produced this envelope. |
| `artifact_kind` | string | Always `"evaluation_result"`. |
| `source_info` | object or null | Provenance metadata. |
| `evaluation_result` | object | The evaluation result payload. |

### ConformanceEnvelope

Wraps a conformance report.

| Field | Type | Description |
|-------|------|-------------|
| `spec_version` | string | Limnalis specification version. |
| `schema_version` | string | JSON Schema version. |
| `package_version` | string | Package version that produced this envelope. |
| `artifact_kind` | string | Always `"conformance_report"`. |
| `corpus_version` | string or null | Version of the fixture corpus used. |
| `report` | object | The conformance report payload. |

### SourceInfo (provenance metadata)

All envelopes may carry a `source_info` object with optional provenance fields.

| Field | Type | Description |
|-------|------|-------------|
| `path` | string or null | Filesystem path of the original source file. |
| `sha256` | string or null | SHA-256 hex digest of the source file. |
| `timestamp` | string or null | ISO 8601 timestamp of when the source was processed. |

## JSON and YAML serialization

All export functions accept a `format` parameter: `"json"` (default) or
`"yaml"`.

### JSON serialization

- Indent: 2 spaces.
- Keys: sorted alphabetically (`sort_keys=True`).
- Encoding: UTF-8, no ASCII escaping (`ensure_ascii=False`).
- Produced by `json.dumps`.

### YAML serialization

- Block style (`default_flow_style=False`).
- Keys: sorted alphabetically (`sort_keys=True`).
- Encoding: UTF-8, unicode allowed (`allow_unicode=True`).
- Produced by `yaml.dump`.

### Deterministic ordering guarantee

Both JSON and YAML output use `sort_keys=True`. For the same input data, the
same serialized output is produced every time. This makes envelope files
suitable for content-addressed storage and diff-based review.

## Version metadata fields

Every envelope carries three version fields:

| Field | Source | Purpose |
|-------|--------|---------|
| `spec_version` | `limnalis.interop.types.SPEC_VERSION` | Identifies which Limnalis specification this artifact conforms to. |
| `schema_version` | `limnalis.interop.types.SCHEMA_VERSION` | Identifies the JSON Schema version used to validate the payload. |
| `package_version` | `limnalis.interop.types.get_package_version()` | The installed `limnalis` Python package version. |

You can retrieve the current values from the CLI:

```bash
limnalis --version
```

Output:

```json
{
  "spec_version": "0.2.2",
  "schema_version": "0.2.2",
  "package_version": "0.1.0"
}
```

## CLI export commands

### Export an AST envelope

```bash
# JSON (default)
limnalis export-ast path/to/source.lmn

# YAML
limnalis export-ast path/to/source.lmn --format yaml

# Redirect to file
limnalis export-ast path/to/source.lmn > ast_envelope.json
```

The command parses the `.lmn` file, normalizes it, wraps the canonical AST in
an `ASTEnvelope`, and prints the serialized output to stdout.

### Export a result envelope

```bash
limnalis export-result path/to/result.json
limnalis export-result path/to/result.yaml --format yaml
```

Reads a JSON or YAML file containing evaluation result data and wraps it in a
`ResultEnvelope`.

### Export a conformance envelope

```bash
limnalis export-conformance path/to/report.json
limnalis export-conformance path/to/report.json --corpus-version 1.0
```

Reads a conformance report file and wraps it in a `ConformanceEnvelope`. The
optional `--corpus-version` flag embeds the fixture corpus version in the
envelope.

## Programmatic API

### export_ast

Parses a `.lmn` source file, normalizes it, and returns a serialized AST
envelope.

```python
from limnalis.interop import export_ast

json_str = export_ast("examples/minimal_bundle.lmn", format="json")
yaml_str = export_ast("examples/minimal_bundle.lmn", format="yaml")
```

Parameters:

- `source_path` -- path to a `.lmn` file.
- `format` -- `"json"` (default) or `"yaml"`.
- `validate` -- whether to schema-validate the AST (default `True`).
- `source_info` -- optional `SourceInfo` for custom provenance.

### export_ast_from_dict

Wraps a pre-built AST dict (already normalized) in an envelope.

```python
from limnalis.interop import export_ast_from_dict

ast_data = {"id": "my_bundle", "node_type": "bundle", "version": "0.2.2"}
json_str = export_ast_from_dict(ast_data, format="json")
```

### export_result

Wraps an evaluation result dict in a `ResultEnvelope`.

```python
from limnalis.interop import export_result

result_data = {"sessions": [], "status": "complete"}
json_str = export_result(result_data, format="json")
```

### export_conformance

Wraps a conformance report dict in a `ConformanceEnvelope`.

```python
from limnalis.interop import export_conformance

report_data = {"passed": 10, "failed": 0}
json_str = export_conformance(report_data, corpus_version="1.0")
```

### envelope_to_dict

Converts any envelope model to a plain dict (useful for custom serialization).

```python
from limnalis.interop import envelope_to_dict, ASTEnvelope

envelope = ASTEnvelope(
    spec_version="0.2.2",
    schema_version="0.2.2",
    package_version="0.1.0",
    normalized_ast={"id": "test"},
)
d = envelope_to_dict(envelope)  # plain dict, JSON-serializable
```

## Further reading

- [Interop Overview](interop_overview.md) -- architecture and canonical vs
  projected distinction.
- [Exchange Package Format](exchange_package_format.md) -- packaging envelopes
  into exchange bundles.
- [Downstream Artifact Consumption](downstream_artifact_consumption.md) --
  how to consume these envelopes.
