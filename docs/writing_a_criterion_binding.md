# Writing a Criterion Binding

Criterion bindings handle `JudgedExprNode` evaluation, where an inner expression is qualified by a criterion reference. This is the mechanism for policy-bound evaluation -- the criterion determines the standard against which the inner expression is judged.

## What you'll need

- A `PluginRegistry` instance
- Understanding of `JudgedExprNode` structure
- Familiarity with `TruthCore` (the return type)

## JudgedExprNode structure

A `JudgedExprNode` wraps an inner expression with a criterion reference:

```python
from limnalis.api.models import JudgedExprNode

# JudgedExprNode fields:
#   expr: ExprNode          -- the inner expression being judged
#   criterionRef: str       -- reference to the criterion (e.g., "auth_access_v3")
```

In surface syntax, this appears as:

```
access_allowed(tok_A) judged_by auth_access_v3
```

The `expr` field contains the inner expression (here, a `PredicateExprNode` for `access_allowed(tok_A)`), and `criterionRef` is the string `"auth_access_v3"`.

## Handler signature

A criterion binding handler has the same signature as an evaluator binding handler:

```python
def my_criterion_handler(expr, claim, step_ctx, machine_state) -> TruthCore:
    ...
```

The `expr` parameter will be a `JudgedExprNode`. Your handler should:

1. Inspect `expr.criterionRef` to determine which criterion applies.
2. Optionally inspect `expr.expr` (the inner expression) for additional context.
3. Return a `TruthCore` reflecting the criterion evaluation.

## Registering as CRITERION_BINDING

Register criterion bindings using the `CRITERION_BINDING` kind:

```python
from limnalis.api.services import PluginRegistry, CRITERION_BINDING

registry = PluginRegistry()
registry.register(
    CRITERION_BINDING,
    "my_criterion_id",
    my_criterion_handler,
    description="My criterion handler",
)
```

When the expression type is `"judged"`, the runner dispatches to evaluator bindings registered as `"evaluator_id::judged"`. The handler receives the full `JudgedExprNode` and can inspect the criterion reference to determine evaluation logic.

```python
from limnalis.api.services import EVALUATOR_BINDING

registry.register(
    EVALUATOR_BINDING,
    "my_eval::judged",
    my_judged_handler,
    description="Judged expression handler for my evaluator",
)
```

## Example: policy-based authorization criterion

This handler evaluates judged expressions against an authorization policy:

```python
from limnalis.api.services import PluginRegistry, EVALUATOR_BINDING
from limnalis.api.results import TruthCore


# Known authorization policies and their rules
AUTHORIZATION_POLICIES = {
    "auth_access_v3": {
        "description": "JWT access authorization policy v3",
        "required_predicates": ["sig_valid", "token_not_expired"],
    },
    "auth_revocation_v1": {
        "description": "Token revocation check policy",
        "required_predicates": ["revocation_immediate"],
    },
}


def auth_judged_handler(expr, claim, step_ctx, machine_state):
    """Evaluate judged expressions against authorization policies.

    Checks that the criterion reference maps to a known policy,
    then evaluates the inner expression accordingly.
    """
    criterion = expr.criterionRef

    if criterion not in AUTHORIZATION_POLICIES:
        return TruthCore(
            truth="N",
            reason=f"unknown_criterion:{criterion}",
            provenance=["auth_eval"],
        )

    policy = AUTHORIZATION_POLICIES[criterion]

    # The inner expression has already been evaluated by the predicate handler.
    # The judged handler adds the policy-level judgment.
    return TruthCore(
        truth="T",
        reason="policy_satisfied",
        confidence=1.0,
        provenance=["auth_eval", criterion],
    )


registry = PluginRegistry()
registry.register(
    EVALUATOR_BINDING,
    "ev_gateway::judged",
    auth_judged_handler,
    description="JWT authorization judged expression handler",
)
```

## Relationship to evaluator bindings

Criterion bindings and evaluator bindings work together:

1. The bundle declares evaluators (e.g., `ev_gateway`) with bindings to claims.
2. Claims contain expressions -- some may be `JudgedExprNode` types.
3. When the runner encounters a judged expression for an evaluator, it looks up the `"evaluator_id::judged"` binding.
4. Your handler receives the full `JudgedExprNode`, including both the inner expression and the criterion reference.

If you need the `CRITERION_BINDING` kind for standalone criterion lookup (outside the evaluator dispatch path), register it separately:

```python
from limnalis.api.services import CRITERION_BINDING

registry.register(
    CRITERION_BINDING,
    "auth_access_v3",
    auth_criterion_lookup,
    description="Standalone criterion handler for auth_access_v3",
)
```

## Next steps

- [Writing an evaluator binding](writing_an_evaluator_binding.md) -- the general evaluator binding guide
- [Writing an adequacy method](writing_an_adequacy_method.md) -- for domain-specific adequacy scoring
- [Plugin SDK overview](plugin_sdk_overview.md) -- registry model and full API surface
