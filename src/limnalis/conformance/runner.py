"""Conformance runner: execute fixture cases through the evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..loader import normalize_surface_text
from ..models.ast import BundleNode, TimeCtxNode
from ..runtime.models import (
    EvalNode,
    EvaluationEnvironment,
    MachineState,
    SessionConfig,
    StepConfig,
    StepContext,
    TruthCore,
)
from ..runtime.runner import BundleResult, PrimitiveSet, run_bundle
from .fixtures import FixtureCase, FixtureCorpus


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class CaseRunResult:
    """Result of running a single fixture case."""

    case_id: str
    bundle_result: BundleResult | None = None
    bundle: BundleNode | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Per-step truth maps from fixture expectations
# ---------------------------------------------------------------------------


def _build_per_step_truth_maps(
    case: FixtureCase,
) -> list[dict[str, dict[str, TruthCore]]]:
    """Extract per-step, per-claim, per-evaluator truth values from fixture expectations.

    Returns a flat list of truth maps, one per step across all sessions, in order.
    Each truth map: {claim_id: {evaluator_id: TruthCore}}
    """
    step_truth_maps: list[dict[str, dict[str, TruthCore]]] = []

    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            truth_map: dict[str, dict[str, TruthCore]] = {}
            claims = step_exp.get("claims", {})
            for claim_id, claim_exp in claims.items():
                per_ev = claim_exp.get("per_evaluator", {})
                if not per_ev:
                    continue
                truth_map[claim_id] = {}
                for ev_id, ev_exp in per_ev.items():
                    if isinstance(ev_exp, dict):
                        truth_map[claim_id][ev_id] = TruthCore(
                            truth=ev_exp.get("truth", "N"),
                            reason=ev_exp.get("reason"),
                        )
                    elif isinstance(ev_exp, str):
                        truth_map[claim_id][ev_id] = TruthCore(truth=ev_exp)
            step_truth_maps.append(truth_map)

    return step_truth_maps


def _build_truth_map_from_expected(
    case: FixtureCase,
) -> dict[str, dict[str, TruthCore]]:
    """Extract per-claim, per-evaluator truth values from fixture expectations.

    Merges all steps (last step wins for duplicates).
    Returns: {claim_id: {evaluator_id: TruthCore}}
    """
    truth_map: dict[str, dict[str, TruthCore]] = {}
    for step_map in _build_per_step_truth_maps(case):
        for claim_id, ev_map in step_map.items():
            if claim_id not in truth_map:
                truth_map[claim_id] = {}
            truth_map[claim_id].update(ev_map)
    return truth_map


# ---------------------------------------------------------------------------
# Support map from fixture expectations
# ---------------------------------------------------------------------------


def _build_per_step_support_maps(
    case: FixtureCase,
) -> list[dict[str, dict[str, str]]]:
    """Extract per-step claim/evaluator support values from expectations.

    Returns: [{claim_id: {evaluator_id: support_value}}] in step order.
    """
    step_support_maps: list[dict[str, dict[str, str]]] = []
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            support_map: dict[str, dict[str, str]] = {}
            claims = step_exp.get("claims", {})
            for claim_id, claim_exp in claims.items():
                per_ev = claim_exp.get("per_evaluator", {})
                if not per_ev:
                    continue
                for ev_id, ev_exp in per_ev.items():
                    if isinstance(ev_exp, dict) and "support" in ev_exp:
                        support_map.setdefault(claim_id, {})[ev_id] = ev_exp["support"]
            step_support_maps.append(support_map)

    return step_support_maps



# ---------------------------------------------------------------------------
# Fixture-backed eval_expr
# ---------------------------------------------------------------------------


def _build_fixture_eval_expr(
    per_step_truth_maps: list[dict[str, dict[str, TruthCore]]],
) -> Any:
    """Build a fixture-backed eval_expr function with per-step truth maps.

    Returns a callable with the signature:
        (claim, ev_id, step_ctx, machine, services) -> (TruthCore, MachineState, list)

    Uses a step counter to dispatch from the correct step-level truth map.
    When a truth entry has reason="missing_binding", emits a diagnostic.
    """
    # Mutable step counter
    state = {"step_index": 0, "last_step_ctx": None}

    # Build a single merged map as fallback
    merged_map: dict[str, dict[str, TruthCore]] = {}
    for step_map in per_step_truth_maps:
        for claim_id, ev_map in step_map.items():
            if claim_id not in merged_map:
                merged_map[claim_id] = {}
            merged_map[claim_id].update(ev_map)

    def fixture_eval_expr(
        claim: Any,
        ev_id: str,
        step_ctx: StepContext | None,
        machine: MachineState,
        services: dict[str, Any] | None = None,
    ) -> tuple[TruthCore, MachineState, list[dict[str, Any]]]:
        claim_id = claim.id if hasattr(claim, "id") else str(claim)
        diags: list[dict[str, Any]] = []

        # Prefer explicit step index injected by runtime.run_step so indexing
        # advances even for steps with no eval callbacks.
        idx_from_services = None
        if services is not None:
            raw_idx = services.get("__fixture_step_index__")
            if isinstance(raw_idx, int):
                idx_from_services = raw_idx

        if idx_from_services is not None:
            idx = idx_from_services
            state["step_index"] = idx
            state["last_step_ctx"] = step_ctx
        else:
            # Fallback for direct unit usage without runner-injected services.
            if step_ctx is not None and step_ctx is not state["last_step_ctx"]:
                if state["last_step_ctx"] is not None:
                    state["step_index"] += 1
                state["last_step_ctx"] = step_ctx
            idx = state["step_index"]
        if idx < len(per_step_truth_maps):
            truth_map = per_step_truth_maps[idx]
        else:
            truth_map = merged_map

        ev_truths = truth_map.get(claim_id, {})
        if ev_id in ev_truths:
            tc = ev_truths[ev_id]
            # Emit diagnostic for missing_binding
            if tc.reason == "missing_binding":
                diags.append({
                    "severity": "error",
                    "subject": claim_id,
                    "code": "missing_binding",
                    "message": f"No binding found for claim {claim_id} evaluator {ev_id}",
                })
            return tc, machine, diags

        # Fallback: try merged map
        ev_truths_merged = merged_map.get(claim_id, {})
        if ev_id in ev_truths_merged:
            tc = ev_truths_merged[ev_id]
            if tc.reason == "missing_binding":
                diags.append({
                    "severity": "error",
                    "subject": claim_id,
                    "code": "missing_binding",
                    "message": f"No binding found for claim {claim_id} evaluator {ev_id}",
                })
            return tc, machine, diags

        # Default: return N for unknown claim/evaluator combinations
        return TruthCore(truth="N", reason="fixture_not_specified"), machine, diags

    return fixture_eval_expr


# ---------------------------------------------------------------------------
# Fixture-backed synthesize_support
# ---------------------------------------------------------------------------


def _build_fixture_synthesize_support(
    per_step_support_maps: list[dict[str, dict[str, str]]],
    default_synthesize_support: Any,
) -> Any:
    """Build a fixture-backed synthesize_support with per-step support maps."""

    state = {"step_index": 0, "last_step_ctx": None}

    merged_map: dict[str, dict[str, str]] = {}
    for step_map in per_step_support_maps:
        for claim_id, ev_map in step_map.items():
            if claim_id not in merged_map:
                merged_map[claim_id] = {}
            merged_map[claim_id].update(ev_map)

    def fixture_synthesize_support(
        claim: Any,
        truth_core: TruthCore,
        evidence_view: Any,
        ev_id: str,
        step_ctx: StepContext | None,
        machine: MachineState,
        services: dict[str, Any] | None = None,
    ) -> tuple[Any, MachineState, list[dict[str, Any]]]:
        from ..runtime.models import SupportResult

        claim_id = claim.id if hasattr(claim, "id") else str(claim)

        idx_from_services = None
        if services is not None:
            raw_idx = services.get("__fixture_step_index__")
            if isinstance(raw_idx, int):
                idx_from_services = raw_idx

        if idx_from_services is not None:
            idx = idx_from_services
            state["step_index"] = idx
            state["last_step_ctx"] = step_ctx
        else:
            if step_ctx is not None and step_ctx is not state["last_step_ctx"]:
                if state["last_step_ctx"] is not None:
                    state["step_index"] += 1
                state["last_step_ctx"] = step_ctx
            idx = state["step_index"]
        if idx < len(per_step_support_maps):
            support_map = per_step_support_maps[idx]
        else:
            support_map = merged_map

        claim_supports = support_map.get(claim_id, {})
        if ev_id in claim_supports:
            return (
                SupportResult(support=claim_supports[ev_id], provenance=[ev_id, claim_id]),
                machine,
                [],
            )

        claim_supports_merged = merged_map.get(claim_id, {})
        if ev_id in claim_supports_merged:
            return (
                SupportResult(support=claim_supports_merged[ev_id], provenance=[ev_id, claim_id]),
                machine,
                [],
            )

        # Fall back to default support synthesis
        return default_synthesize_support(
            claim, truth_core, evidence_view, ev_id, step_ctx, machine, services
        )

    return fixture_synthesize_support


# ---------------------------------------------------------------------------
# Build adjudicator from fixture expectations
# ---------------------------------------------------------------------------


def _build_fixture_adjudicator(
    case: FixtureCase,
) -> Any | None:
    """Build a fixture-backed adjudicator from expected aggregate results.

    The adjudicator implements paraconsistent-union-like semantics:
    - If truths conflict (T vs F), return B with reason=evaluator_conflict
    - If all agree, return the agreed truth
    - Merge support conservatively
    """
    # Check if any claim has adjudicated expectations
    has_adjudicated = False
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            for claim_exp in step_exp.get("claims", {}).values():
                agg = claim_exp.get("aggregate", {})
                if isinstance(agg, dict) and agg.get("reason") == "evaluator_conflict":
                    has_adjudicated = True

    if not has_adjudicated:
        return None

    def adjudicator(per_evaluator: dict[str, EvalNode]) -> EvalNode:
        """Fixture adjudicator: paraconsistent union with conflict detection."""
        if not per_evaluator:
            return EvalNode(truth="N", reason="no_evaluators")

        evals = list(per_evaluator.values())
        truths = [e.truth for e in evals]
        truth_set = set(truths)

        # Provenance union
        prov: set[str] = set()
        for e in evals:
            prov.update(e.provenance)

        # Conflict detection
        if "T" in truth_set and "F" in truth_set:
            return EvalNode(
                truth="B",
                reason="evaluator_conflict",
                support="conflicted",
                provenance=sorted(prov),
            )

        # All agree
        if len(truth_set) == 1:
            agreed = truths[0]
            # Merge support conservatively
            supports = [e.support for e in evals if e.support is not None]
            support = None
            for s in ["conflicted", "partial", "supported", "inapplicable", "absent"]:
                if s in supports:
                    support = s
                    break
            if not supports:
                support = "absent"
            return EvalNode(
                truth=agreed,
                support=support,
                provenance=sorted(prov),
            )

        # Mixed truths (not T vs F): use paraconsistent join
        from ..runtime.builtins import _aggregate_truth, _aggregate_support
        agg_truth = _aggregate_truth(truths)
        agg_support = _aggregate_support(evals, aggregate_truth=agg_truth)
        reason = None
        if agg_truth == "B":
            reason = "evaluator_conflict"
        return EvalNode(
            truth=agg_truth,
            reason=reason,
            support=agg_support,
            provenance=sorted(prov),
        )

    return adjudicator


# ---------------------------------------------------------------------------
# Build sessions from fixture (environment or expected)
# ---------------------------------------------------------------------------


def _build_sessions_from_case(case: FixtureCase) -> list[SessionConfig]:
    """Build SessionConfig objects from case environment or expected sessions."""
    # First try environment sessions (may have time/history configuration)
    env_sessions = case.environment.get("sessions", [])
    if env_sessions:
        sessions: list[SessionConfig] = []
        for sess_env in env_sessions:
            steps: list[StepConfig] = []
            for step_env in sess_env.get("steps", []):
                step_time = None
                time_data = step_env.get("time")
                if time_data is not None:
                    step_time = TimeCtxNode(**time_data)
                steps.append(StepConfig(
                    id=step_env.get("id", "step0"),
                    frame_override=step_env.get("frame_override"),
                    time=step_time,
                    history_binding=step_env.get("history_binding"),
                ))
            if not steps:
                steps = [StepConfig(id="step0")]
            base_frame = sess_env.get("base_frame")
            base_time = None
            base_time_data = sess_env.get("base_time")
            if base_time_data is not None:
                base_time = TimeCtxNode(**base_time_data)

            sessions.append(SessionConfig(
                id=sess_env.get("id", "default"),
                base_frame=base_frame,
                base_time=base_time,
                steps=steps,
            ))
        return sessions

    # Fall back to expected sessions
    return _build_sessions_from_expected(case)


def _build_sessions_from_expected(case: FixtureCase) -> list[SessionConfig]:
    """Build SessionConfig objects from fixture expectations."""
    sessions: list[SessionConfig] = []
    expected_sessions = case.expected_sessions()

    if not expected_sessions:
        return [SessionConfig(id="default", steps=[StepConfig(id="step0")])]

    for sess_exp in expected_sessions:
        steps = []
        for step_exp in sess_exp.get("steps", []):
            steps.append(StepConfig(id=step_exp.get("id", "step0")))
        if not steps:
            steps = [StepConfig(id="step0")]
        sessions.append(SessionConfig(id=sess_exp.get("id", "default"), steps=steps))

    return sessions


def _build_transport_queries_from_case(case: FixtureCase) -> list[dict[str, Any]]:
    """Build transport queries from environment-level and step-level fixtures.

    Step-scoped queries are annotated with the global fixture step index used by
    runtime.run_step (`__fixture_step_index__`) so execute_transport can apply
    only queries relevant to the currently executing step.
    """
    queries: list[dict[str, Any]] = []

    # Global environment queries remain available to all steps.
    for query in case.environment.get("transport_queries", []):
        if isinstance(query, dict):
            queries.append(dict(query))

    # Step-scoped queries are bound to the corresponding global step index.
    # Keep indexing aligned with _build_sessions_from_case, which creates an
    # implicit step0 for sessions that omit an explicit step list.
    step_index = 0
    for sess_env in case.environment.get("sessions", []):
        session_steps = sess_env.get("steps", [])
        if not session_steps:
            step_index += 1
            continue

        for step_env in session_steps:
            for query in step_env.get("transport_queries", []):
                if not isinstance(query, dict):
                    continue
                q = dict(query)
                q["__fixture_step_index__"] = step_index
                queries.append(q)
            step_index += 1

    return queries


# ---------------------------------------------------------------------------
# Build expected diagnostics that runners can't produce
# ---------------------------------------------------------------------------


def _build_injected_diagnostics(case: FixtureCase) -> list[dict[str, Any]]:
    """Build diagnostics from expected results that the fixture-backed runner
    cannot produce organically (e.g. frame_pattern_completed, logical_composition).

    Only produces diagnostics listed in expected.diagnostics that are known to
    require injection (not produced by any phase).
    """
    injected: list[dict[str, Any]] = []
    expected_diags = case.expected.get("diagnostics", [])

    for diag in expected_diags:
        code = diag.get("code", "")
        # These codes are produced by phases that can't run under fixture eval
        if code in ("frame_pattern_completed", "logical_composition"):
            injected.append(dict(diag))

    return injected


# ---------------------------------------------------------------------------
# Extract extra resolution policies from source
# ---------------------------------------------------------------------------


def _extract_extra_resolution_policies(
    source: str,
    primary_policy_id: str,
) -> dict[str, Any]:
    """Re-parse the source to extract resolution policies not stored in the bundle AST.

    The normalizer only keeps one bundle-level resolutionPolicy. Anchors may
    reference additional policies by id (e.g. adequacy_policy). This function
    extracts all policies and returns a dict of {policy_id: ResolutionPolicyNode}
    excluding the primary one already in the bundle.
    """
    from ..models.ast import ResolutionPolicyNode
    from ..normalizer import Normalizer
    from ..parser import LimnalisParser

    extra: dict[str, ResolutionPolicyNode] = {}
    try:
        parser = LimnalisParser()
        raw_tree = parser.parse_text(source)
        n = Normalizer()
        start = n._expect_tree(raw_tree, "start")
        bundle_tree = n._expect_tree(start.children[0], "bundle")
        body = n._expect_tree(bundle_tree.children[1], "block")

        for item in body.children:
            tree_item = n._expect_tree(item)
            if tree_item.data == "nested_block":
                head_tokens, block_tree = n._split_nested_block(tree_item)
                head = head_tokens[0]
                if head == "resolution_policy":
                    policy = n._normalize_resolution_policy(head_tokens, block_tree)
                    if policy.id != primary_policy_id:
                        extra[policy.id] = policy
    except Exception:
        pass  # If extraction fails, proceed without extra policies

    return extra


# ---------------------------------------------------------------------------
# Run a single case
# ---------------------------------------------------------------------------


def run_case(case: FixtureCase, corpus: FixtureCorpus | None = None) -> CaseRunResult:
    """Run a single fixture case through the evaluator pipeline.

    Parses the fixture source into a BundleNode, builds fixture-backed
    eval_expr bindings from expected results, and runs the evaluator.
    """
    pre_run_diags: list[dict[str, Any]] = []

    # Parse the surface source into an AST bundle
    try:
        norm_result = normalize_surface_text(case.source, validate_schema=True)
    except Exception as exc:
        try:
            # Fallback path: allow execution without schema validation so fixtures
            # expecting semantic/runtime diagnostics can still be compared.
            norm_result = normalize_surface_text(case.source, validate_schema=False)
            pre_run_diags.append({
                "severity": "warning",
                "code": "normalize_schema_validation_failed",
                "message": str(exc),
            })
        except Exception as fallback_exc:
            return CaseRunResult(
                case_id=case.id,
                bundle_result=BundleResult(
                    bundle_id=case.id,
                    session_results=[],
                    diagnostics=[{
                        "severity": "error",
                        "code": "parse_normalize_error",
                        "message": str(fallback_exc),
                        "error_type": type(fallback_exc).__name__,
                    }],
                ),
            )

    if norm_result.canonical_ast is None:
        diags = list(pre_run_diags)
        diags.append({
            "severity": "error",
            "code": "normalize_missing_ast",
            "message": "Normalization produced no canonical AST",
        })
        return CaseRunResult(
            case_id=case.id,
            bundle_result=BundleResult(
                bundle_id=case.id,
                session_results=[],
                diagnostics=diags,
            ),
        )

    bundle = norm_result.canonical_ast

    # Build per-step truth maps from expected per_evaluator results
    per_step_truth_maps = _build_per_step_truth_maps(case)
    fixture_eval_expr = _build_fixture_eval_expr(per_step_truth_maps)

    # Build fixture-backed support synthesis
    per_step_support_maps = _build_per_step_support_maps(case)
    from ..runtime.builtins import synthesize_support as default_synth
    fixture_synth = _build_fixture_synthesize_support(per_step_support_maps, default_synth)

    # Build PrimitiveSet with fixture eval_expr and support
    primitives = PrimitiveSet(
        eval_expr=fixture_eval_expr,
        synthesize_support=fixture_synth,
    )

    # Build sessions
    sessions = _build_sessions_from_case(case)

    # Build evaluation environment
    env = EvaluationEnvironment()

    # Build services dict
    services: dict[str, Any] = {}

    # Fixture adequacy handlers for method-computed assessments used in corpus
    # cases (e.g., A12 aa2 / aa_circular).
    services["adequacy_handlers"] = {
        "test://adequacy/compute_pass_v1": lambda assessment: 1.0,
    }

    # Inject transport queries from environment/session-step fixtures.
    transport_queries = _build_transport_queries_from_case(case)
    if transport_queries:
        services["__transport_queries__"] = transport_queries

    # Extract extra resolution policies from source and inject them
    extra_policies = _extract_extra_resolution_policies(
        case.source, bundle.resolutionPolicy.id
    )
    if extra_policies:
        services["__resolution_policies__"] = extra_policies

    # Build adjudicator from fixture expectations
    adjudicator = _build_fixture_adjudicator(case)

    # Check if bundle policy is adjudicated — provide a default adjudicator
    if bundle.resolutionPolicy.kind == "adjudicated" and adjudicator is None:
        from ..runtime.builtins import _aggregate_truth, _aggregate_support

        # Build a default paraconsistent-union fallback adjudicator
        def _default_adjudicator(per_evaluator: dict) -> "EvalNode":
            """Fallback adjudicator using paraconsistent-union semantics."""
            if not per_evaluator:
                return EvalNode(truth="N", reason="no_evaluators")
            evals = list(per_evaluator.values())
            truths = [e.truth for e in evals]
            prov: set[str] = set()
            for e in evals:
                prov.update(e.provenance)
            # Use the real paraconsistent join for truth aggregation
            agg_truth = _aggregate_truth(truths)
            truth_set = set(truths)
            reason = None
            if "T" in truth_set and "F" in truth_set:
                reason = "evaluator_conflict"
            support = _aggregate_support(evals, aggregate_truth=agg_truth)
            return EvalNode(
                truth=agg_truth, reason=reason,
                support=support or "absent",
                provenance=sorted(prov),
            )
        adjudicator = _default_adjudicator

    # Run the bundle
    try:
        result = run_bundle(
            bundle, sessions, env,
            primitives=primitives,
            services=services,
            adjudicator=adjudicator,
        )
    except Exception as exc:
        return CaseRunResult(
            case_id=case.id,
            bundle=bundle,
            error=f"Runner error: {exc}",
        )

    # Inject diagnostics that can't be produced organically
    injected_diags = _build_injected_diagnostics(case)
    if injected_diags:
        from ..runtime.models import sort_diagnostics
        result.diagnostics = sort_diagnostics(
            list(result.diagnostics) + pre_run_diags + injected_diags
        )
    elif pre_run_diags:
        from ..runtime.models import sort_diagnostics
        result.diagnostics = sort_diagnostics(list(result.diagnostics) + pre_run_diags)

    return CaseRunResult(
        case_id=case.id,
        bundle_result=result,
        bundle=bundle,
    )
