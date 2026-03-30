# Downstream Usage Examples

This cookbook shows common patterns for using the Limnalis public API to parse, normalize, evaluate, and test bundles.

## What you'll need

- Python 3.11+
- Limnalis installed (`pip install limnalis` or `pip install -e ".[dev]"`)
- A `.lmn` surface file or pre-normalized AST JSON

## Minimal parse + normalize example

Parse a `.lmn` surface file into a raw parse tree, then normalize it into a validated AST:

```python
from limnalis.api.normalizer import normalize_surface_file

result = normalize_surface_file("examples/minimal_bundle.lmn")

# result.bundle is a BundleNode (the normalized AST root)
bundle = result.bundle
print(f"Bundle ID: {bundle.id}")
print(f"Claims: {len(bundle.claims)}")
```

To normalize from a string instead of a file:

```python
from limnalis.api.normalizer import normalize_surface_text

source = """
bundle my_bundle
  frame system=test namespace=demo scale=unit task=check regime=standard
  claim c1 (atomic)
    overload(line_B)
  evaluator ev1 (model, primary)
    bind ev1 -> c1
"""

result = normalize_surface_text(source)
bundle = result.bundle
```

To use the parser and normalizer separately:

```python
from limnalis.api.parser import LimnalisParser
from limnalis.api.normalizer import Normalizer

parser = LimnalisParser()
tree = parser.parse_file("examples/minimal_bundle.lmn")

normalizer = Normalizer()
result = normalizer.normalize(tree)
bundle = result.bundle
```

## Parse + normalize + evaluate example

Run the full pipeline from surface syntax to evaluation results:

```python
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import run_bundle, EvaluationEnvironment

# 1. Parse and normalize
result = normalize_surface_file("my_bundle.lmn")
bundle = result.bundle

# 2. Set up the evaluation environment
env = EvaluationEnvironment(clock="2024-01-01T00:00:00Z")

# 3. Run evaluation (uses builtin primitives -- most phases are stubbed)
eval_result = run_bundle(bundle, env=env)

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

Register domain-specific handlers and wire them into the runner:

```python
from limnalis.api.services import (
    PluginRegistry,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    build_services_from_registry,
)
from limnalis.api.results import TruthCore, SupportResult
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import run_bundle


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
registry.register(EVALUATOR_BINDING, "my_eval::predicate", my_predicate_handler)
registry.register(EVIDENCE_POLICY, "my://policy/support_v1", my_support_policy)

# Build services and run
services = build_services_from_registry(registry)
bundle = normalize_surface_file("my_bundle.lmn").bundle
result = run_bundle(bundle, services=services)
```

## Running B1 with the grid plugin pack

The grid example plugin pack provides handlers for the B1 fixture case (power grid contingency analysis):

```python
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import run_bundle
from limnalis.plugins.grid_example import register_grid_plugins

# 1. Create registry and register grid plugins
registry = PluginRegistry()
register_grid_plugins(registry)

# 2. Build services
services = build_services_from_registry(registry)

# 3. Parse, normalize, and evaluate the B1 bundle
bundle = normalize_surface_file("tests/fixtures/B1/B1.lmn").bundle
result = run_bundle(bundle, services=services)

# 4. Inspect per-claim results
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

The JWT example plugin pack provides handlers for the B2 fixture case (JWT gateway authorization):

```python
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import run_bundle
from limnalis.plugins.jwt_example import register_jwt_plugins

# 1. Create registry and register JWT plugins
registry = PluginRegistry()
register_jwt_plugins(registry)

# 2. Build services
services = build_services_from_registry(registry)

# 3. Parse, normalize, and evaluate the B2 bundle
bundle = normalize_surface_file("tests/fixtures/B2/B2.lmn").bundle
result = run_bundle(bundle, services=services)

# 4. Check license results (B2 demonstrates license-level failure)
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

## Using the fixture plugin pack for conformance testing

The fixture plugin pack provides deterministic handlers backed by expected values from fixture cases. This is useful for conformance testing:

```python
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.api.conformance import load_corpus, compare_case, run_case
from limnalis.plugins.fixtures import register_fixture_plugins

# 1. Load the fixture corpus
corpus = load_corpus("tests/fixtures")

# 2. Run each case
for case in corpus:
    print(f"Running case: {case.id}")

    # Create a fresh registry for each case
    registry = PluginRegistry()
    extras = register_fixture_plugins(registry, case)
    services = build_services_from_registry(registry)
    services.update(extras)

    # Run and compare
    actual = run_case(case, services=services)
    comparison = compare_case(case, actual)

    if comparison.passed:
        print(f"  PASS")
    else:
        print(f"  FAIL: {comparison.differences}")
```

To load from the default corpus location:

```python
from limnalis.api.conformance import load_corpus_from_default

corpus = load_corpus_from_default()
```

## Combining multiple plugin packs

You can register handlers from multiple packs into a single registry, as long as there are no plugin ID conflicts:

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

```python
result = run_bundle(bundle, services=services)

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
