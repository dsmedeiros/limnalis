"""Fixture-backed plugin pack for Limnalis conformance testing.

Provides deterministic plugin implementations that return expected values
from the fixture corpus. Used by the conformance runner and available for
downstream testing.
"""

from __future__ import annotations

from typing import Any

from ..loader import normalize_surface_text
from . import (
    ADEQUACY_METHOD,
    ADJUDICATOR,
    BASELINE_HANDLER,
    CRITERION_BINDING,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    TRANSPORT_HANDLER,
    PluginRegistry,
    build_services_from_registry,
)
from ..conformance.fixtures import FixtureCase
from ..models.ast import BaselineRefTermNode
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
        *,
        per_step_truth_maps: list[dict[str, dict[str, TruthCore]]] | None = None,
    ) -> None:
        self._evaluator_id = evaluator_id
        self._truth_map = truth_map
        self._per_step_truth_maps = per_step_truth_maps or []

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        claim_id = claim.id if hasattr(claim, "id") else str(claim)
        truth_map = self._truth_map
        raw_step_idx = machine_state.adequacy_store.get("__fixture_step_index__")
        if self._per_step_truth_maps and isinstance(raw_step_idx, int):
            if 0 <= raw_step_idx < len(self._per_step_truth_maps):
                truth_map = self._per_step_truth_maps[raw_step_idx]

        ev_truths = truth_map.get(claim_id, {})
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
        agg_support: str | None = "absent"
        if supports:
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


def _build_per_step_truth_maps(
    case: FixtureCase,
) -> list[dict[str, dict[str, TruthCore]]]:
    """Build per-step truth maps from fixture case expectations."""
    step_truth_maps: list[dict[str, dict[str, TruthCore]]] = []
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            truth_map: dict[str, dict[str, TruthCore]] = {}
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
            step_truth_maps.append(truth_map)
    return step_truth_maps


def _build_truth_map(case: FixtureCase) -> dict[str, dict[str, TruthCore]]:
    """Build a merged truth map from fixture case expectations.

    Returns: {claim_id: {evaluator_id: TruthCore}}
    """
    truth_map: dict[str, dict[str, TruthCore]] = {}
    for step_map in _build_per_step_truth_maps(case):
        for claim_id, ev_map in step_map.items():
            if claim_id not in truth_map:
                truth_map[claim_id] = {}
            truth_map[claim_id].update(ev_map)
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
    claim_expr_types: dict[str, str] = {}

    if case.source:
        try:
            norm = normalize_surface_text(case.source, validate_schema=False)
            if norm.canonical_ast is not None:
                for block in norm.canonical_ast.claimBlocks:
                    for claim in block.claims:
                        node_name = getattr(claim.expr, "node", "") or type(claim.expr).__name__
                        claim_expr_types[claim.id] = node_name.removesuffix("Expr").lower()
        except Exception:
            claim_expr_types = {}

    # From environment bindings
    for binding in case.environment.get("bindings", []):
        if isinstance(binding, dict) and binding.get("type") == "evaluator":
            ev_id = binding.get("id", "")
            expr_type = binding.get("expr_type", "predicate")
            if ev_id:
                pairs.add((ev_id, expr_type))

    # From expected per_evaluator keys (ensures all referenced evaluators are covered)
    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            for claim_id, claim_exp in step_exp.get("claims", {}).items():
                expr_type = claim_expr_types.get(claim_id, "predicate")
                for ev_id in claim_exp.get("per_evaluator", {}):
                    pairs.add((ev_id, expr_type))

    return pairs


def _has_adjudicated_policy(case: FixtureCase) -> bool:
    """Check whether the fixture source uses adjudicated resolution policy."""
    if case.source:
        try:
            norm = normalize_surface_text(case.source, validate_schema=False)
            if (
                norm.canonical_ast is not None
                and norm.canonical_ast.resolutionPolicy.kind == "adjudicated"
            ):
                return True
        except Exception:
            pass
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
    per_step_truth_maps = _build_per_step_truth_maps(case)
    truth_map = _build_truth_map(case)
    support_map = _build_support_map(case)

    # -- 2. Register evaluator binding plugins --
    ev_pairs = _collect_evaluator_expr_types(case)
    for evaluator_id, expr_type in ev_pairs:
        plugin_id = f"{evaluator_id}::{expr_type}"
        handler = FixtureEvalHandlerForEvaluator(
            evaluator_id,
            truth_map,
            per_step_truth_maps=per_step_truth_maps,
        )
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
# Live extension fixture pack (project-authored extension corpus, M7 T5)
# ---------------------------------------------------------------------------
#
# The vendored corpus is evaluated through claim-id-keyed fixture maps built
# from expectations (see conformance.runner._build_fixture_eval_expr), which
# never exercises sub-expression evaluation.  The bindings below are LIVE:
# they key on predicate NAMES (atom level) or on materialized baseline values,
# so LogicalExpr composition runs through the runtime's spec §4 pair algebra
# and baseline resolution runs through the wave-2
# services["baseline_criterion_resolver"] / shared_state cache machinery.
# Stated behaviors mirror fixtures/limnalis_extension_corpus_v0.1.yaml.

ATOMS_V2_URI = "test://eval/atoms_v2"
BASELINE_BY_CONTEXT_V1_URI = "test://baseline/by_context_v1"
BASELINE_MATCH_V1_URI = "test://eval/baseline_match_v1"

# test://eval/atoms_v2 truth table, keyed on predicate NAME (never claim id).
_ATOMS_V2_TRUTHS: dict[str, tuple[str, str | None]] = {
    "t": ("T", None),
    "f": ("F", None),
    "b": ("B", "source_conflict"),
    "n": ("N", "undefined_term"),
}

# test://baseline/by_context_v1 value table, keyed on the effective step
# context (time point, regime facet) per the spec §17.2 A11 narrative.
_BY_CONTEXT_V1_VALUES: dict[tuple[str | None, str | None], int] = {
    ("2026-03-06T09:00:00Z", "nominal"): 10,
    ("2026-03-06T09:05:00Z", "stress"): 20,
}

# test://eval/baseline_match_v1: sensor_A is fixed at 10 (spec §17.2 A11).
_BASELINE_MATCH_V1_EXPECTED_VALUE = 10


class AtomTruthEvalHandler:
    """ATOM-LEVEL evaluator binding keyed on predicate NAMES, never claim ids.

    The default instance implements ``test://eval/atoms_v2`` (t→T, f→F,
    b→B[source_conflict], n→N[undefined_term]; unknown names →
    N[undefined_term]).  Track C evaluators reuse the class with their own
    stated truth tables (e.g. ``test://paradox/eval/zf_v1`` mapping
    choice-dependent predicates to N[missing_binding]).  Because the handler
    resolves individual PredicateExpr leaves, any LogicalExpr over these
    atoms is composed by the live §4 pair algebra in
    ``runtime.builtins._eval_logical_expr`` — never keyed on claim ids.
    """

    def __init__(
        self,
        table: dict[str, tuple[str, str | None]] | None = None,
        *,
        uri: str = ATOMS_V2_URI,
        unknown_reason: str = "undefined_term",
    ) -> None:
        self._table = dict(_ATOMS_V2_TRUTHS if table is None else table)
        self._uri = uri
        self._unknown_reason = unknown_reason

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        name = getattr(expr, "name", None)
        entry = self._table.get(name) if isinstance(name, str) else None
        if entry is None:
            return TruthCore(
                truth="N",
                reason=self._unknown_reason,
                provenance=[self._uri],
            )
        truth, reason = entry
        return TruthCore(
            truth=truth,
            reason=reason,
            provenance=[self._uri, f"atom:{name}"],
        )


class BaselineMatchEvalHandler:
    """``test://eval/baseline_match_v1`` — baseline-comparison evaluator.

    Returns T when every BaselineRefTerm in the claim expression resolves to
    a ready baseline whose materialized value equals the expected sensor
    value (10 — sensor_A is fixed at 10 per the spec §17.2 A11 narrative);
    F otherwise (missing, non-ready, or non-matching baselines, or a claim
    with no baseline reference, all yield F).
    """

    def __init__(self, expected_value: int = _BASELINE_MATCH_V1_EXPECTED_VALUE) -> None:
        self._expected_value = expected_value

    @staticmethod
    def _collect_baseline_ref_ids(expr: Any) -> list[str]:
        refs: list[str] = []

        def _walk(obj: Any) -> None:
            if isinstance(obj, BaselineRefTermNode):
                if obj.id not in refs:
                    refs.append(obj.id)
                return
            for sub in getattr(obj, "args", None) or []:
                _walk(sub)
            for sub in getattr(obj, "items", None) or []:
                _walk(sub)

        _walk(expr)
        return refs

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        ref_ids = self._collect_baseline_ref_ids(expr)
        if not ref_ids:
            return TruthCore(truth="F", provenance=[BASELINE_MATCH_V1_URI])
        for ref_id in ref_ids:
            state = machine_state.baseline_store.get(ref_id)
            if (
                state is None
                or state.status != "ready"
                or state.value != self._expected_value
            ):
                return TruthCore(
                    truth="F",
                    provenance=sorted({BASELINE_MATCH_V1_URI, *ref_ids}),
                )
        return TruthCore(
            truth="T",
            provenance=sorted({BASELINE_MATCH_V1_URI, *ref_ids}),
        )


def _frame_regime(frame: Any) -> str | None:
    """Extract the regime facet from a FrameNode or FramePatternNode."""
    regime = getattr(frame, "regime", None)
    if regime is None:
        facets = getattr(frame, "facets", None)
        if facets is not None:
            regime = getattr(facets, "regime", None)
    return regime


def by_context_baseline_resolver(
    baseline_node: Any,
    step_ctx: StepContext | None,
    services: dict[str, Any],
) -> Any:
    """``test://baseline/by_context_v1`` — context-sensitive baseline criterion.

    Returns 10 under step context (time t1 2026-03-06T09:00:00Z,
    regime=nominal) and 20 under (t2 2026-03-06T09:05:00Z, regime=stress),
    per the spec §17.2 A11 narrative.  Any other context raises, which the
    baseline materialization scaffold surfaces as a
    ``baseline_resolution_error`` diagnostic with the baseline unresolved.
    """
    time_point: str | None = None
    regime: str | None = None
    if step_ctx is not None:
        if step_ctx.effective_time is not None:
            time_point = step_ctx.effective_time.t
        regime = _frame_regime(step_ctx.effective_frame)
    key = (time_point, regime)
    if key not in _BY_CONTEXT_V1_VALUES:
        raise LookupError(
            f"{BASELINE_BY_CONTEXT_V1_URI}: unmapped step context {key!r}"
        )
    return _BY_CONTEXT_V1_VALUES[key]


# ---------------------------------------------------------------------------
# Track C paradox-forensics bindings (M7 T6)
# ---------------------------------------------------------------------------
#
# Deterministic live bindings for the four paradox-forensics cases (C1-C4).
# Every URI a Track C bundle references is registered here; the only
# "unresolved" outcomes are ones whose missing-ness IS the pinned verdict
# (e.g. qg_tbd_v1 declaring its score not yet computable, zf_v1 declaring
# choice-dependent predicates undecidable without AC).

# C1 — liar forensics
PARADOX_EVAL_LIAR_V1_URI = "test://paradox/eval/liar_v1"
PARADOX_CRITERION_TARSKI_GATE_V1_URI = "test://paradox/criterion/tarski_gate_v1"
# C2 — Schwarzschild forensics
PARADOX_EVAL_GR_SEMICLASSICAL_V1_URI = "test://paradox/eval/gr_semiclassical_v1"
PARADOX_METHOD_GW_WAVEFORMS_V1_URI = "test://paradox/method/gw_waveforms_v1"
PARADOX_METHOD_QG_TBD_V1_URI = "test://paradox/method/qg_tbd_v1"
PARADOX_BRIDGE_NAIVE_EXTRAPOLATION_V1_URI = "test://paradox/bridge/naive_extrapolation_v1"
# C3 — decoherence cat
PARADOX_EVAL_UNITARY_V1_URI = "test://paradox/eval/unitary_v1"
PARADOX_EVAL_COLLAPSE_V1_URI = "test://paradox/eval/collapse_v1"
PARADOX_BRIDGE_AMPLIFICATION_V1_URI = "test://paradox/bridge/amplification_v1"
# C4 — Banach-Tarski
PARADOX_EVAL_ZFC_V1_URI = "test://paradox/eval/zfc_v1"
PARADOX_EVAL_ZF_V1_URI = "test://paradox/eval/zf_v1"
PARADOX_METHOD_LEBESGUE_MEASURE_V1_URI = "test://paradox/method/lebesgue_measure_v1"

# Predicate truth tables (name -> (truth, reason)), stated in the corpus.
_LIAR_V1_TRUTHS: dict[str, tuple[str, str | None]] = {
    # The liar sentence is an undefined term for the truth evaluator.
    "false": ("N", "undefined_term"),
}
_GR_SEMICLASSICAL_V1_TRUTHS: dict[str, tuple[str, str | None]] = {
    "geodesically_incomplete": ("T", None),
    "infinite_density": ("T", None),
}
_UNITARY_V1_TRUTHS: dict[str, tuple[str, str | None]] = {
    "superposed": ("T", None),
    "interference_pattern": ("T", None),
}
_COLLAPSE_V1_TRUTHS: dict[str, tuple[str, str | None]] = {
    "superposed": ("F", None),
    "interference_pattern": ("T", None),
}
_ZFC_V1_TRUTHS: dict[str, tuple[str, str | None]] = {
    "duplicable": ("T", None),
    # The duplication theorem contradicts naive volume preservation.
    "volume_preserved": ("F", None),
}
# zf_v1 is REGISTERED (live-pack URI) but deterministically undecided on
# choice-dependent predicates: without AC it has no binding for them.
_ZF_V1_TRUTHS: dict[str, tuple[str, str | None]] = {
    "duplicable": ("N", "missing_binding"),
    "volume_preserved": ("N", "missing_binding"),
}
# Dynamic-expression truth tables (subject symbol -> (truth, reason)).
_GR_SEMICLASSICAL_V1_DYNAMICS: dict[str, tuple[str, str | None]] = {
    # Declared unboundedness: curvature divergence is assertable (lint-11
    # style declaration; spec DynamicExpr `-->` normalizes to op=approaches).
    "curvature": ("T", None),
}


class DynamicTruthEvalHandler:
    """Live evaluator handler for DynamicExpr claims.

    Keys on the dynamic SUBJECT symbol (e.g. ``curvature`` in
    ``curvature --> divergence_within_finite_time``); unknown subjects
    resolve N[undefined_term].  Deterministic with stated outputs.
    """

    def __init__(
        self,
        table: dict[str, tuple[str, str | None]],
        *,
        uri: str,
    ) -> None:
        self._table = dict(table)
        self._uri = uri

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        subject = getattr(expr, "subject", None)
        name = getattr(subject, "value", None)
        if not isinstance(name, str):
            name = getattr(subject, "name", None)
        entry = self._table.get(name) if isinstance(name, str) else None
        if entry is None:
            return TruthCore(
                truth="N",
                reason="undefined_term",
                provenance=[self._uri],
            )
        truth, reason = entry
        return TruthCore(
            truth=truth,
            reason=reason,
            provenance=[self._uri, f"dynamic:{name}"],
        )


def tarski_self_reference_criterion(
    expr: Any,
    claim: Any,
    step_ctx: StepContext | None,
    machine_state: MachineState,
) -> TruthCore:
    """``test://paradox/criterion/tarski_gate_v1`` — self-reference detector.

    Returns B[self_reference] when any symbol argument inside the judged
    inner expression names the enclosing claim's own id (the claim judges
    itself); otherwise returns T (the criterion passes).  Deterministic.
    """
    claim_id = getattr(claim, "id", None)
    inner = getattr(expr, "expr", expr)

    symbols: list[str] = []

    def _walk(obj: Any) -> None:
        value = getattr(obj, "value", None)
        if isinstance(value, str):
            symbols.append(value)
        for sub in getattr(obj, "args", None) or []:
            _walk(sub)
        for sub in getattr(obj, "items", None) or []:
            _walk(sub)

    _walk(inner)

    if isinstance(claim_id, str) and claim_id in symbols:
        return TruthCore(
            truth="B",
            reason="self_reference",
            provenance=[PARADOX_CRITERION_TARSKI_GATE_V1_URI, f"claim:{claim_id}"],
        )
    return TruthCore(
        truth="T",
        provenance=[PARADOX_CRITERION_TARSKI_GATE_V1_URI],
    )


class JudgedCriterionEvalHandler:
    """Live evaluator handler for JudgedExpr claims.

    Dispatches on the JudgedExpr's ``criterionRef`` URI against the live
    criterion-binding table; an unregistered criterion resolves
    N[missing_binding] (the A13 missing-criterion semantics).
    """

    def __init__(
        self,
        criteria: dict[str, Any],
        *,
        uri: str,
    ) -> None:
        self._criteria = dict(criteria)
        self._uri = uri

    def __call__(
        self,
        expr: Any,
        claim: Any,
        step_ctx: StepContext | None,
        machine_state: MachineState,
    ) -> TruthCore:
        criterion_ref = getattr(expr, "criterionRef", None)
        handler = (
            self._criteria.get(criterion_ref)
            if isinstance(criterion_ref, str)
            else None
        )
        if handler is None:
            provenance = [self._uri]
            if isinstance(criterion_ref, str):
                provenance.append(criterion_ref)
            return TruthCore(
                truth="N",
                reason="missing_binding",
                provenance=provenance,
            )
        return handler(expr, claim, step_ctx, machine_state)


# Adequacy method callables (uri -> callable(assessment) -> float | str).
# A non-numeric return leaves the assessment score unresolved, which the
# runtime pins as N[missing_binding] + an adequacy_method_binding_missing
# error diagnostic (vendored ast_decision: unresolved_method ->
# N[missing_binding]); that missing-ness is the stated verdict for
# qg_tbd_v1.
def _gw_waveforms_method(assessment: Any) -> float:
    """test://paradox/method/gw_waveforms_v1 — recomputes 0.99 (agrees with
    the attested score, which the runtime uses directly when present)."""
    return 0.99


def _qg_tbd_method(assessment: Any) -> str:
    """test://paradox/method/qg_tbd_v1 — declares the score not yet
    computable (returns the non-numeric sentinel 'N')."""
    return "N"


def _lebesgue_measure_method(assessment: Any) -> float:
    """test://paradox/method/lebesgue_measure_v1 — recomputes 0.98 (agrees
    with the attested score)."""
    return 0.98


_LIVE_CRITERION_BINDINGS: dict[str, Any] = {
    PARADOX_CRITERION_TARSKI_GATE_V1_URI: tarski_self_reference_criterion,
}

_LIVE_ADEQUACY_METHODS: dict[str, Any] = {
    PARADOX_METHOD_GW_WAVEFORMS_V1_URI: _gw_waveforms_method,
    PARADOX_METHOD_QG_TBD_V1_URI: _qg_tbd_method,
    PARADOX_METHOD_LEBESGUE_MEASURE_V1_URI: _lebesgue_measure_method,
}


def _bridge_via_marker(uri: str) -> Any:
    """Registry marker for a live-pack bridge ``via`` URI.

    The builtin ``execute_transport`` implements metadata_only / preserve /
    degrade internally (spec §10.2) and never invokes a transport handler
    for those modes; the marker records the URI as pack-resolved so Track C
    bundles carry no dangling ``via`` references.
    """

    def _marker(*args: Any, **kwargs: Any) -> None:
        return None

    _marker.__doc__ = (
        f"Live extension bridge via marker for {uri}: builtin degrade/"
        "preserve semantics apply; handler is never invoked."
    )
    return _marker


_LIVE_BRIDGE_VIA_URIS: tuple[str, ...] = (
    PARADOX_BRIDGE_NAIVE_EXTRAPOLATION_V1_URI,
    PARADOX_BRIDGE_AMPLIFICATION_V1_URI,
)


def _partial_factory(cls: Any, *args: Any, **kwargs: Any) -> Any:
    """Zero-argument factory for a handler class with bound arguments."""

    def _make() -> Any:
        return cls(*args, **kwargs)

    return _make


# Live pack registries: binding URI -> {expr kind -> handler factory}.
# Expr kinds use the RegistryEvaluatorBindings plugin-id suffixes
# ("predicate", "dynamic", "judged", ...).
_LIVE_EVALUATOR_HANDLER_FACTORIES: dict[str, dict[str, Any]] = {
    ATOMS_V2_URI: {"predicate": AtomTruthEvalHandler},
    BASELINE_MATCH_V1_URI: {"predicate": BaselineMatchEvalHandler},
    PARADOX_EVAL_LIAR_V1_URI: {
        "predicate": _partial_factory(
            AtomTruthEvalHandler, _LIAR_V1_TRUTHS, uri=PARADOX_EVAL_LIAR_V1_URI
        ),
        "judged": _partial_factory(
            JudgedCriterionEvalHandler,
            _LIVE_CRITERION_BINDINGS,
            uri=PARADOX_EVAL_LIAR_V1_URI,
        ),
    },
    PARADOX_EVAL_GR_SEMICLASSICAL_V1_URI: {
        "predicate": _partial_factory(
            AtomTruthEvalHandler,
            _GR_SEMICLASSICAL_V1_TRUTHS,
            uri=PARADOX_EVAL_GR_SEMICLASSICAL_V1_URI,
        ),
        "dynamic": _partial_factory(
            DynamicTruthEvalHandler,
            _GR_SEMICLASSICAL_V1_DYNAMICS,
            uri=PARADOX_EVAL_GR_SEMICLASSICAL_V1_URI,
        ),
    },
    PARADOX_EVAL_UNITARY_V1_URI: {
        "predicate": _partial_factory(
            AtomTruthEvalHandler, _UNITARY_V1_TRUTHS, uri=PARADOX_EVAL_UNITARY_V1_URI
        ),
    },
    PARADOX_EVAL_COLLAPSE_V1_URI: {
        "predicate": _partial_factory(
            AtomTruthEvalHandler, _COLLAPSE_V1_TRUTHS, uri=PARADOX_EVAL_COLLAPSE_V1_URI
        ),
    },
    PARADOX_EVAL_ZFC_V1_URI: {
        "predicate": _partial_factory(
            AtomTruthEvalHandler, _ZFC_V1_TRUTHS, uri=PARADOX_EVAL_ZFC_V1_URI
        ),
    },
    PARADOX_EVAL_ZF_V1_URI: {
        "predicate": _partial_factory(
            AtomTruthEvalHandler, _ZF_V1_TRUTHS, uri=PARADOX_EVAL_ZF_V1_URI
        ),
    },
}
_LIVE_BASELINE_RESOLVERS: dict[str, Any] = {
    BASELINE_BY_CONTEXT_V1_URI: by_context_baseline_resolver,
}


def _dispatching_baseline_resolver(resolvers: dict[str, Any]) -> Any:
    """Build a ``services["baseline_criterion_resolver"]`` callable that
    dispatches on the baseline's criterion ref URI."""

    def _resolve(
        baseline_node: Any,
        step_ctx: StepContext | None,
        services: dict[str, Any],
    ) -> Any:
        criterion = getattr(baseline_node, "criterion", None)
        ref = getattr(criterion, "ref", None)
        resolver = resolvers.get(ref) if isinstance(ref, str) else None
        if resolver is None:
            raise LookupError(
                f"no live baseline resolver registered for criterion {ref!r}"
            )
        return resolver(baseline_node, step_ctx, services)

    return _resolve


def _iter_bundle_claims(bundle: Any) -> Any:
    for block in getattr(bundle, "claimBlocks", None) or []:
        yield from getattr(block, "claims", None) or []


def _collect_judged_criterion_refs(bundle: Any) -> list[str]:
    """Collect JudgedExpr criterionRef URIs from bundle claim expressions."""
    refs: list[str] = []

    def _walk(obj: Any) -> None:
        criterion_ref = getattr(obj, "criterionRef", None)
        if isinstance(criterion_ref, str) and criterion_ref not in refs:
            refs.append(criterion_ref)
        for attr in ("expr", "lhs", "rhs", "property", "onset",
                     "persistsWhile", "dissolvesWhen", "hysteresis"):
            sub = getattr(obj, attr, None)
            if sub is not None and sub is not obj:
                _walk(sub)
        for sub in getattr(obj, "args", None) or []:
            _walk(sub)

    for claim in _iter_bundle_claims(bundle):
        _walk(getattr(claim, "expr", None))
    return refs


def _collect_adequacy_method_refs(bundle: Any) -> list[str]:
    """Collect adequacy method URIs from bundle anchors and joint groups."""
    refs: list[str] = []
    for anchor in getattr(bundle, "anchors", None) or []:
        for aa in getattr(anchor, "adequacy", None) or []:
            method = getattr(aa, "method", None)
            if isinstance(method, str) and method not in refs:
                refs.append(method)
    for ja in getattr(bundle, "jointAdequacies", None) or []:
        for aa in getattr(ja, "assessments", None) or []:
            method = getattr(aa, "method", None)
            if isinstance(method, str) and method not in refs:
                refs.append(method)
    return refs


def register_extension_fixture_plugins(
    registry: PluginRegistry,
    bundle: Any,
) -> None:
    """Register live extension-pack plugins for a bundle's binding URIs.

    Follows the existing register pattern:

    - evaluator handlers under ``EVALUATOR_BINDING`` with
      ``{evaluator_id}::{expr_kind}`` ids (the key shape
      ``RegistryEvaluatorBindings`` resolves) — one registration per expr
      kind the pack defines for the evaluator's binding URI (predicate,
      dynamic, judged);
    - baseline criterion resolvers under the registry-only
      ``BASELINE_HANDLER`` kind keyed by criterion URI;
    - judged-criterion callables referenced by bundle claims under the
      registry-only ``CRITERION_BINDING`` kind keyed by criterion URI;
    - adequacy method callables referenced by bundle anchors/joint groups
      under ``ADEQUACY_METHOD`` (wired into ``services["adequacy_handlers"]``
      by ``build_services_from_registry``);
    - bridge ``via`` URIs under the registry-only ``TRANSPORT_HANDLER`` kind
      as documentation markers (the builtin ``execute_transport`` implements
      metadata_only/preserve/degrade internally and never calls them).
    """
    for evaluator in getattr(bundle, "evaluators", None) or []:
        binding_uri = getattr(evaluator, "binding", None)
        kind_factories = _LIVE_EVALUATOR_HANDLER_FACTORIES.get(binding_uri)
        if kind_factories is None:
            continue
        for expr_kind in sorted(kind_factories):
            factory = kind_factories[expr_kind]
            plugin_id = f"{evaluator.id}::{expr_kind}"
            if not registry.has(EVALUATOR_BINDING, plugin_id):
                registry.register(
                    EVALUATOR_BINDING,
                    plugin_id,
                    factory(),
                    description=(
                        f"Live extension {expr_kind} binding {binding_uri} "
                        f"for {evaluator.id}"
                    ),
                )

    for baseline in getattr(bundle, "baselines", None) or []:
        criterion = getattr(baseline, "criterion", None)
        ref = getattr(criterion, "ref", None)
        resolver = _LIVE_BASELINE_RESOLVERS.get(ref) if isinstance(ref, str) else None
        if resolver is None:
            continue
        if not registry.has(BASELINE_HANDLER, ref):
            registry.register(
                BASELINE_HANDLER,
                ref,
                resolver,
                description=f"Live extension baseline criterion {ref}",
            )

    for criterion_ref in _collect_judged_criterion_refs(bundle):
        handler = _LIVE_CRITERION_BINDINGS.get(criterion_ref)
        if handler is None:
            continue
        if not registry.has(CRITERION_BINDING, criterion_ref):
            registry.register(
                CRITERION_BINDING,
                criterion_ref,
                handler,
                description=f"Live extension judged criterion {criterion_ref}",
            )

    for method_ref in _collect_adequacy_method_refs(bundle):
        handler = _LIVE_ADEQUACY_METHODS.get(method_ref)
        if handler is None:
            continue
        if not registry.has(ADEQUACY_METHOD, method_ref):
            registry.register(
                ADEQUACY_METHOD,
                method_ref,
                handler,
                description=f"Live extension adequacy method {method_ref}",
            )

    for bridge in getattr(bundle, "bridges", None) or []:
        via = getattr(bridge, "via", None)
        if via not in _LIVE_BRIDGE_VIA_URIS:
            continue
        if not registry.has(TRANSPORT_HANDLER, via):
            registry.register(
                TRANSPORT_HANDLER,
                via,
                _bridge_via_marker(via),
                description=f"Live extension bridge via marker {via}",
            )


def build_live_fixture_services(bundle: Any) -> dict[str, Any] | None:
    """Build live-evaluation services for a bundle bound to the extension pack.

    Returns ``None`` unless the bundle declares at least one evaluator and
    EVERY evaluator's binding URI is in the live pack — vendored corpus
    bundles (``test://eval/atoms_v1`` etc.) therefore never activate the
    live path.  Otherwise returns a services dict containing
    ``evaluator_bindings`` (registry-backed atom-level handlers) and, when
    any bundle baseline criterion ref is in the pack,
    ``baseline_criterion_resolver`` wired for the §16.6.3 shared_state cache
    machinery in ``runtime.builtins.materialize_referenced_baselines``.
    """
    evaluators = getattr(bundle, "evaluators", None) or []
    if not evaluators:
        return None
    for evaluator in evaluators:
        if getattr(evaluator, "binding", None) not in _LIVE_EVALUATOR_HANDLER_FACTORIES:
            return None

    registry = PluginRegistry()
    register_extension_fixture_plugins(registry, bundle)
    services = build_services_from_registry(registry)

    resolvers = {
        meta.plugin_id: meta.handler
        for meta in registry.list_plugins(BASELINE_HANDLER)
    }
    if resolvers:
        services["baseline_criterion_resolver"] = _dispatching_baseline_resolver(
            resolvers
        )
    return services


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ATOMS_V2_URI",
    "BASELINE_BY_CONTEXT_V1_URI",
    "BASELINE_MATCH_V1_URI",
    "PARADOX_BRIDGE_AMPLIFICATION_V1_URI",
    "PARADOX_BRIDGE_NAIVE_EXTRAPOLATION_V1_URI",
    "PARADOX_CRITERION_TARSKI_GATE_V1_URI",
    "PARADOX_EVAL_COLLAPSE_V1_URI",
    "PARADOX_EVAL_GR_SEMICLASSICAL_V1_URI",
    "PARADOX_EVAL_LIAR_V1_URI",
    "PARADOX_EVAL_UNITARY_V1_URI",
    "PARADOX_EVAL_ZFC_V1_URI",
    "PARADOX_EVAL_ZF_V1_URI",
    "PARADOX_METHOD_GW_WAVEFORMS_V1_URI",
    "PARADOX_METHOD_LEBESGUE_MEASURE_V1_URI",
    "PARADOX_METHOD_QG_TBD_V1_URI",
    "AtomTruthEvalHandler",
    "BaselineMatchEvalHandler",
    "DynamicTruthEvalHandler",
    "FixtureAdequacyHandler",
    "FixtureAdjudicator",
    "FixtureEvalHandlerForEvaluator",
    "FixtureSupportHandler",
    "JudgedCriterionEvalHandler",
    "build_live_fixture_services",
    "by_context_baseline_resolver",
    "register_extension_fixture_plugins",
    "register_fixture_plugins",
    "tarski_self_reference_criterion",
]
