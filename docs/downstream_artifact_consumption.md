# Downstream Artifact Consumption

This guide is for tool authors and pipeline operators who need to consume
Limnalis interop artifacts. It covers envelopes, exchange packages, and
compatibility checking with concrete code examples.

## Prerequisites

Install the `limnalis` package:

```bash
pip install limnalis
```

All consumer-facing functionality lives in `limnalis.interop`. You should only
import from this module.

## Consuming AST envelopes

An AST envelope is a JSON or YAML file containing a normalized canonical AST
wrapped in version metadata. It is the primary artifact for tools that need to
read Limnalis parse results.

### From a file

```python
from pathlib import Path
from limnalis.interop import import_ast_envelope

envelope = import_ast_envelope(Path("bundle_ast.json"))

# Access version metadata
print(envelope.spec_version)       # e.g. "0.2.2"
print(envelope.schema_version)     # e.g. "0.2.2"
print(envelope.package_version)    # e.g. "0.1.0"
print(envelope.artifact_kind)      # "ast"

# Access the AST payload
ast = envelope.normalized_ast
print(ast["id"])                   # bundle ID
print(ast["node_type"])            # "bundle"
```

### From a string

```python
from limnalis.interop import import_ast_envelope

json_text = '{"spec_version": "0.2.2", ...}'
envelope = import_ast_envelope(json_text, format="json")
```

When importing from a string, the `format` parameter is required.

### From a dict

```python
from limnalis.interop import import_ast_envelope

data = {"spec_version": "0.2.2", "schema_version": "0.2.2", ...}
envelope = import_ast_envelope(data)
```

### Format detection

When importing from a `Path`, the format is auto-detected from the file
extension:

- `.json` -- parsed as JSON.
- `.yaml` or `.yml` -- parsed as YAML.
- Other extensions -- raises `ValueError`; pass `format` explicitly.

## Consuming result envelopes

Result envelopes wrap evaluation results from the Limnalis runtime.

```python
from pathlib import Path
from limnalis.interop import import_result_envelope

envelope = import_result_envelope(Path("result.json"))

print(envelope.artifact_kind)       # "evaluation_result"
result = envelope.evaluation_result
# Inspect result-specific keys
for key in sorted(result.keys()):
    print(f"  {key}")
```

## Consuming conformance envelopes

Conformance envelopes wrap conformance reports that test a Limnalis
implementation against the fixture corpus.

```python
from pathlib import Path
from limnalis.interop import import_conformance_envelope

envelope = import_conformance_envelope(Path("conformance.json"))

print(envelope.artifact_kind)       # "conformance_report"
print(envelope.corpus_version)      # version of fixture corpus used
report = envelope.report
```

## Consuming exchange packages

An exchange package bundles multiple artifacts with a manifest and checksums.
See [Exchange Package Format](exchange_package_format.md) for the full
specification.

### Inspect a package

```python
from limnalis.interop import inspect_package

metadata = inspect_package("my_package/")  # or "my_package.zip"
manifest = metadata.manifest

print(manifest.spec_version)
print(manifest.artifact_types)    # e.g. ["ast", "source"]
print(manifest.checksums)         # {"ast/bundle.json": "abc123..."}
```

### Validate a package

Always validate before trusting package contents:

```python
from limnalis.interop import validate_package

issues = validate_package("my_package/")
if issues:
    for issue in issues:
        print(f"PROBLEM: {issue}")
    raise RuntimeError("Package validation failed")
```

Validation checks:

- `manifest.json` exists and parses as valid JSON.
- Manifest conforms to the `ExchangeManifest` schema.
- All files listed in `checksums` exist.
- All SHA-256 checksums match.
- Subdirectory contents match declared `artifact_types`.
- Version fields are non-empty.

### Extract a package

```python
from limnalis.interop import extract_package

output_dir = extract_package("my_package.zip", "./extracted/")
# output_dir is a Path pointing to ./extracted/
# Now read individual files from the extracted directory
```

### End-to-end: validate, extract, read artifacts

```python
from pathlib import Path
from limnalis.interop import (
    validate_package,
    extract_package,
    inspect_package,
    import_ast_envelope,
)

pkg_path = "my_package.zip"

# 1. Validate
issues = validate_package(pkg_path)
if issues:
    raise RuntimeError(f"Invalid package: {issues}")

# 2. Extract
extracted = extract_package(pkg_path, "./work/")

# 3. Discover artifacts
metadata = inspect_package(extracted)
print(f"Contains: {metadata.manifest.artifact_types}")

# 4. Read AST envelopes
ast_dir = extracted / "ast"
if ast_dir.is_dir():
    for ast_file in sorted(ast_dir.iterdir()):
        envelope = import_ast_envelope(ast_file)
        print(f"  Bundle: {envelope.normalized_ast.get('id')}")
```

## Compatibility checking

When consuming an envelope produced by a different version of Limnalis, check
compatibility before processing:

```python
from limnalis.interop import (
    import_ast_envelope,
    check_envelope_compatibility,
    SPEC_VERSION,
    SCHEMA_VERSION,
)

envelope = import_ast_envelope("bundle_ast.json")

issues = check_envelope_compatibility(envelope)
if issues:
    print(f"Local versions: spec={SPEC_VERSION}, schema={SCHEMA_VERSION}")
    for issue in issues:
        print(f"  WARNING: {issue}")
    # Decide whether to proceed or abort
```

The compatibility check compares:

- `envelope.spec_version` against the local `SPEC_VERSION`.
- `envelope.schema_version` against the local `SCHEMA_VERSION`.

A mismatch does not necessarily mean the envelope is unusable, but it means the
envelope was produced against a different specification or schema version and
the payload structure may differ.

## What NOT to do

### Do not import from internal modules

```python
# WRONG -- internal modules are not stable
from limnalis.models.ast import BundleNode
from limnalis.normalizer import normalize

# RIGHT -- use the interop API
from limnalis.interop import import_ast_envelope, export_ast
```

The `limnalis.interop` public API (everything in `__all__`) is the stable
contract. Internal modules (`limnalis.models`, `limnalis.normalizer`,
`limnalis.parser`, `limnalis.runtime`) may change without notice.

### Do not parse envelope JSON manually

```python
# WRONG -- no validation, no type safety
import json
data = json.loads(Path("bundle.json").read_text())
ast = data["normalized_ast"]

# RIGHT -- validated Pydantic model
from limnalis.interop import import_ast_envelope
envelope = import_ast_envelope("bundle.json")
ast = envelope.normalized_ast
```

Using `import_ast_envelope` ensures the envelope conforms to the expected
structure. Extra fields are rejected (`extra='forbid'`), missing required fields
raise validation errors, and types are checked.

### Do not assume LinkML projection is authoritative

```python
# WRONG -- treating projection as the schema authority
linkml_schema = yaml.safe_load(open("limnalis_ast.linkml.yaml"))
# ... using linkml_schema to validate data

# RIGHT -- use canonical JSON Schema for validation
# or use import_ast_envelope which validates via Pydantic
```

The LinkML projection is lossy. Use the vendored JSON Schemas or the Pydantic
import functions for validation.

### Do not modify exchange package contents without regenerating checksums

If you add, remove, or modify files in an exchange package, the checksums in
`manifest.json` will no longer match. Use `create_package` to build a new
package, or re-run `validate_package` after manual changes to detect mismatches.

## Example scripts

Complete working examples are provided in `examples/consumers/`:

| Script | What it demonstrates |
|--------|---------------------|
| `read_ast_envelope.py` | Load an AST envelope, print summary, check compatibility |
| `read_result_envelope.py` | Load a result envelope, print summary |
| `inspect_package.py` | Inspect exchange package metadata |
| `linkml_consumer.py` | Read a LinkML projection with plain PyYAML (no runtime) |

Run any example:

```bash
python examples/consumers/read_ast_envelope.py bundle_ast.json
python examples/consumers/inspect_package.py my_package/
python examples/consumers/linkml_consumer.py limnalis_ast.linkml.yaml
```

## Further reading

- [Interop Overview](interop_overview.md) -- architecture, canonical vs
  projected models, quick start.
- [Export Formats](export_formats.md) -- envelope specification, serialization.
- [Exchange Package Format](exchange_package_format.md) -- package structure,
  manifest fields, checksums.
- [LinkML Projection](linkml_projection.md) -- projection details and
  limitations.
