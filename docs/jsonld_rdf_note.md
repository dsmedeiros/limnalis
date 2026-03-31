# JSON-LD / RDF Mapping Note (Non-Normative)

> **Status**: Exploratory. Not part of the Limnalis specification.
> No semantic dependency on RDF/OWL is established by this note.

## Context

Limnalis exports structured artifacts (AST envelopes, evaluation results, conformance
reports) as JSON. Organizations that maintain RDF-based knowledge graphs or linked-data
pipelines may want to ingest these artifacts alongside other semantic resources. A
JSON-LD context layer would let standard JSON output be interpreted as RDF triples
without changing the canonical serialization.

## Potential Approach

Each envelope type (`ASTEnvelope`, `ResultEnvelope`, `ConformanceEnvelope`) could carry
an optional `@context` property pointing to a Limnalis-hosted context document. Because
the envelopes already use `artifact_kind` as a discriminator, this maps naturally to an
`@type` annotation.

Example JSON-LD snippet for an `ASTEnvelope`:

```json
{
  "@context": {
    "@vocab": "https://limnalis.dev/schema/",
    "spec_version": "limnalis:specVersion",
    "schema_version": "limnalis:schemaVersion",
    "artifact_kind": "@type",
    "normalized_ast": {
      "@id": "limnalis:normalizedAST",
      "@type": "@json"
    }
  },
  "spec_version": "0.2.2",
  "schema_version": "0.2.2",
  "package_version": "0.1.0",
  "artifact_kind": "ast",
  "source_info": {
    "path": "example.lmn",
    "sha256": "abc123...",
    "timestamp": "2026-03-30T12:00:00Z"
  },
  "normalized_ast": { "..." : "..." }
}
```

The `@json` type on `normalized_ast` treats the entire AST payload as an opaque JSON
literal, avoiding the need to define RDF mappings for every internal AST node.

## Scope and Limitations

**Maps cleanly:**
- Envelope-level metadata (versions, timestamps, artifact kind).
- `SourceInfo` provenance fields (path, sha256, timestamp).
- Flat string/numeric attributes on AST nodes (id, kind, status enums).

**Does not map cleanly:**
- **Discriminated unions.** The AST uses Pydantic discriminated unions extensively
  (e.g., `Expr` variants). RDF has no native union concept; each variant would need its
  own `@type`, and consumers would need to handle open class hierarchies.
- **Open dict fields** (`dict[str, Any]`). These appear in `ClaimNode.annotations` and
  envelope payloads. JSON-LD `@json` can encapsulate them but they become opaque to
  SPARQL queries.
- **Cross-field validators.** Pydantic constraints (e.g., conditional required fields)
  have no RDF/OWL equivalent. SHACL shapes could partially express these but would be a
  separate maintenance burden.

The existing LinkML projection (`linkml/limnalis_ast.linkml.yaml`) documents these same
lossy boundaries: discriminated unions project as first-variant, open dicts as strings,
and validators are omitted.

## Recommendations

1. **Keep as future work.** Do not introduce `@context` into the canonical envelope
   models or JSON Schema at this time.
2. **No implementation dependency on RDF/OWL.** The Pydantic model layer and vendored
   JSON Schema remain the sole sources of truth.
3. **If pursued, scope narrowly.** Start with envelope-level metadata only; treat
   `normalized_ast` as an opaque `@json` blob rather than attempting full AST-to-RDF
   mapping.
4. **Leverage LinkML if expanding.** The existing LinkML projection could generate
   JSON-LD contexts via LinkML tooling, keeping the derivation automated rather than
   hand-maintained.
5. **Publish context documents separately.** Any future `@context` should live at a
   stable URL under `limnalis.dev/schema/` and be versioned alongside `spec_version`.
