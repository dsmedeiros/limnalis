"""Built-in implementations of Limnalis primitive operations.

Implements the 6 fully internal primitives and provides stubs for the 7 that
require domain/external logic.

NOTE on section numbering: Section numbers in this file (e.g. "2. build_step_context",
"7. classify_claim") follow the Protocol numbering defined in primitives.py (1-13),
NOT the runner phase numbering (1-12). The runner has 12 phases because compose_license
(Protocol #5) has no assigned runner phase yet.
"""

from __future__ import annotations

from typing import Any, Callable

from ..models.ast import (
    BundleNode,
    ClaimBlockNode,
    ClaimNode,
    EvidenceNode,
    EvidenceRelationNode,
    FacetValueMap,
    FrameNode,
    FrameOrPatternNode,
    FramePatternNode,
    NoteExprNode,
    ResolutionPolicyNode,
    TimeCtxNode,
)
from ..models.conformance import TruthValue
from .models import (
    BaselineState,
    ClaimClassification,
    ClaimEvidenceView,
    EvalNode,
    EvaluationEnvironment,
    LicenseResult,
    MachineState,
    SessionConfig,
    StepConfig,
    StepContext,
    SupportResult,
    TruthCore,
)

Diagnostics = list[dict[str, Any]]

# ===================================================================
# FACETS used for frame merging
# ===================================================================

_FRAME_FACETS = ("system", "namespace", "scale", "task", "regime", "observer", "version")


# ===================================================================
# 2. build_step_context  (fully internal)
# ===================================================================


def _frame_facets(frame: FrameOrPatternNode) -> dict[str, str | None]:
    """Extract facet values from a Frame or FramePattern node."""
    if isinstance(frame, FrameNode):
        return {f: getattr(frame, f, None) for f in _FRAME_FACETS}
    elif isinstance(frame, FramePatternNode):
        return {f: getattr(frame.facets, f, None) for f in _FRAME_FACETS}
    # discriminated union — should not happen
    raise TypeError(f"Unexpected frame type: {type(frame)}")


def _merge_frame_facets(*frames: FrameOrPatternNode | None) -> dict[str, str | None]:
    """Merge facets from frames; later values override earlier ones."""
    merged: dict[str, str | None] = {f: None for f in _FRAME_FACETS}
    for frame in frames:
        if frame is None:
            continue
        facets = _frame_facets(frame)
        for k, v in facets.items():
            if v is not None:
                merged[k] = v
    return merged


def _facets_to_frame(facets: dict[str, str | None]) -> FrameOrPatternNode:
    """Build a Frame or FramePattern from merged facets.

    Returns a FrameNode if all required facets are present, else a FramePatternNode.
    """
    required = ("system", "namespace", "scale", "task", "regime")
    if all(facets.get(f) is not None for f in required):
        return FrameNode(
            system=facets["system"],  # type: ignore[arg-type]
            namespace=facets["namespace"],  # type: ignore[arg-type]
            scale=facets["scale"],  # type: ignore[arg-type]
            task=facets["task"],  # type: ignore[arg-type]
            regime=facets["regime"],  # type: ignore[arg-type]
            observer=facets.get("observer"),
            version=facets.get("version"),
        )
    # Build a pattern with only non-None facets
    non_none = {k: v for k, v in facets.items() if v is not None}
    if not non_none:
        # Degenerate case: no facets at all — return minimal pattern
        non_none = {"system": "unknown"}
    return FramePatternNode(facets=FacetValueMap(**non_none))


def build_step_context(
    bundle: BundleNode,
    session: SessionConfig,
    step: StepConfig,
    env: EvaluationEnvironment,
) -> StepContext:
    """Build effective step context via merge semantics.

    effective_frame = merge(bundle.frame, session.base_frame, step.frame_override)
    effective_time  = step.time ?? session.base_time ?? bundle.time ?? env.clock
    effective_history = resolved step.history_binding if present, else env.history
    """
    diags: Diagnostics = []

    # --- frame merge ---
    merged_facets = _merge_frame_facets(bundle.frame, session.base_frame, step.frame_override)

    # Emit diagnostic if all merged facets are None (degenerate case)
    if all(v is None for v in merged_facets.values()):
        diags.append({
            "severity": "warning",
            "code": "empty_effective_frame",
            "message": "All frame facets are None after merging bundle, session, and step frames; "
                       "falling back to degenerate frame. This may indicate misconfiguration.",
        })

    effective_frame = _facets_to_frame(merged_facets)

    # --- time precedence ---
    effective_time: TimeCtxNode | None = None
    if step.time is not None:
        effective_time = step.time
    elif session.base_time is not None:
        effective_time = session.base_time
    elif bundle.time is not None:
        effective_time = bundle.time
    elif env.clock is not None:
        effective_time = TimeCtxNode(kind="point", t=env.clock)

    # --- history ---
    if step.history_binding is not None:
        effective_history = {"binding": step.history_binding}
        diags.append({
            "severity": "info",
            "code": "history_binding_used",
            "subject": step.id,
            "message": f"Step uses explicit history binding: {step.history_binding}",
        })
    else:
        effective_history = dict(env.history)

    return StepContext(
        effective_frame=effective_frame,
        effective_time=effective_time,
        effective_history=effective_history,
        diagnostics=diags,
    )


# ===================================================================
# 7. classify_claim  (fully internal)
# ===================================================================


def classify_claim(claim: ClaimNode) -> ClaimClassification:
    """Classify whether a claim is evaluable.

    NoteExpr => evaluable = false
    All other expression kinds => evaluable = true
    """
    expr = claim.expr
    # Unwrap discriminated union to get the concrete node
    expr_kind = expr.node

    if isinstance(expr, NoteExprNode):
        return ClaimClassification(
            claim_id=claim.id,
            evaluable=False,
            expr_kind=expr_kind,
            reason="NoteExpr claims are non-evaluable",
        )
    return ClaimClassification(
        claim_id=claim.id,
        evaluable=True,
        expr_kind=expr_kind,
    )


# ===================================================================
# 6. build_evidence_view  (fully internal)
# ===================================================================


def build_evidence_view(
    claim: ClaimNode,
    bundle: BundleNode,
    step_ctx: StepContext,
    machine_state: MachineState,
) -> tuple[ClaimEvidenceView, MachineState, Diagnostics]:
    """Build declared per-claim evidence view.

    - explicitEvidence from claim.refs matching bundle evidence ids
    - relatedEvidence empty for now
    - relations from declared EvidenceRelation entries involving those evidence ids
    - crossConflictScore = max conflicts score if any
    - completenessSummary = min completeness among relevant evidence items if any
    """
    diags: Diagnostics = []

    # Index bundle evidence and relations
    evidence_by_id: dict[str, EvidenceNode] = {e.id: e for e in bundle.evidence}
    all_relations: list[EvidenceRelationNode] = list(bundle.evidenceRelations)

    # Explicit evidence from claim.refs
    explicit: list[EvidenceNode] = []
    explicit_ids: set[str] = set()
    for ref_id in claim.refs:
        if ref_id in evidence_by_id:
            explicit.append(evidence_by_id[ref_id])
            explicit_ids.add(ref_id)

    # Relations involving the explicit evidence ids
    relevant_relations: list[EvidenceRelationNode] = [
        r for r in all_relations if r.lhs in explicit_ids or r.rhs in explicit_ids
    ]

    # crossConflictScore = max conflicts score
    conflict_scores = [
        r.score for r in relevant_relations if r.kind == "conflicts" and r.score is not None
    ]
    cross_conflict_score = max(conflict_scores) if conflict_scores else None

    # completenessSummary = min completeness among relevant evidence
    completeness_values = [e.completeness for e in explicit if e.completeness is not None]
    completeness_summary = min(completeness_values) if completeness_values else None

    view = ClaimEvidenceView(
        claim_id=claim.id,
        explicit_evidence=explicit,
        related_evidence=[],
        relations=relevant_relations,
        cross_conflict_score=cross_conflict_score,
        completeness_summary=completeness_summary,
    )

    # Store in machine state
    new_state = machine_state.model_copy(deep=True)
    new_state.evidence_views[claim.id] = view

    return view, new_state, diags


# ===================================================================
# 10. assemble_eval  (fully internal)
# ===================================================================


def assemble_eval(
    truth_core: TruthCore,
    support_result: SupportResult,
    evaluator_id: str,
) -> EvalNode:
    """Assemble TruthCore + SupportResult + evaluator_id into an EvalNode.

    - provenance = union(truthCore.provenance, supportResult.provenance, [evaluator_id])
    - confidence from TruthCore
    - reason from TruthCore
    - support from SupportResult
    """
    prov_set: set[str] = set(truth_core.provenance)
    prov_set.update(support_result.provenance)
    prov_set.add(evaluator_id)

    return EvalNode(
        truth=truth_core.truth,
        reason=truth_core.reason,
        support=support_result.support,
        confidence=truth_core.confidence,
        provenance=sorted(prov_set),
    )


# ===================================================================
# 11. apply_resolution_policy  (fully internal)
# ===================================================================

# Truth lattice for paraconsistent union:
#   T + T = T,  F + F = F,  N + N = N
#   T + F = B,  T + B = B,  F + B = B
#   T + N = T,  F + N = F,  B + N = B

_TRUTH_JOIN: dict[tuple[TruthValue, TruthValue], TruthValue] = {
    ("T", "T"): "T",
    ("F", "F"): "F",
    ("B", "B"): "B",
    ("N", "N"): "N",
    ("T", "F"): "B",
    ("F", "T"): "B",
    ("T", "B"): "B",
    ("B", "T"): "B",
    ("F", "B"): "B",
    ("B", "F"): "B",
    ("T", "N"): "T",
    ("N", "T"): "T",
    ("F", "N"): "F",
    ("N", "F"): "F",
    ("B", "N"): "B",
    ("N", "B"): "B",
}


def _aggregate_truth(values: list[TruthValue]) -> TruthValue:
    """Aggregate truth values using the paraconsistent join lattice."""
    if not values:
        return "N"
    result = values[0]
    for v in values[1:]:
        result = _TRUTH_JOIN[(result, v)]
    return result


def _aggregate_support(evals: list[EvalNode]) -> str | None:
    """Aggregate support values.

    Per spec: union semantics — if any supported, result is supported;
    if any partial, partial; if any conflicted, conflicted; else absent.
    """
    supports = [e.support for e in evals if e.support is not None]
    if not supports:
        return None
    if "supported" in supports:
        return "supported"
    if "partial" in supports:
        return "partial"
    if "conflicted" in supports:
        return "conflicted"
    return "absent"


def apply_resolution_policy(
    per_evaluator: dict[str, EvalNode],
    policy: ResolutionPolicyNode,
    adjudicator: Callable[[dict[str, EvalNode]], EvalNode] | None = None,
) -> EvalNode:
    """Apply a resolution policy to per-evaluator results.

    Policies:
    - single: return the single evaluator's result
    - paraconsistent_union: join truth values, aggregate support
    - priority_order: choose first non-N result in order
    - adjudicated: delegate to adjudicator callable
    """
    if policy.kind == "single":
        if not policy.members or len(policy.members) != 1:
            raise ValueError("single policy requires exactly one member")
        member = policy.members[0]
        if member not in per_evaluator:
            return EvalNode(truth="N", reason="missing_evaluator", provenance=[member])
        return per_evaluator[member]

    elif policy.kind == "paraconsistent_union":
        if not per_evaluator:
            return EvalNode(truth="N", reason="no_evaluators")

        # Filter to declared policy members if specified
        if policy.members:
            filtered = {k: v for k, v in per_evaluator.items() if k in policy.members}
        else:
            filtered = per_evaluator

        if not filtered:
            return EvalNode(truth="N", reason="no_evaluators")

        evals = list(filtered.values())
        truths = [e.truth for e in evals]
        agg_truth = _aggregate_truth(truths)
        agg_support = _aggregate_support(evals)

        # Determine reason and conflict support
        reason: str | None = None
        truth_set = set(truths)
        if "T" in truth_set and "F" in truth_set:
            reason = "evaluator_conflict"
            # When evaluators disagree (truth=B), mark support as conflicted
            agg_support = "conflicted"
        else:
            # Preserve unique inherited reason
            reasons = [e.reason for e in evals if e.reason is not None]
            unique_reasons = list(dict.fromkeys(reasons))
            if len(unique_reasons) == 1:
                reason = unique_reasons[0]

        # Provenance = union
        prov: set[str] = set()
        for e in evals:
            prov.update(e.provenance)

        return EvalNode(
            truth=agg_truth,
            reason=reason,
            support=agg_support,
            confidence=None,
            provenance=sorted(prov),
        )

    elif policy.kind == "priority_order":
        if not policy.order:
            raise ValueError("priority_order policy requires order")
        for evaluator_id in policy.order:
            if evaluator_id in per_evaluator:
                ev = per_evaluator[evaluator_id]
                if ev.truth != "N":
                    return ev
        # All N or missing — return N
        prov = set()
        for e in per_evaluator.values():
            prov.update(e.provenance)
        return EvalNode(truth="N", reason="all_non_decisive", provenance=sorted(prov))

    elif policy.kind == "adjudicated":
        if adjudicator is None:
            raise ValueError("adjudicated policy requires an adjudicator callable")
        return adjudicator(per_evaluator)

    raise ValueError(f"Unknown resolution policy kind: {policy.kind}")


# ===================================================================
# 12. fold_block  (fully internal)
# ===================================================================


def fold_block(
    block: ClaimBlockNode,
    per_claim_aggregates: dict[str, EvalNode],
    per_claim_per_evaluator: dict[str, dict[str, EvalNode]],
    claim_classifications: dict[str, ClaimClassification],
    policy: ResolutionPolicyNode,
    adjudicator: Callable[[dict[str, EvalNode]], EvalNode] | None = None,
) -> tuple[dict[str, EvalNode], EvalNode]:
    """Fold a claim block into per-evaluator block truths and an aggregate.

    1. Per-evaluator block fold: for each evaluator, fold evaluable claim truths
    2. Aggregate evaluator-local block truths under apply_resolution_policy
    3. Exclude non-evaluable claims
    4. Empty evaluable set => N[empty_block]
    """
    # Collect all evaluator ids from per-claim data
    evaluator_ids: set[str] = set()
    for claim_evals in per_claim_per_evaluator.values():
        evaluator_ids.update(claim_evals.keys())

    # Identify evaluable claims in this block
    evaluable_claim_ids = [
        c.id
        for c in block.claims
        if c.id in claim_classifications and claim_classifications[c.id].evaluable
    ]

    # Empty evaluable set
    if not evaluable_claim_ids:
        empty_eval = EvalNode(truth="N", reason="empty_block", provenance=[block.id])
        per_ev_blocks: dict[str, EvalNode] = {
            eid: EvalNode(truth="N", reason="empty_block", provenance=[eid, block.id])
            for eid in evaluator_ids
        }
        return per_ev_blocks, empty_eval

    # Step 1: per-evaluator block fold
    per_evaluator_block: dict[str, EvalNode] = {}
    for evaluator_id in evaluator_ids:
        ev_truths: list[TruthValue] = []
        ev_provenance: set[str] = {evaluator_id, block.id}
        for claim_id in evaluable_claim_ids:
            if claim_id in per_claim_per_evaluator:
                claim_evals = per_claim_per_evaluator[claim_id]
                if evaluator_id in claim_evals:
                    ev_truths.append(claim_evals[evaluator_id].truth)
                    ev_provenance.update(claim_evals[evaluator_id].provenance)

        if ev_truths:
            block_truth = _aggregate_truth(ev_truths)
        else:
            block_truth = "N"

        per_evaluator_block[evaluator_id] = EvalNode(
            truth=block_truth,
            support="inapplicable",
            provenance=sorted(ev_provenance),
        )

    # Step 2: aggregate evaluator-local block truths under resolution policy
    # Build synthetic EvalNodes for aggregation
    aggregate = apply_resolution_policy(per_evaluator_block, policy, adjudicator)

    return per_evaluator_block, aggregate


# ===================================================================
# STUBS for primitives requiring external/domain logic
# ===================================================================


def resolve_ref(
    ref: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[Any, MachineState, Diagnostics]:
    """Stub: resolve a reference. Requires domain logic."""
    raise NotImplementedError("resolve_ref requires domain-specific implementation")


def resolve_baseline(
    baseline_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[Any, MachineState, Diagnostics]:
    """Stub: resolve a baseline. Requires domain logic."""
    raise NotImplementedError("resolve_baseline requires domain-specific implementation")


def evaluate_adequacy_set(
    anchor_ids: list[str],
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[dict[str, Any], MachineState, Diagnostics]:
    """Stub: evaluate adequacy for a set of anchors. Requires domain logic."""
    raise NotImplementedError("evaluate_adequacy_set requires domain-specific implementation")


# Protocol #5: compose_license — no assigned runner phase (deferred to future milestone)
def compose_license(
    claim_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[LicenseResult, MachineState, Diagnostics]:
    """Stub: compose license for a claim. Requires domain logic."""
    raise NotImplementedError("compose_license requires domain-specific implementation")


def eval_expr(
    claim: ClaimNode,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TruthCore, MachineState, Diagnostics]:
    """Stub: evaluate a claim expression. Requires domain logic."""
    raise NotImplementedError("eval_expr requires domain-specific implementation")


def synthesize_support(
    claim: ClaimNode,
    truth_core: TruthCore,
    evidence_view: ClaimEvidenceView,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[SupportResult, MachineState, Diagnostics]:
    """Stub: synthesize support assessment. Requires domain logic."""
    raise NotImplementedError("synthesize_support requires domain-specific implementation")


def execute_transport(
    bridge: Any,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[Any, MachineState, Diagnostics]:
    """Stub: execute transport query. Requires domain logic."""
    raise NotImplementedError("execute_transport requires domain-specific implementation")
