# Downstream Usage Examples

This cookbook shows common patterns for using the Limnalis public API to parse, normalize, evaluate, and test bundles.

All Python snippets below are executed by `tests/test_doc_snippets.py` from the repository root, so they stay in sync with the real API. The HTML comment markers (`<!-- doc-snippet: ... -->`) before each block are the extraction hooks for that test; they are invisible in rendered Markdown.

## What you'll need

- Python 3.11+
- Limnalis installed from a clone of this repository: `pip install -e .` (or `pip install -e ".[dev]"` to include test tooling). The package is not yet published to PyPI. Alternatively, run without installing via `PYTHONPATH=src python -m limnalis ...` from the repository root.
- Runtime dependencies (installed automatically): `pydantic` 2.x, `lark`, `jsonschema`, `PyYAML`.
- A `.lmn` surface file or pre-normalized AST JSON

## Minimal parse + normalize example

Parse a `.lmn` surface file into a raw parse tree, then normalize it into a validated AST. `normalize_surface_file` returns a `NormalizationResult` whose `canonical_ast` field holds the normalized `BundleNode`; claims are grouped by stratum under `bundle.claimBlocks`, and each block carries its own `claims` list:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.normalizer import normalize_surface_file

result = normalize_surface_file("examples/minimal_bundle.lmn")

# result.canonical_ast is a BundleNode (the normalized AST root)
bundle = result.canonical_ast
print(f"Bundle ID: {bundle.id}")
print(f"Claim blocks: {len(bundle.claimBlocks)}")
print(f"Claims: {sum(len(block.claims) for block in bundle.claimBlocks)}")
```

To normalize from a string instead of a file:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.normalizer import normalize_surface_text

source = """
bundle my_bundle {
  frame {
    system Demo;
    namespace Examples;
    scale unit;
    task check;
    regime standard;
  }

  evaluator ev1 {
    kind model;
    binding test://eval/demo_v1;
  }

  local {
    c1: overload(line_B);
  }
}
"""

result = normalize_surface_text(source)
bundle = result.canonical_ast
```

To use the parser and normalizer separately:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.parser import LimnalisParser
from limnalis.api.normalizer import Normalizer

parser = LimnalisParser()
tree = parser.parse_file("examples/minimal_bundle.lmn")

normalizer = Normalizer()
result = normalizer.normalize(tree)
bundle = result.canonical_ast
```

## Parse + normalize + evaluate example

Run the full pipeline from surface syntax to evaluation results. `run_bundle` requires the bundle plus two more positional arguments: the list of `SessionConfig` objects to execute and an `EvaluationEnvironment`:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)

# 1. Parse and normalize
result = normalize_surface_file("examples/minimal_bundle.lmn")
bundle = result.canonical_ast

# 2. Set up the evaluation environment and session plan
env = EvaluationEnvironment(clock="2026-01-01T00:00:00Z")
sessions = [SessionConfig(id="s1", steps=[StepConfig(id="step1")])]

# 3. Run evaluation (builtin primitives; without plugin services,
#    unbound evaluators fall back to defaults)
eval_result = run_bundle(bundle, sessions, env)

# 4. Inspect results
for session_result in eval_result.session_results:
    print(f"Session: {session_result.session_id}")
    for step_result in session_result.step_results:
        print(f"  Step: {step_result.step_id}")
        for claim_result in step_result.claim_results:
            print(f"    Claim {claim_result.claim_id}: evaluable={claim_result.is_evaluable}")
            if claim_result.aggregate:
                print(f"      Aggregate truth: {claim_result.aggregate.truth}")
```

## Using the plugin registry to wire custom evaluators

Register domain-specific handlers and wire them into the runner. Plugin IDs for evaluator bindings use the `"evaluator_id::expr_type"` convention; `ev0` is the evaluator declared in `examples/minimal_bundle.lmn`, so the handler below is actually consulted when that bundle is evaluated:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.services import (
    PluginRegistry,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    build_services_from_registry,
)
from limnalis.api.results import TruthCore, SupportResult
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)


# Define handlers
def my_predicate_handler(expr, claim, step_ctx, machine_state):
    return TruthCore(
        truth="T",
        reason="domain_check_passed",
        confidence=0.95,
        provenance=["my_eval_v1"],
    )


def my_support_policy(claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state):
    return SupportResult(
        support="supported",
        provenance=[evaluator_id],
    )


# Set up registry
registry = PluginRegistry()
registry.register(EVALUATOR_BINDING, "ev0::predicate", my_predicate_handler)
registry.register(EVIDENCE_POLICY, "my://policy/support_v1", my_support_policy)

# Build services and run
services = build_services_from_registry(registry)
bundle = normalize_surface_file("examples/minimal_bundle.lmn").canonical_ast

env = EvaluationEnvironment()
sessions = [SessionConfig(id="s1", steps=[StepConfig(id="step1")])]
result = run_bundle(bundle, sessions, env, services=services)
```

## Running B1 with the grid plugin pack

The grid example plugin pack provides handlers for the B1 fixture case (power grid contingency analysis). The B1 bundle is not a standalone `.lmn` file: it ships inside the fixture corpus (`fixtures/limnalis_fixture_corpus_v0.2.2.json`) as the `source` of case `B1`, so load the corpus and normalize the case source:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.conformance import load_corpus_from_default
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)
from limnalis.api.normalizer import normalize_surface_text
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.plugins.grid_example import register_grid_plugins

# 1. Create registry and register grid plugins
registry = PluginRegistry()
register_grid_plugins(registry)

# 2. Build services
services = build_services_from_registry(registry)

# 3. Load the B1 bundle from the fixture corpus and normalize it
corpus = load_corpus_from_default()
case = corpus.get_case("B1")
bundle = normalize_surface_text(case.source).canonical_ast

# 4. Evaluate
env = EvaluationEnvironment()
sessions = [SessionConfig(id="s1", steps=[StepConfig(id="step1")])]
result = run_bundle(bundle, sessions, env, services=services)

# 5. Inspect per-claim results
for session_result in result.session_results:
    for step_result in session_result.step_results:
        for claim_result in step_result.claim_results:
            print(f"Claim {claim_result.claim_id}:")
            for ev_id, eval_node in claim_result.per_evaluator.items():
                print(f"  {ev_id}: truth={eval_node.truth}, support={eval_node.support}")
```

The grid plugin pack registers:

- Evaluator bindings for `ev_grid` (predicate, causal, emergence)
- Grid support policy
- Grid adequacy check methods

## Running B2 with the JWT plugin pack

The JWT example plugin pack provides handlers for the B2 fixture case (JWT gateway authorization). Like B1, the B2 bundle lives inside the fixture corpus:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.conformance import load_corpus_from_default
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)
from limnalis.api.normalizer import normalize_surface_text
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.plugins.jwt_example import register_jwt_plugins

# 1. Create registry and register JWT plugins
registry = PluginRegistry()
register_jwt_plugins(registry)

# 2. Build services
services = build_services_from_registry(registry)

# 3. Load the B2 bundle from the fixture corpus and normalize it
corpus = load_corpus_from_default()
case = corpus.get_case("B2")
bundle = normalize_surface_text(case.source).canonical_ast

# 4. Evaluate
env = EvaluationEnvironment()
sessions = [SessionConfig(id="s1", steps=[StepConfig(id="step1")])]
result = run_bundle(bundle, sessions, env, services=services)

# 5. Check license results (B2 demonstrates license-level failure)
for session_result in result.session_results:
    for step_result in session_result.step_results:
        for claim_result in step_result.claim_results:
            if claim_result.license:
                overall = claim_result.license.overall
                print(f"Claim {claim_result.claim_id}: license={overall.truth}")
```

The JWT plugin pack registers:

- Evaluator bindings for `ev_gateway` (predicate, judged)
- JWT support policy
- JWT adequacy check methods

## Running conformance cases with the fixture plugin pack

The fixture plugin pack (`limnalis.plugins.fixtures`) provides deterministic handlers backed by expected values from fixture cases. You do not wire it up yourself: `run_case` applies it internally, building fixture-backed bindings from the case's expected results, then running the evaluator. Pass the corpus as the second argument so corpus-level fixture bindings are available:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.conformance import compare_case, load_corpus_from_default, run_case

# 1. Load the fixture corpus
corpus = load_corpus_from_default()

# 2. Run and compare each case (FixtureCorpus is not iterable itself;
#    iterate its .cases list)
for case in corpus.cases:
    print(f"Running case: {case.id}")

    actual = run_case(case, corpus)
    comparison = compare_case(case, actual)

    if comparison.passed:
        print("  PASS")
    else:
        print(f"  FAIL: {comparison.mismatches}")
```

`compare_case` returns a `CaseComparison` whose `mismatches` list holds field-level differences; its `warnings` list carries advisory notes (e.g. under-specified expectation pins) that never affect `passed`.

To load a corpus from an explicit path instead of the default vendored location:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.conformance import load_corpus

corpus = load_corpus("fixtures/limnalis_fixture_corpus_v0.2.2.json")
```

## Combining multiple plugin packs

You can register handlers from multiple packs into a single registry, as long as there are no plugin ID conflicts:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.plugins.grid_example import register_grid_plugins
from limnalis.plugins.jwt_example import register_jwt_plugins

registry = PluginRegistry()
register_grid_plugins(registry)
register_jwt_plugins(registry)

# Both sets of handlers are now available
services = build_services_from_registry(registry)

# List all registered plugins
for plugin in registry.list_plugins():
    print(f"  {plugin.kind}: {plugin.plugin_id} -- {plugin.description}")
```

## Inspecting evaluation diagnostics

The runner records diagnostics for stubbed or failing phases:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)
from limnalis.api.normalizer import normalize_surface_file

bundle = normalize_surface_file("examples/minimal_bundle.lmn").canonical_ast
env = EvaluationEnvironment()
sessions = [SessionConfig(id="s1", steps=[StepConfig(id="step1")])]

# No plugin services registered, so unbound phases record diagnostics
result = run_bundle(bundle, sessions, env)

for session_result in result.session_results:
    for step_result in session_result.step_results:
        if step_result.diagnostics:
            print(f"Step {step_result.step_id} diagnostics:")
            for diag in step_result.diagnostics:
                severity = diag.get("severity", "info")
                code = diag.get("code", "")
                message = diag.get("message", "")
                print(f"  [{severity}] {code}: {message}")
```

## Next steps

- [Plugin SDK overview](plugin_sdk_overview.md) -- full API surface and registry model
- [Writing an evaluator binding](writing_an_evaluator_binding.md) -- implement custom expression evaluation
- [Writing a criterion binding](writing_a_criterion_binding.md) -- implement criterion-based evaluation
- [Writing an adequacy method](writing_an_adequacy_method.md) -- implement adequacy scoring
- [Writing a transport handler](writing_a_transport_handler.md) -- implement cross-frame transport
