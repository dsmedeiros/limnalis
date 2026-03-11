# Limnalis v0.2.2 schema package

This package drafts the JSON Schema layer directly from the conformance corpus rather than from prose alone.

Files:
- `limnalis_ast_schema_v0.2.2.json` — canonical AST schema for normalized bundles and node families
- `limnalis_conformance_result_schema_v0.2.2.json` — expected-result schema used by conformance cases
- `limnalis_fixture_corpus_schema_v0.2.2.json` — top-level schema for the machine-readable fixture corpus
- `limnalis_schema_validation_report_v0.2.2.json` — validation report for the current `limnalis_fixture_corpus_v0.2.2.json`

Settled directly from the corpus:
- `ResolutionPolicyNode` as a discriminated union with conditional requirements
- `TransportNode` as a discriminated union with conditional requirements
- optional `AdequacyAssessmentNode.score`
- explicit `per_evaluator` maps on claim and block outputs

Notes:
- Some semantic constraints are intentionally left to evaluator-level validation because plain JSON Schema cannot express them cleanly, including:
  - exact-set equality for joint adequacy anchor matching
  - uniqueness of ids across bundle-local namespaces
  - equality between `priority_order.members` and `priority_order.order`
  - cross-node circular-dependency detection in adequacy basis chains
- The fixture schema validates the current corpus structurally. Parser/normalizer output should target the AST schema; evaluator conformance output should target the conformance-result schema.

Validation summary:
- Fixture corpus valid against fixture schema: True
- Error count: 0
