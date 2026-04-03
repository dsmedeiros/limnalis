# How to Read Limnalis

## For Architects

**Bundle structure** -- a bundle contains a frame (evaluation context), evaluators (with kind, role, binding), claim blocks by stratum (`local`, `systemic`, `meta`), and optional evidence, anchors, bridges, and resolution policies.

**Frame semantics** -- frames set the epistemic boundary. Claims are evaluated within their frame. Transport via bridges is required to move truth across frames. See `examples/cwt_transport_bundle.lmn`.

**Evaluator composition** -- multiple evaluators assess claims independently; a resolution policy aggregates results. See the [Multi-Evaluator Cookbook](cookbook/multi_evaluator.md).

## For Plugin Authors

**Extension points** -- eight plugin kinds map to pipeline phases. The most common is `EVALUATOR_BINDING` (Phase 8). See the [Plugin SDK Overview](plugin_sdk_overview.md).

**The 13 primitives** -- defaults live in `limnalis.runtime.builtins`. Replace them via `PluginRegistry` and `build_services_from_registry`. See the [Custom Plugin Cookbook](cookbook/custom_plugin.md).

**Binding patterns** -- evaluator bindings use `"evaluator_id::expr_type"`. Plugin packs group handlers in `register_*` functions. Reference: `src/limnalis/plugins/grid_example.py`, `src/limnalis/plugins/jwt_example.py`.

## For Governance Reviewers

**What to look for:**

1. **Claim strata** -- local claims should be frame-specific; systemic claims address cross-cutting concerns; meta claims are annotations only
2. **Evaluator coverage** -- does each claim have a capable evaluator?
3. **Resolution policy** -- is the policy appropriate when evaluators disagree?

**Evidence quality** -- check `completeness` (0-1), `internal_conflict` (lower is better), `evidence_relation` entries for conflicts, and `refs` on claims.

**Adequacy** -- review `score >= threshold` in adequacy blocks, the `basis` list grounding each assessment, and `joint_adequacy` blocks. See the [Adequacy Execution Guide](adequacy_execution_guide.md).
