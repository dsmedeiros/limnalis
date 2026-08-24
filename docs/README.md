# Limnalis Documentation Index

Every document under `docs/` is listed here, grouped by purpose. If you add a doc, add it to this index -- `tests/test_doc_snippets.py` enforces that every `docs/**/*.md` file is referenced here.

## Where to start (reading order)

1. [Getting Started](getting_started.md) -- install, first bundle, CLI walkthrough.
2. [How to Read Limnalis](reading_limnalis.md) -- **the orientation doc**: what to look for in a bundle, by audience (architects, plugin authors, governance reviewers). Read this before diving into the guides below.
3. [How Evaluation Works](how_evaluation_works.md) -- the 13-phase pipeline, truth values, resolution policies.
4. [Architecture](architecture.md) -- module map, public API surface, extension points.

The upstream language specification lives in [`../spec/`](../spec/README.md) (canonical consolidated spec, reconstruction, conformance matrix, and errata).

## Cookbook (task-oriented recipes)

| Doc | What it shows |
|---|---|
| [Conformance Testing](cookbook/conformance_testing.md) | Running fixture-corpus cases and reading comparison results |
| [Writing a Custom Plugin](cookbook/custom_plugin.md) | Handler → registry → runner wiring, step by step |
| [Multi-Evaluator Bundles](cookbook/multi_evaluator.md) | Independent evaluators plus resolution policies |
| [Transport Chains](cookbook/transport_chains.md) | Bridges, transport modes, property loss across frames |

## Semantic guides

| Doc | Topic |
|---|---|
| [Transport Semantics](transport_semantics.md) | Transport modes per spec §10.2, chain composition, degradation and completion policies |
| [Adequacy Execution Guide](adequacy_execution_guide.md) | Basis-driven adequacy, contested multi-producer aggregation |
| [Evidence Inference Guide](evidence_inference_guide.md) | Opt-in evidence relation inference (transitivity policies) |
| [Summary Policy Guide](summary_policy_guide.md) | Non-normative summarization (passthrough, severity-max, majority-vote) |
| [Paradox Gallery](paradox_gallery.md) | Track C stress bundles: liar, Banach-Tarski, Schwarzschild, decoherence |

## Extending Limnalis (plugin SDK)

| Doc | Extension point |
|---|---|
| [Plugin SDK Overview](plugin_sdk_overview.md) | Full API surface, registry model, plugin kinds |
| [Downstream Usage Examples](downstream_usage_examples.md) | Executable parse/normalize/evaluate/conformance patterns |
| [Writing an Evaluator Binding](writing_an_evaluator_binding.md) | `eval_expr` (phase 8) -- the most common extension |
| [Writing a Criterion Binding](writing_a_criterion_binding.md) | `JudgedExpr` criterion evaluation |
| [Writing an Adequacy Method](writing_an_adequacy_method.md) | Adequacy scoring feeding license composition |
| [Writing a Transport Handler](writing_a_transport_handler.md) | Cross-frame transport (phase 13), custom degradation policies |

## Interop and artifacts

Entry point: [Interop Overview](interop_overview.md) -- canonical vs projected models, consumer quick start.

| Doc | Topic |
|---|---|
| [Export Formats](export_formats.md) | Envelope types, serialization, version metadata |
| [Exchange Package Format](exchange_package_format.md) | Multi-artifact packages: manifest, checksums, validation |
| [Downstream Artifact Consumption](downstream_artifact_consumption.md) | Reading envelopes and packages as a consumer |
| [Interop Schema Export](interop_schema_export.md) | Exporting Pydantic model schemas for downstream tooling |
| [LinkML Projection](linkml_projection.md) | The lossy LinkML projection pipeline and its limits |
| [JSON-LD / RDF Note](jsonld_rdf_note.md) | Exploratory, non-normative: what would and would not map to RDF |
| [Schema Package Readme (v0.2.2)](limnalis_schema_package_readme_v0.2.2.md) | How the vendored JSON Schema layer was drafted from the corpus |

## Tooling

| Doc | Topic |
|---|---|
| [SARIF Export](sarif_export.md) | `lint`/`analyze --format sarif` for code-scanning pipelines |

## Governance, policy, and design records

| Doc | Topic |
|---|---|
| [Compatibility and Deviations](compatibility_and_deviations.md) | How spec/implementation mismatches are recorded; the current deviation ledger |
| [AST Pressure Points Settled (v0.2.2)](limnalis_ast_pressure_points_settled_v0.2.2.md) | AST decisions treated as settled for schema drafting |
| [Spec Errata](../spec/Limnalis-v0.2.2-errata.md) | Known errors and internal tensions in the vendored specification set |

### Architecture Decision Records ([adr/](adr/))

| ADR | Decision |
|---|---|
| [001](adr/001-pydantic-ast-models.md) | Pydantic AST models |
| [002](adr/002-execution-model.md) | Execution model |
| [003](adr/003-conformance-first-workflow.md) | Conformance-first workflow |
| [004](adr/004-public-api-freeze.md) | Public API freeze (`limnalis.api.*`) |
| [005](adr/005-summary-policy-separation.md) | Summary policy separation |
| [006](adr/006-evidence-inference-opt-in.md) | Evidence inference is opt-in |
| [007](adr/007-transport-chain-semantics.md) | Transport chain semantics |
| [008](adr/008-contested-adequacy-aggregation.md) | Contested adequacy aggregation (see its 2026-08-24 amendment) |

## Historical documents

Point-in-time milestone records, kept for provenance. Each carries a "Historical -- superseded" banner; do not use them as current references.

| Doc | Snapshot of |
|---|---|
| [Implementation Notes](implementation_notes.md) | Early design rationale (Pydantic choice, layering) |
| [Milestone 3B Notes](milestone_3b_notes.md) | Broadened evaluator + conformance harness delivery |
| [Milestone 3C Status](milestone_3c_status.md) | First full conformance pass |
| [M6B Stress Bundles](m6b_stress_bundles.md) | Transport/adequacy stress-bundle delivery |
| [Release Candidate Status](release_candidate_status.md) | v0.2.2rc1 snapshot (2026-03-25) |

## Related directories

- [`../spec/`](../spec/README.md) -- vendored specification set and errata
- [`../examples/`](../examples/) -- runnable `.lmn` bundles and consumer scripts
- [`../editor/`](../editor/) -- editor support (VS Code extension)
- [`../schemas/`](../schemas/) -- vendored JSON Schemas (immutable)
- [`../fixtures/`](../fixtures/) -- vendored fixture corpus + project extension corpus
