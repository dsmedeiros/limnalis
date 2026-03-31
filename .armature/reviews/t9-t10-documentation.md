# Review: T9-T10 Interop Documentation

**Reviewer:** Independent compliance reviewer
**Date:** 2026-03-30
**Scope:** docs/interop_overview.md, docs/exchange_package_format.md,
docs/export_formats.md, docs/linkml_projection.md,
docs/downstream_artifact_consumption.md, docs/jsonld_rdf_note.md

## Verdict: PASS

All five checklist items satisfied.

## Checklist Results

### 1. No source code changes -- PASS

The changeset consists of six new files, all under `docs/`. No `.py`, `.lark`,
`.json`, `.yaml`, or other source/config files were added or modified. Verified
via `git status --short`.

### 2. Canonical vs projected distinction -- PASS

The distinction is maintained clearly and consistently across all six documents:

- `interop_overview.md` dedicates a full section ("Canonical vs projected
  models -- a critical distinction") with separate subsections for each
  category and a rule-of-thumb summary.
- `linkml_projection.md` opens with a bold disclaimer that projections are
  DERIVED artifacts and not the canonical source of truth. Lossy mappings are
  enumerated in a table.
- `downstream_artifact_consumption.md` includes an explicit "Do not assume
  LinkML projection is authoritative" anti-pattern with code examples showing
  wrong vs right usage.
- `export_formats.md` consistently describes envelopes as serializations of
  canonical models.
- The stability table in `interop_overview.md` marks LinkML projection shape as
  "Not stable -- derived, may change" while canonical schemas are stable.

### 3. JSON-LD note is clearly non-normative -- PASS

`jsonld_rdf_note.md` opens with an explicit status block:
> Status: Exploratory. Not part of the Limnalis specification.
> No semantic dependency on RDF/OWL is established by this note.

Recommendations section reinforces this with "Keep as future work" and "No
implementation dependency on RDF/OWL." The note is not cross-linked from the
other five documents, avoiding any implication of normative status.

### 4. Accuracy of API references -- PASS

All API names referenced in the documentation were verified against the actual
`limnalis.interop.__all__` exports:

- Envelope types: `ASTEnvelope`, `ResultEnvelope`, `ConformanceEnvelope`,
  `SourceInfo` -- all present.
- Export functions: `export_ast`, `export_ast_from_dict`, `export_result`,
  `export_conformance`, `envelope_to_dict` -- all present.
- Import functions: `import_ast_envelope`, `import_result_envelope`,
  `import_conformance_envelope` -- all present.
- Package functions: `create_package`, `inspect_package`, `validate_package`,
  `extract_package` -- all present.
- Projection: `project_linkml_schema` -- present.
- Compatibility: `check_envelope_compatibility` -- present.
- Constants: `SPEC_VERSION`, `SCHEMA_VERSION`, `get_package_version` -- all
  present.

No phantom API names detected; no real API names omitted from relevant docs.

### 5. No governance modifications -- PASS

`.armature/` directory has no staged or unstaged changes. Verified via
`git status --short .armature/`.

## Minor Observations (non-blocking)

- The `jsonld_rdf_note.md` references a URL `limnalis.dev/schema/` that does
  not currently exist. This is acceptable since the note is explicitly
  exploratory and recommends this as future work.
- `linkml_projection.md` references `examples/consumers/linkml_consumer.py`
  which exists (added in T8). Cross-references are consistent.
