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

<!-- doc-snippet: setup -->
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

<!-- doc-snippet: setup -->
```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING

registry = PluginRegistry()
registry.register(EVALUATOR_BINDING, "my_eval::predicate", my_predicate_handler)
```

The plugin ID follows the `"evaluator_id::expr_type"` convention: the handler is consulted for claims assigned to the evaluator whose `id` matches the part before `::`.

### 3. Wire into the runner

`run_bundle` takes the normalized bundle (`NormalizationResult.canonical_ast`), the sessions to execute, and the evaluation environment; the registry's handlers ride along in `services`:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.services import build_services_from_registry
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)
from limnalis.api.normalizer import normalize_surface_file

services = build_services_from_registry(registry)
bundle = normalize_surface_file("examples/minimal_bundle.lmn").canonical_ast

env = EvaluationEnvironment()
sessions = [SessionConfig(id="s1", steps=[StepConfig(id="step1")])]
result = run_bundle(bundle, sessions, env, services=services)
```

### 4. Organize as a plugin pack

<!-- doc-snippet: runnable -->
```python
def register_my_plugins(registry):
    from limnalis.api.services import EVALUATOR_BINDING
    registry.register(EVALUATOR_BINDING, "my_eval::predicate", my_predicate_handler)
    registry.register(EVALUATOR_BINDING, "my_eval::causal", my_causal_handler)
```

For complete working examples: `examples/consumer_grid_b1.py` shows plugin-pack registration and then runs case B1 through the conformance harness (`run_case`/`compare_case`, not `run_bundle`); the ["Running B1 with the grid plugin pack"](../downstream_usage_examples.md#running-b1-with-the-grid-plugin-pack) section of the downstream usage examples shows the same plugin pack wired directly into `run_bundle`.

## Further Reading

- [Plugin SDK Overview](../plugin_sdk_overview.md) -- full API reference
- [Writing an Evaluator Binding](../writing_an_evaluator_binding.md) -- deep dive
- [Writing an Adequacy Method](../writing_an_adequacy_method.md) -- adequacy scoring
