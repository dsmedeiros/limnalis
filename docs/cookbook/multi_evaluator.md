# Cookbook: Multi-Evaluator Bundles

## When to Use Multiple Evaluators

Multiple evaluators are useful when independent assessors must agree, different methodologies apply, or you need adjudicated resolution when evaluators disagree.

See `examples/governance_stack_bundle.lmn` for a complete working example.

## Key Elements

### 1. Declare evaluators with distinct roles

```
evaluator ev_auditor {
  kind institution;  role primary;
  binding test://eval/external_auditor;
}
evaluator ev_self {
  kind human;  role auxiliary;
  binding test://eval/self_assessment;
}
evaluator ev_auto {
  kind model;  role audit;
  binding test://eval/automated_checker;
}
```

### 2. Define a resolution policy

```
resolution_policy rp_adjudicated {
  kind adjudicated;
  members [ev_auditor, ev_self, ev_auto];
  binding test://resolution/compliance_adjudicator_v1;
}
```

The `kind` determines how disagreements resolve. See [How Evaluation Works](../how_evaluation_works.md) for policy kinds.

### 3. Write claims referencing evidence

```
local {
  c_access: access_control_adequate(system_1, policy_A) refs [e_audit, e_auto];
}
```

Each evaluator independently evaluates `c_access` (Phase 8). Phase 11 aggregates the results per the resolution policy.

## Running It

```bash
limnalis evaluate examples/governance_stack_bundle.lmn
```

To wire custom evaluator plugins programmatically, see the [Custom Plugin Cookbook](custom_plugin.md) and `examples/consumer_grid_b1.py`.
