"""Fixture-backed plugin pack for Limnalis conformance testing.

Provides deterministic plugin implementations that return expected values
from the fixture corpus. Used by the conformance runner and available for
downstream testing.
"""

from __future__ import annotations

from typing import Any

from . import (
    ADEQUACY_METHOD,
    ADJUDICATOR,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    PluginRegistry,
)
from ..conformance.fixtures import FixtureCase
from ..runtime.models import (
    EvalNode,
    MachineState,
    StepContext,
    SupportResult,
    TruthCore,
)


# ---------------------------------------------------------------------------
# Handler classes
# ---------------------------------------------------------------------------


class _FixtureEvalHandler:
    """Fixture-backed expression evaluation handler (DEPRECATED).

    .. deprecated::
        This class is buggy for multi-evaluator claims: it returns the first
        truth value found regardless of which evaluator the handler represents.
        Use :class:`FixtureEvalHandlerForEvaluator` instead, which is scoped
        to a specific evaluator_id.

    Returns truth values from pre-computed expectations.
    """

    def __init__(self, truth_map: dict[str, dict[str, TruthCore]]) -> None:
        # truth_map: {claim_id: {evaluator_id: TruthCore}}
        self._truth_map = truth_map

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        claim_id = claim.id if hasattr(claim, "id") else str(claim)
        ev_truths = self._truth_map.get(claim_id, {})
        if ev_truths:
            for _ev_id, tc in ev_truths.items():
                return tc
        return TruthCore(truth="N", reason="fixture_not_specified")


class FixtureEvalHandlerForEvaluator:
    """Fixture-backed evaluation handler scoped to a single evaluator_id.

    Registered per ``evaluator_id::expr_type`` key in the plugin registry.
    """

    def __init__(
        self,
        evaluator_id: str,
        truth_map: dict[str, dict[str, TruthCore]],
    ) -> None:
        self._evaluator_id = evaluator_id
        self._truth_map = truth_map

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        claim_id = claim.id if hasattr(claim, "id") else str(claim)
        ev_truths = self._truth_map.get(claim_id, {})
        if self._evaluator_id in ev_truths:
            return ev_truths[self._evaluator_id]
        return TruthCore(truth="N", reason="fixture_not_specified")


class FixtureSupportHandler:
    """Fixture-backed support synthesis handler."""

    def __init__(
        self,
        support_map: dict[str, dict[str, str]],
        default_synth: Any = None,
    ) -> None:
        # support_map: {claim_id: {evaluator_id: support_value}}
        self._support_map = support_map
        self._default_synth = default_synth

    def __call__(
        self,
        claim: Any,
        truth_core: TruthCore,
        evidence_view: Any,
        evaluator_id: str,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> SupportResult:
        claim_id = claim.id if hasattr(claim, "id") else str(claim)
        claim_supports = self._support_map.get(claim_id, {})
        if evaluator_id in claim_supports:
            return SupportResult(
                support=claim_supports[evaluator_id],
                provenance=[evaluator_id, claim_id],
            )
        if self._default_synth is not None:
            result = self._default_synth(
                claim, truth_core, evidence_view, evaluator_id,
                step_ctx, machine_state,
            )
            if isinstance(result, tuple):
                return result[0]
            return result
        return SupportResult(support="absent", provenance=[])


class FixtureAdequacyHandler:
    """Fixture-backed adequacy method handler."""

    def __init__(self, score: float) -> None:
        self._score = score

    def __call__(self, assessment: Any) -> float:
        return self._score


class FixtureAdjudicator:
    """Fixture-backed adjudicator using paraconsistent-union semantics.

    Detects evaluator conflicts (T vs F) and returns B with
    reason=evaluator_conflict, otherwise returns the agreed truth.
    """

    def __call__(self, per_evaluator: dict[str, EvalNode]) -> EvalNode:
        if not per_evaluator:
            return EvalNode(truth="N", reason="no_evaluators")

        evals = list(per_evaluator.values())
        truths = [e.truth for e in evals]
        truth_set = set(truths)

        prov: set[str] = set()
        for e in evals:
            prov.update(e.provenance)

        if "T" in truth_set and "F" in truth_set:
            return EvalNode(
                truth="B",
                reason="evaluator_conflict",
                support="conflicted",
                provenance=sorted(prov),
            )

        if len(truth_set) == 1:
            agreed = truths[0]
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

        # Mixed truths (not T vs F): use paraconsistent join.
        # Inline the lattice join to avoid importing private helpers from
        # runtime.builtins.  The join table: T absorbs N, F absorbs N,
        # B absorbs everything, and T+F -> B.
        _JOIN = {
            ("T", "T"): "T", ("F", "F"): "F", ("B", "B"): "B", ("N", "N"): "N",
            ("T", "F"): "B", ("F", "T"): "B",
            ("T", "B"): "B", ("B", "T"): "B", ("F", "B"): "B", ("B", "F"): "B",
            ("T", "N"): "T", ("N", "T"): "T",
            ("F", "N"): "F", ("N", "F"): "F",
            ("B", "N"): "B", ("N", "B"): "B",
        }
        agg_truth = truths[0]
        for v in truths[1:]:
            agg_truth = _JOIN[(agg_truth, v)]

        reason = None
        if agg_truth == "B":
            reason = "evaluator_conflict"

        # Aggregate support: conservative ordering.
        # Force "conflicted" only on real T/F evaluator disagreement.
        supports = [e.support for e in evals if e.support is not None]
        agg_support: str | None = None
        if supports:
            if agg_truth == "B" and "T" in truth_set and "F" in truth_set:
                agg_support = "conflicted"
            else:
                for s in ["conflicted", "partial", "supported", "inapplicable", "absent"]:
                    if s in supports:
                        agg_support = s
                        break

        return EvalNode(
            truth=agg_truth,
            reason=reason,
            support=agg_support,
            provenance=sorted(prov),
        )


# ---------------------------------------------------------------------------
# Truth/support map builders (reuse logic from conformance.runner)
# ---------------------------------------------------------------------------


def _build_truth_map(case: FixtureCase) -> dict[str, dict[str, TruthCore]]:
    """Build a merged truth map from fixture case expectations.

    Returns: {claim_id: {evaluator_id: TruthCore}}
    """
    truth_map: dict[str, dict[str, TruthCore]] = {}
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            claims = step_exp.get("claims", {})
            for claim_id, claim_exp in claims.items():
                per_ev = claim_exp.get("per_evaluator", {})
                if not per_ev:
                    continue
                if claim_id not in truth_map:
                    truth_map[claim_id] = {}
                for ev_id, ev_exp in per_ev.items():
                    if isinstance(ev_exp, dict):
                        truth_map[claim_id][ev_id] = TruthCore(
                            truth=ev_exp.get("truth", "N"),
                            reason=ev_exp.get("reason"),
                        )
                    elif isinstance(ev_exp, str):
                        truth_map[claim_id][ev_id] = TruthCore(truth=ev_exp)
    return truth_map


def _build_support_map(case: FixtureCase) -> dict[str, dict[str, str]]:
    """Build a merged support map from fixture case expectations.

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


def _collect_evaluator_expr_types(
    case: FixtureCase,
) -> set[tuple[str, str]]:
    """Collect all (evaluator_id, expr_type) pairs from case bindings/environment.

    Falls back to ``"predicate"`` as the default expr_type when the fixture
    does not specify one.
    """
    pairs: set[tuple[str, str]] = set()

    # From environment bindings
    for binding in case.environment.get("bindings", []):
        if isinstance(binding, dict):
            ev_id = binding.get("id", "")
            expr_type = binding.get("expr_type", "predicate")
            if ev_id:
                pairs.add((ev_id, expr_type))

    # From expected per_evaluator keys (ensures all referenced evaluators are covered)
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            for claim_exp in step_exp.get("claims", {}).values():
                for ev_id in claim_exp.get("per_evaluator", {}):
                    pairs.add((ev_id, "predicate"))

    return pairs


def _has_adjudicated_policy(case: FixtureCase) -> bool:
    """Check if the case has adjudicated resolution expectations."""
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            for claim_exp in step_exp.get("claims", {}).values():
                agg = claim_exp.get("aggregate", {})
                if isinstance(agg, dict) and agg.get("reason") == "evaluator_conflict":
                    return True
    return False


# ---------------------------------------------------------------------------
# Main registration function
# ---------------------------------------------------------------------------


def register_fixture_plugins(
    registry: PluginRegistry,
    case: FixtureCase,
    *,
    default_support_synth: Any = None,
) -> dict[str, Any]:
    """Register all fixture-backed plugins for a conformance case.

    Analyzes the fixture case's expected results and registers:
    - Evaluator bindings (per evaluator_id + expr_type)
    - Support policy handlers (per evidence policy URI)
    - Adequacy method handlers (per method URI)
    - Adjudicator (if resolution policy is adjudicated)

    Returns a supplementary services dict with any extra entries
    needed (e.g., transport queries, resolution policies) that
    don't fit the plugin model.

    Args:
        registry: Plugin registry to register into
        case: Fixture case with expected results
        default_support_synth: Optional fallback support synthesis callable

    Returns:
        Dict of extra service entries (transport queries, etc.)
    """
    extras: dict[str, Any] = {}

    # -- 1. Build truth and support maps --
    truth_map = _build_truth_map(case)
    support_map = _build_support_map(case)

    # -- 2. Register evaluator binding plugins --
    ev_pairs = _collect_evaluator_expr_types(case)
    for evaluator_id, expr_type in ev_pairs:
        plugin_id = f"{evaluator_id}::{expr_type}"
        handler = FixtureEvalHandlerForEvaluator(evaluator_id, truth_map)
        if not registry.has(EVALUATOR_BINDING, plugin_id):
            registry.register(
                EVALUATOR_BINDING,
                plugin_id,
                handler,
                description=f"Fixture eval binding for {evaluator_id}",
            )

    # -- 3. Register evidence policy handlers --
    for binding in case.environment.get("bindings", []):
        if isinstance(binding, dict) and binding.get("type") == "evidence_policy":
            policy_uri = binding.get("id", "")
            if policy_uri and not registry.has(EVIDENCE_POLICY, policy_uri):
                handler = FixtureSupportHandler(
                    support_map, default_synth=default_support_synth,
                )
                registry.register(
                    EVIDENCE_POLICY,
                    policy_uri,
                    handler,
                    description=f"Fixture evidence policy {policy_uri}",
                )

    # -- 4. Register adequacy method handlers --
    adequacy_methods = case.environment.get("adequacy_methods", {})
    if isinstance(adequacy_methods, dict):
        for method_uri, method_def in adequacy_methods.items():
            score = 1.0
            if isinstance(method_def, dict):
                score = method_def.get("score", 1.0)
            if not registry.has(ADEQUACY_METHOD, method_uri):
                registry.register(
                    ADEQUACY_METHOD,
                    method_uri,
                    FixtureAdequacyHandler(score),
                    description=f"Fixture adequacy method {method_uri}",
                )

    # Also register any adequacy handlers referenced in source anchors
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            for claim_exp in step_exp.get("claims", {}).values():
                for ev_exp in claim_exp.get("per_evaluator", {}).values():
                    if isinstance(ev_exp, dict):
                        method = ev_exp.get("adequacy_method")
                        if method and not registry.has(ADEQUACY_METHOD, method):
                            registry.register(
                                ADEQUACY_METHOD,
                                method,
                                FixtureAdequacyHandler(1.0),
                                description=f"Fixture adequacy method {method}",
                            )

    # -- 5. Register adjudicator if adjudicated policy --
    if _has_adjudicated_policy(case):
        adjudicator_id = f"fixture_adjudicator::{case.id}"
        if not registry.has(ADJUDICATOR, adjudicator_id):
            registry.register(
                ADJUDICATOR,
                adjudicator_id,
                FixtureAdjudicator(),
                description=f"Fixture adjudicator for case {case.id}",
            )

    # -- 6. Build extra service entries --
    # Transport queries
    transport_queries: list[dict[str, Any]] = []
    for query in case.environment.get("transport_queries", []):
        if isinstance(query, dict):
            transport_queries.append(dict(query))
    if transport_queries:
        extras["__transport_queries__"] = transport_queries

    # Step index tracking placeholder
    extras["__fixture_step_index__"] = 0

    return extras


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "FixtureAdequacyHandler",
    "FixtureAdjudicator",
    "FixtureEvalHandlerForEvaluator",
    "FixtureSupportHandler",
    "register_fixture_plugins",
]
