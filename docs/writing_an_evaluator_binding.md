# Writing an Evaluator Binding

Evaluator bindings are the most common Limnalis extension point. They implement the `eval_expr` phase (phase 8), where expressions within claims are evaluated to produce a truth value.

## What you'll need

- A `PluginRegistry` instance
- Knowledge of which evaluator IDs and expression types your bundle declares
- Familiarity with `TruthCore` (the return type)

## Handler signature

Every evaluator binding handler has the same signature:

```python
def my_handler(expr, claim, step_ctx, machine_state) -> TruthCore:
    ...
```

| Parameter | Type | Description |
|---|---|---|
| `expr` | Expression node (e.g., `PredicateExprNode`, `CausalExprNode`) | The expression to evaluate |
| `claim` | `ClaimNode` | The claim containing the expression |
| `step_ctx` | `StepContext` or `None` | Effective frame, time, and history for the current step |
| `machine_state` | `MachineState` | Accumulated state: baselines, adequacy, license, evidence, transport stores |

The return value must be a `TruthCore`:

```python
from limnalis.api.results import TruthCore

TruthCore(
    truth="T",         # Required. One of: "T" (true), "F" (false), "B" (both), "N" (neither)
    reason="...",      # Optional. Human-readable reason string
    confidence=0.95,   # Optional. Float in [0.0, 1.0]
    provenance=["..."],  # Optional. List of provenance tags for traceability
)
```

## Expression types

The runner dispatches to your handler based on the evaluator ID declared in the bundle and the expression type of the claim. The expression types you may encounter:

| Expression type | Node class | Dispatch key | Description |
|---|---|---|---|
| Predicate | `PredicateExprNode` | `"predicate"` | Simple predicate with name and args |
| Causal | `CausalExprNode` | `"causal"` | Causal claim with lhs, rhs, mode (obs/do) |
| Emergence | `EmergenceExprNode` | `"emergence"` | Emergent property with onset/persist/dissolve |
| Dynamic | `DynamicExprNode` | `"dynamic"` | Dynamic behavior (approaches, diverges, etc.) |
| Judged (inner) | `JudgedExprNode` | `"judged"` | Expression with criterion reference |
| Criterion | `CriterionExprNode` | `"criterion"` | Criterion-bound evaluation |

## How to register

Plugin IDs for evaluator bindings use the format `"evaluator_id::expr_type"`:

```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING

registry = PluginRegistry()
registry.register(
    EVALUATOR_BINDING,
    "my_eval::predicate",      # evaluator_id::expr_type
    my_predicate_handler,
    description="My predicate evaluator",
)
```

The `evaluator_id` must match the evaluator ID declared in your bundle's evaluator nodes. The `expr_type` must match the expression kind of the claims assigned to that evaluator.

## What context is available

### StepContext

The `step_ctx` parameter provides the effective evaluation context for the current step:

```python
step_ctx.effective_frame    # FrameNode or FramePatternNode -- the active frame
step_ctx.effective_time     # TimeCtxNode or None -- the active time context
step_ctx.effective_history  # dict -- history bindings
step_ctx.diagnostics        # list[dict] -- accumulated diagnostics
```

### MachineState

The `machine_state` parameter provides the accumulated state across the evaluation:

```python
machine_state.resolution_store   # ResolutionStore -- previous resolution results
machine_state.baseline_store     # dict[str, BaselineState] -- resolved baselines
machine_state.adequacy_store     # dict -- adequacy evaluation results
machine_state.license_store      # dict -- license composition results
machine_state.evidence_views     # dict[str, ClaimEvidenceView] -- per-claim evidence
machine_state.transport_store    # dict[str, TransportResult] -- transport results
machine_state.diagnostics        # list[dict] -- accumulated diagnostics
```

## Example: minimal predicate handler

A predicate handler that checks a simple property:

```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING
from limnalis.api.results import TruthCore


def voltage_predicate_handler(expr, claim, step_ctx, machine_state):
    """Evaluate voltage-related predicates."""
    name = expr.name  # e.g., "overload", "undervoltage"

    if name == "overload":
        return TruthCore(
            truth="T",
            reason="line_overloaded",
            confidence=1.0,
            provenance=["voltage_eval_v1"],
        )

    # Unknown predicate -- return N (neither true nor false)
    return TruthCore(
        truth="N",
        reason=f"unrecognized_predicate:{name}",
        provenance=["voltage_eval_v1"],
    )


registry = PluginRegistry()
registry.register(
    EVALUATOR_BINDING,
    "ev_voltage::predicate",
    voltage_predicate_handler,
)
```

## Example: causal handler with evidence inspection

A causal handler that inspects the evidence view to detect conflicts:

```python
from limnalis.api.results import TruthCore


def sensor_causal_handler(expr, claim, step_ctx, machine_state):
    """Evaluate causal claims using sensor evidence."""
    claim_id = claim.id
    evidence_view = machine_state.evidence_views.get(claim_id)

    # Check for evidence conflicts
    if evidence_view and evidence_view.cross_conflict_score is not None:
        if evidence_view.cross_conflict_score > 0.5:
            return TruthCore(
                truth="B",
                reason="source_conflict",
                confidence=1.0 - evidence_view.cross_conflict_score,
                provenance=["sensor_eval", "conflict_detected"],
            )

    # Evaluate causal mode
    mode = expr.mode  # "obs" or "do"
    if mode == "obs":
        return TruthCore(
            truth="T",
            reason="observational_causation_confirmed",
            confidence=0.85,
            provenance=["sensor_eval"],
        )

    return TruthCore(
        truth="N",
        reason="interventional_not_supported",
        provenance=["sensor_eval"],
    )
```

Register it alongside the predicate handler:

```python
from limnalis.api.services import EVALUATOR_BINDING

registry.register(EVALUATOR_BINDING, "ev_sensor::causal", sensor_causal_handler)
```

## Determinism

Evaluator bindings should be deterministic: given the same inputs, they must produce the same output. This is a critical invariant of the Limnalis evaluation model.

Guidelines:

- Do not use random number generators or system clock in handlers.
- If your handler depends on external state (databases, APIs), cache the results and ensure reproducibility.
- The `provenance` field should trace back to the data sources used, enabling audit.
- The runner executes evaluators in a deterministic order (sorted by evaluator ID). Your handler should not depend on evaluation order of other claims.

## Next steps

- [Writing a criterion binding](writing_a_criterion_binding.md) -- for JudgedExpr criterion evaluation
- [Writing an adequacy method](writing_an_adequacy_method.md) -- for domain-specific adequacy scoring
- [Plugin SDK overview](plugin_sdk_overview.md) -- registry model and full API surface
- [Downstream usage examples](downstream_usage_examples.md) -- wiring plugins into a full evaluation run
