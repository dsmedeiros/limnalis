# Cookbook: Writing a Custom Plugin

## Plugin Kinds

Limnalis supports eight plugin kinds. The most common is `EVALUATOR_BINDING` (Phase 8).

| Kind | Purpose |
|------|---------|
| `EVALUATOR_BINDING` | Evaluate claim expressions (most common) |
| `CRITERION_BINDING` | Evaluate criterion refs in `JudgedExpr` |
| `EVIDENCE_POLICY` | Control evidence-to-support synthesis |
| `ADEQUACY_METHOD` | Domain-specific adequacy scoring |
| `ADJUDICATOR` | Multi-evaluator conflict resolution |
| `TRANSPORT_HANDLER` | Cross-frame transport execution |
| `BASELINE_HANDLER` | Custom baseline initialization |
| `BINDING_RESOLVER` | Custom reference resolution |

## Step-by-Step: Evaluator Binding

### 1. Write a handler

```python
from limnalis.api.results import TruthCore

def my_predicate_handler(expr, claim, step_ctx, machine_state):
    return TruthCore(
        truth="T", reason="my_check_passed",
        confidence=0.9, provenance=["my_plugin_v1"],
    )
```

See `src/limnalis/plugins/grid_example.py` for a working reference.

### 2. Register the handler

```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING

registry = PluginRegistry()
registry.register(EVALUATOR_BINDING, "my_eval::predicate", my_predicate_handler)
```

The plugin ID follows the `"evaluator_id::expr_type"` convention.

### 3. Wire into the runner

```python
from limnalis.api.services import build_services_from_registry
from limnalis.api.evaluator import run_bundle
from limnalis.api.normalizer import normalize_surface_file

services = build_services_from_registry(registry)
result = run_bundle(normalize_surface_file("my_bundle.lmn").bundle, services=services)
```

### 4. Organize as a plugin pack

```python
def register_my_plugins(registry):
    from limnalis.api.services import EVALUATOR_BINDING
    registry.register(EVALUATOR_BINDING, "my_eval::predicate", my_predicate_handler)
    registry.register(EVALUATOR_BINDING, "my_eval::causal", my_causal_handler)
```

See `examples/consumer_grid_b1.py` for a complete example with plugin registration and conformance.

## Further Reading

- [Plugin SDK Overview](../plugin_sdk_overview.md) -- full API reference
- [Writing an Evaluator Binding](../writing_an_evaluator_binding.md) -- deep dive
- [Writing an Adequacy Method](../writing_an_adequacy_method.md) -- adequacy scoring
