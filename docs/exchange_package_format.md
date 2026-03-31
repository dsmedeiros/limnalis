# Exchange Package Format

An exchange package bundles multiple Limnalis artifacts (source files, AST
envelopes, evaluation results, conformance reports) into a single self-describing
unit with integrity checksums. Packages can be exchanged between tools, archived,
or used as CI pipeline artifacts.

## Package structure

A package is either a **directory** or a **zip archive** with the following
layout:

```
my_package/
  manifest.json
  source/            (optional -- .lmn source files)
    minimal_bundle.lmn
  ast/               (optional -- AST envelope files)
    minimal_bundle_ast.json
  results/           (optional -- evaluation result files)
    run_001.json
  conformance/       (optional -- conformance report files)
    report.json
```

Only subdirectories that contain artifacts are created. An empty package is
valid but unusual.

### Subdirectory mapping

| Subdirectory   | Artifact type in manifest  | Contents |
|----------------|---------------------------|----------|
| `source/`      | `source`                  | Raw `.lmn` surface files |
| `ast/`         | `ast`                     | AST envelope JSON/YAML |
| `results/`     | `evaluation_result`       | Result envelope JSON/YAML |
| `conformance/` | `conformance_report`      | Conformance envelope JSON/YAML |

## Manifest format

Every package contains a `manifest.json` at its root. The manifest is a JSON
object with deterministic key ordering.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format_version` | string | yes | Manifest format version. Currently `"1.0"`. |
| `spec_version` | string | yes | Limnalis spec version (e.g. `"0.2.2"`). |
| `schema_version` | string | yes | JSON Schema version for AST payloads (e.g. `"0.2.2"`). |
| `package_version` | string | yes | Version of the `limnalis` package that created this. |
| `corpus_version` | string or null | no | Fixture corpus version, if applicable. |
| `artifact_types` | array of strings | yes | Sorted list of artifact types present. |
| `plugin_requirements` | array of strings | no | Package names required to process artifacts. Defaults to `[]`. |
| `checksums` | object | yes | Map of relative file paths to SHA-256 hex digests. |
| `created_at` | string or null | no | ISO 8601 UTC timestamp of package creation. |

### Example manifest.json

```json
{
  "artifact_types": [
    "ast",
    "source"
  ],
  "checksums": {
    "ast/minimal_bundle_ast.json": "a1b2c3d4e5f6...full_sha256_hex...",
    "source/minimal_bundle.lmn": "f6e5d4c3b2a1...full_sha256_hex..."
  },
  "corpus_version": null,
  "created_at": "2026-03-30T12:00:00+00:00",
  "format_version": "1.0",
  "package_version": "0.1.0",
  "plugin_requirements": [],
  "schema_version": "0.2.2",
  "spec_version": "0.2.2"
}
```

## Artifact types

The `artifact_types` array in the manifest records which categories of artifact
are present. Valid values:

- `"source"` -- raw Limnalis surface syntax files.
- `"ast"` -- normalized AST envelopes (see [Export Formats](export_formats.md)).
- `"evaluation_result"` -- evaluation result envelopes.
- `"conformance_report"` -- conformance report envelopes.

## Checksum verification

Every non-manifest file in the package has a SHA-256 checksum recorded in the
`checksums` field. Keys are forward-slash-separated relative paths from the
package root (e.g. `"ast/bundle.json"`).

To verify integrity:

1. Read the `manifest.json`.
2. For each entry in `checksums`, read the file and compute its SHA-256 hex
   digest.
3. Compare the computed digest to the manifest value. Any mismatch indicates
   corruption or tampering.

The `validate_package` function and `package-validate` CLI command perform this
check automatically and also verify that:

- All files in `checksums` exist.
- All checksums match.
- Subdirectory contents match the declared `artifact_types`.
- Version fields are non-empty.

## Zip vs directory formats

Packages can be stored in either format:

| Format | When to use | Notes |
|--------|------------|-------|
| `directory` | Local workflows, development | Human-readable, easy to inspect |
| `zip` | Archival, transfer, CI artifacts | Single file, ZIP_DEFLATED compression |

All package operations (`inspect_package`, `validate_package`, `extract_package`)
transparently handle both formats. The format is auto-detected: if the path
points to a file that is a valid zip, it is treated as a zip package; otherwise
it is treated as a directory.

When creating a zip package, the tool builds the directory layout in a temporary
location, writes `manifest.json`, then zips the contents. The temporary
directory is cleaned up automatically.

## CLI commands for package operations

### Create a package

```bash
# Directory format
limnalis package-create ./my_package \
    --source examples/minimal_bundle.lmn \
    --ast bundle_ast.json \
    --result run_001.json \
    --conformance report.json \
    --format directory

# Zip format
limnalis package-create my_package.zip \
    --ast bundle_ast.json \
    --format zip
```

Output on success:

```json
{
  "status": "ok",
  "root_path": "./my_package",
  "artifact_types": ["ast", "source"]
}
```

### Inspect a package

```bash
limnalis package-inspect ./my_package
limnalis package-inspect my_package.zip
```

Prints the full manifest as JSON.

### Validate a package

```bash
limnalis package-validate ./my_package
```

Output when valid:

```json
{
  "status": "ok"
}
```

Output when issues are found:

```json
{
  "status": "invalid",
  "issues": [
    "Checksum mismatch for ast/bundle.json: expected abc123..., got def456..."
  ]
}
```

### Extract a package

```bash
limnalis package-extract my_package.zip ./extracted/
```

Extracts a zip package to a directory, or copies a directory package to the
target location.

## Programmatic API

```python
from limnalis.interop import (
    create_package,
    inspect_package,
    validate_package,
    extract_package,
)

# Create
metadata = create_package(
    "my_package/",
    source_files=["examples/minimal_bundle.lmn"],
    ast_files=["bundle_ast.json"],
    format="directory",
)
print(metadata.manifest.artifact_types)
print(metadata.manifest.checksums)

# Inspect
metadata = inspect_package("my_package/")
print(metadata.manifest.spec_version)

# Validate
issues = validate_package("my_package/")
if issues:
    for issue in issues:
        print(f"ISSUE: {issue}")

# Extract
extract_package("my_package.zip", "./extracted/")
```

## Further reading

- [Interop Overview](interop_overview.md) -- high-level architecture.
- [Export Formats](export_formats.md) -- envelope format details for the files
  inside a package.
- [Downstream Artifact Consumption](downstream_artifact_consumption.md) --
  end-to-end consumer guide.
