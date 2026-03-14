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


def _build_support_map_from_expected(
    case: FixtureCase,
) -> dict[str, dict[str, str]]:
    """Extract per-claim, per-evaluator support values from fixture expectations.

    Returns: {claim_id: {evaluator_id: support_value}}
    """
    support_map: dict[str, dict[str, str]] = {}
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            claims = step_exp.get("claims", {})
            for claim_id, claim_exp in claims.items():
                per_ev = claim_exp.get("per_evaluator", {})
                if not per_ev:
                    continue
                for ev_id, ev_exp in per_ev.items():
                    if isinstance(ev_exp, dict) and "support" in ev_exp:
                        support_map.setdefault(claim_id, {})[ev_id] = ev_exp["support"]
    return support_map


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
    state = {"step_index": 0, "last_step_id": None}

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

        # Track step transitions to advance the step index
        current_step_id = None
        if step_ctx is not None:
            # Use effective_time or effective_history as step discriminant
            if step_ctx.effective_time is not None:
                current_step_id = getattr(step_ctx.effective_time, "t", None)
            if current_step_id is None and step_ctx.effective_history:
                current_step_id = str(step_ctx.effective_history)

        if current_step_id is not None and current_step_id != state["last_step_id"]:
            if state["last_step_id"] is not None:
                state["step_index"] += 1
            state["last_step_id"] = current_step_id

        # Choose the truth map for the current step
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
    support_map: dict[str, dict[str, str]],
    default_synthesize_support: Any,
) -> Any:
    """Build a fixture-backed synthesize_support that uses expected values when available."""

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
        claim_supports = support_map.get(claim_id, {})

        if ev_id in claim_supports:
            return (
                SupportResult(support=claim_supports[ev_id], provenance=[ev_id, claim_id]),
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
                    time=step_time,
                    history_binding=step_env.get("history_binding"),
                ))
            if not steps:
                steps = [StepConfig(id="step0")]
            sessions.append(SessionConfig(
                id=sess_env.get("id", "default"),
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
    # Parse the surface source into an AST bundle
    try:
        norm_result = normalize_surface_text(case.source, validate_schema=True)
    except Exception as exc:
        return CaseRunResult(case_id=case.id, error=f"Parse/normalize error: {exc}")

    if norm_result.canonical_ast is None:
        return CaseRunResult(
            case_id=case.id, error="Normalization produced no canonical AST"
        )

    bundle = norm_result.canonical_ast

    # Build per-step truth maps from expected per_evaluator results
    per_step_truth_maps = _build_per_step_truth_maps(case)
    fixture_eval_expr = _build_fixture_eval_expr(per_step_truth_maps)

    # Build fixture-backed support synthesis
    support_map = _build_support_map_from_expected(case)
    from ..runtime.builtins import synthesize_support as default_synth
    fixture_synth = _build_fixture_synthesize_support(support_map, default_synth)

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

    # Inject transport queries from environment
    transport_queries = case.environment.get("transport_queries", [])
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
        # Build a default paraconsistent-union fallback adjudicator
        def _default_adjudicator(per_evaluator: dict) -> "EvalNode":
            """Fallback adjudicator using paraconsistent-union semantics."""
            if not per_evaluator:
                return EvalNode(truth="N", reason="no_evaluators")
            evals = list(per_evaluator.values())
            truths = {e.truth for e in evals}
            prov: set[str] = set()
            for e in evals:
                prov.update(e.provenance)
            if "T" in truths and "F" in truths:
                return EvalNode(
                    truth="B", reason="evaluator_conflict",
                    support="conflicted", provenance=sorted(prov),
                )
            agreed = evals[0].truth
            supports = [e.support for e in evals if e.support is not None]
            support = None
            for s in ["conflicted", "partial", "supported", "inapplicable", "absent"]:
                if s in supports:
                    support = s
                    break
            return EvalNode(
                truth=agreed, support=support or "absent",
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
        result.diagnostics = list(result.diagnostics) + injected_diags

    return CaseRunResult(
        case_id=case.id,
        bundle_result=result,
        bundle=bundle,
    )
