# Limnalis Plugin SDK Overview

## What you'll need

- Python 3.11+
- Limnalis installed (`pip install limnalis` or `pip install -e ".[dev]"` for development)
- Familiarity with the Limnalis evaluation model (bundles, claims, evaluators, frames)

## Public vs internal modules

All stable, supported imports for extension authors live under `limnalis.api.*`:

| Module | Contents |
|---|---|
| `limnalis.api.plugins` | Phase protocols, `EvaluatorBindings`, `ExprHandler`, `PrimitiveSet` |
| `limnalis.api.context` | `StepContext`, `MachineState`, `EvaluationEnvironment`, `SessionConfig`, `StepConfig`, `ClaimClassification`, `ClaimEvidenceView`, `BaselineState`, `ResolutionStore` |
| `limnalis.api.results` | `TruthCore`, `SupportResult`, `EvalNode`, `LicenseResult`, `TransportResult`, `BlockResult`, `ClaimResult`, `StepResult`, `SessionResult`, `BundleResult`, `EvaluationResult` |
| `limnalis.api.models` | AST nodes: `BundleNode`, `ClaimNode`, `ExprNode`, expression types, `AdequacyAssessmentNode`, `BridgeNode`, `TransportNode` |
| `limnalis.api.services` | `PluginRegistry`, `PluginMetadata`, `build_services_from_registry`, kind constants |
| `limnalis.api.parser` | `LimnalisParser` |
| `limnalis.api.normalizer` | `Normalizer`, `NormalizationResult`, `normalize_surface_file`, `normalize_surface_text` |
| `limnalis.api.evaluator` | `run_bundle`, `run_session`, `run_step`, `PrimitiveSet` |
| `limnalis.api.conformance` | `FixtureCase`, `compare_case`, `load_corpus`, `run_case` |

Everything outside `limnalis.api.*` is internal and may change without notice between releases. Do not import from `limnalis.runtime`, `limnalis.models`, `limnalis.plugins`, or other internal packages directly.

## What is extensible

Limnalis evaluates bundles through a fixed 13-phase pipeline. Each phase has a default (builtin) implementation. Extension authors can replace or augment behavior at specific phases by registering plugin handlers.

**Extensible phases and their plugin kinds:**

| Phase | Primitive | Plugin kind | Typical use |
|---|---|---|---|
| 1 | resolve_ref | `BINDING_RESOLVER` | Custom reference resolution |
| 3 | resolve_baseline | `BASELINE_HANDLER` | Custom baseline initialization |
| 4 | evaluate_adequacy_set | `ADEQUACY_METHOD` | Domain-specific adequacy scoring |
| 5 | compose_license | (via adequacy results) | Driven by adequacy plugins |
| 6 | build_evidence_view | `EVIDENCE_POLICY` | Custom evidence synthesis |
| 8 | eval_expr | `EVALUATOR_BINDING` | Expression evaluation (most common) |
| 9 | synthesize_support | `EVIDENCE_POLICY` | Support synthesis from evidence |
| 11 | apply_resolution_policy | `ADJUDICATOR` | Multi-evaluator conflict resolution |
| 13 | execute_transport | `TRANSPORT_HANDLER` | Cross-frame transport execution |

**Not extensible:** The phase ordering itself, AST model definitions, normalization, and parsing are fixed. You cannot add new phases, reorder existing ones, or change the AST schema through plugins.

## Plugin kinds

Each plugin is registered under a **kind** that determines where in the pipeline it is used. Import kind constants from `limnalis.api.services`:

```python
from limnalis.api.services import (
    EVALUATOR_BINDING,    # "evaluator_binding"
    CRITERION_BINDING,    # "criterion_binding"
    EVIDENCE_POLICY,      # "evidence_policy"
    ADEQUACY_METHOD,      # "adequacy_method"
    ADJUDICATOR,          # "adjudicator"
    TRANSPORT_HANDLER,    # "transport_handler"
    BASELINE_HANDLER,     # "baseline_handler"
    BINDING_RESOLVER,     # "binding_resolver"
)
```

**`EVALUATOR_BINDING`** is the most common extension point. It maps an evaluator ID and expression type to a handler that produces a `TruthCore`. Plugin IDs use the format `"evaluator_id::expr_type"` (e.g., `"my_eval::predicate"`).

**`EVIDENCE_POLICY`** handlers control how evidence maps to support levels during support synthesis.

**`ADEQUACY_METHOD`** handlers score adequacy assessments referenced in anchor nodes.

**`ADJUDICATOR`** handlers resolve conflicts when multiple evaluators disagree.

**`CRITERION_BINDING`** handlers evaluate criterion references in `JudgedExpr` nodes.

**`TRANSPORT_HANDLER`**, **`BASELINE_HANDLER`**, and **`BINDING_RESOLVER`** cover less common extension points for cross-frame transport, baseline initialization, and custom reference resolution respectively.

## The plugin registry model

The `PluginRegistry` is a simple key-value store keyed by `(kind, plugin_id)` pairs. Each entry stores a handler callable plus optional metadata:

```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING

registry = PluginRegistry()

registry.register(
    EVALUATOR_BINDING,
    "my_eval::predicate",
    my_handler,
    version="1.0",
    description="My predicate evaluator",
)
```

Key operations:

- `registry.register(kind, plugin_id, handler, *, version="", description="")` -- register a handler; raises `PluginConflictError` on duplicate.
- `registry.get(kind, plugin_id)` -- retrieve a handler; raises `PluginNotFoundError` if missing.
- `registry.has(kind, plugin_id)` -- check existence without raising.
- `registry.list_plugins(kind=None)` -- list all registered plugins, optionally filtered by kind, in deterministic sorted order.
- `registry.unregister(kind, plugin_id)` -- remove a plugin.
- `registry.clear()` -- remove all plugins (useful in test teardown).

## Quick start: registering a simple evaluator binding

```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING
from limnalis.api.results import TruthCore


def my_predicate_handler(expr, claim, step_ctx, machine_state):
    """Evaluate predicate expressions for my domain."""
    return TruthCore(
        truth="T",
        reason="my_domain_check_passed",
        confidence=0.95,
        provenance=["my_eval_v1"],
    )


registry = PluginRegistry()
registry.register(
    EVALUATOR_BINDING,
    "my_eval::predicate",
    my_predicate_handler,
    description="My domain predicate handler",
)
```

## Wiring plugins into the runner with build_services_from_registry

Once you have registered all your plugins, use `build_services_from_registry()` to produce the services dict that `run_bundle`, `run_session`, and `run_step` expect:

```python
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.api.evaluator import run_bundle
from limnalis.api.normalizer import normalize_surface_file

# 1. Create and populate the registry
registry = PluginRegistry()
# ... register your plugins ...

# 2. Build services from the registry
services = build_services_from_registry(registry)

# 3. Parse, normalize, and evaluate
bundle = normalize_surface_file("my_bundle.lmn").bundle

result = run_bundle(bundle, services=services)
```

`build_services_from_registry` collects:

- **evaluator_bindings** -- wraps all `EVALUATOR_BINDING` plugins into a `RegistryEvaluatorBindings` adapter that dispatches `eval_expr` calls by `evaluator_id` and `expr_type`.
- **support_policy_handlers** -- collects all `EVIDENCE_POLICY` plugins into a dict keyed by plugin ID.
- **adequacy_handlers** -- collects all `ADEQUACY_METHOD` plugins into a dict keyed by plugin ID (the method URI).

## Organizing plugins into packs

For real-world use, group related handlers into a registration function:

```python
def register_my_domain_plugins(registry):
    """Register all plugins for my domain."""
    from limnalis.api.services import EVALUATOR_BINDING, EVIDENCE_POLICY

    registry.register(EVALUATOR_BINDING, "my_eval::predicate", my_predicate_handler)
    registry.register(EVALUATOR_BINDING, "my_eval::causal", my_causal_handler)
    registry.register(EVIDENCE_POLICY, "my://policy/support_v1", my_support_policy)
```

See the bundled examples for reference:

- `limnalis.plugins.grid_example` -- Grid/power domain (B1 fixture case)
- `limnalis.plugins.jwt_example` -- JWT/auth domain (B2 fixture case)
- `limnalis.plugins.fixtures` -- Fixture-backed conformance plugins

## Next steps

- [Writing an evaluator binding](writing_an_evaluator_binding.md) -- the most common extension point
- [Writing a criterion binding](writing_a_criterion_binding.md) -- for JudgedExpr criterion evaluation
- [Writing an adequacy method](writing_an_adequacy_method.md) -- for domain-specific adequacy scoring
- [Writing a transport handler](writing_a_transport_handler.md) -- for cross-frame transport
- [Downstream usage examples](downstream_usage_examples.md) -- parse, normalize, evaluate cookbook
