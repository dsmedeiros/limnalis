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
    AdequacyAssessmentNode,
    AnchorNode,
    BundleNode,
    CausalExprNode,
    ClaimBlockNode,
    ClaimNode,
    CriterionExprNode,
    DeclarationExprNode,
    DynamicExprNode,
    EmergenceExprNode,
    EvidenceNode,
    EvidenceRelationNode,
    FacetValueMap,
    FrameNode,
    FrameOrPatternNode,
    FramePatternNode,
    JointAdequacyNode,
    JudgedExprNode,
    LogicalExprNode,
    NoteExprNode,
    PredicateExprNode,
    ResolutionPolicyNode,
    TimeCtxNode,
)
from ..models.conformance import TruthValue
from .models import (
    AdequacyResult,
    AnchorAdequacyResult,
    BaselineState,
    ClaimClassification,
    ClaimEvidenceView,
    EvalNode,
    EvaluationEnvironment,
    EvaluatorBindings,
    JointAdequacyResult,
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


def _aggregate_support(
    evals: list[EvalNode],
    aggregate_truth: TruthValue | None = None,
) -> str | None:
    """Aggregate support values for paraconsistent union.

    Priority order per spec:
    - conflicted if any evaluator conflicted OR aggregate truth is B[evaluator_conflict]
    - else partial if any partial
    - else supported if any supported
    - else inapplicable if all inapplicable
    - else absent
    """
    supports = [e.support for e in evals if e.support is not None]
    if not supports:
        return None

    # If aggregate truth is B (evaluator_conflict), force conflicted
    if aggregate_truth == "B":
        return "conflicted"

    if "conflicted" in supports:
        return "conflicted"
    if "partial" in supports:
        return "partial"
    if "supported" in supports:
        return "supported"
    if all(s == "inapplicable" for s in supports):
        return "inapplicable"
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

        # Determine reason
        reason: str | None = None
        truth_set = set(truths)
        if "T" in truth_set and "F" in truth_set:
            reason = "evaluator_conflict"
        else:
            # Preserve unique inherited reason
            reasons = [e.reason for e in evals if e.reason is not None]
            unique_reasons = list(dict.fromkeys(reasons))
            if len(unique_reasons) == 1:
                reason = unique_reasons[0]

        # Support aggregation (uses aggregate truth for conflict detection)
        agg_support = _aggregate_support(evals, aggregate_truth=agg_truth)

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
        # Filter to declared policy members if specified
        if policy.members:
            filtered = {k: v for k, v in per_evaluator.items() if k in policy.members}
        else:
            filtered = per_evaluator
        if not filtered:
            return EvalNode(truth="N", reason="no_evaluators")
        return adjudicator(filtered)

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


def _detect_basis_cycles(
    assessment_id: str,
    basis: list[str],
    all_claims: dict[str, Any],
    all_anchors: dict[str, AnchorNode],
    visited: set[str] | None = None,
) -> bool:
    """Detect circular basis dependency for an adequacy assessment.

    An assessment A depends on assessment B if A.basis references a claim
    that uses an anchor whose adequacy includes B. Follow the chain and
    detect if we revisit the starting assessment.
    """
    if visited is None:
        visited = set()
    if assessment_id in visited:
        return True
    visited = visited | {assessment_id}

    for claim_id in basis:
        claim = all_claims.get(claim_id)
        if claim is None:
            continue
        # The claim uses anchors; each of those anchors' assessments are
        # transitive dependencies
        for anchor_id in getattr(claim, "usesAnchors", []):
            anchor = all_anchors.get(anchor_id)
            if anchor is None:
                continue
            for aa in anchor.adequacy:
                if _detect_basis_cycles(aa.id, aa.basis, all_claims, all_anchors, visited):
                    return True
    return False


def _evaluate_single_assessment(
    aa: AdequacyAssessmentNode,
    all_claims: dict[str, Any],
    all_anchors: dict[str, AnchorNode],
    services: dict[str, Any],
) -> tuple[AdequacyResult, Diagnostics]:
    """Evaluate a single adequacy assessment and return its result."""
    diags: Diagnostics = []

    # Check for circular basis dependency (diagnostic rule 25)
    if aa.basis and _detect_basis_cycles(aa.id, aa.basis, all_claims, all_anchors):
        diags.append({
            "severity": "error",
            "code": "lint.adequacy.circular_basis",
            "phase": "license",
            "subject": aa.id,
            "message": f"Circular basis dependency detected for assessment {aa.id}",
        })
        return AdequacyResult(
            assessment_id=aa.id,
            task=aa.task,
            producer=aa.producer,
            adequate=False,
            truth="N",
            reason="circular_dependency",
            score=None,
            threshold=aa.threshold,
            provenance=[aa.producer, aa.id],
        ), diags

    # Determine the effective score
    effective_score = aa.score

    # If score is "N" (explicitly marked as not-available), treat as None
    if effective_score == "N":
        effective_score = None

    # If no score provided, check if a method handler is available in services
    if effective_score is None:
        method_handler = services.get("adequacy_handlers", {}).get(aa.method)
        if method_handler is not None:
            computed = method_handler(aa)
            if isinstance(computed, (int, float)):
                effective_score = float(computed)

    # Determine adequacy
    if effective_score is not None:
        adequate = effective_score >= aa.threshold
        truth: TruthValue = "T" if adequate else "F"
    else:
        # Score-omitted computed assessments: adequate by default
        adequate = True
        truth = "T"

    return AdequacyResult(
        assessment_id=aa.id,
        task=aa.task,
        producer=aa.producer,
        adequate=adequate,
        truth=truth,
        reason=None,
        score=effective_score,
        threshold=aa.threshold,
        provenance=[aa.producer, aa.id],
    ), diags


def _aggregate_adequacy_by_policy(
    assessments: list[AdequacyResult],
    policy_kind: str,
    policy_order: list[str] | None = None,
    adjudicator_handler: Callable[..., Any] | None = None,
) -> tuple[TruthValue, str | None]:
    """Aggregate multiple assessment results under a given policy kind.

    Returns (truth, reason).
    """
    if not assessments:
        return "N", "no_assessments"

    if policy_kind == "single":
        # Single: use the sole assessment directly
        return assessments[0].truth, assessments[0].reason

    elif policy_kind == "paraconsistent_union":
        truths = [a.truth for a in assessments]
        agg = _aggregate_truth(truths)
        truth_set = set(truths)
        reason: str | None = None
        if "T" in truth_set and "F" in truth_set:
            agg = "B"
            reason = "method_conflict"
        elif agg == "B":
            reason = "method_conflict"
        return agg, reason

    elif policy_kind == "priority_order":
        order = policy_order or [a.producer for a in assessments]
        producer_map = {a.producer: a for a in assessments}
        for pid in order:
            if pid in producer_map and producer_map[pid].truth != "N":
                return producer_map[pid].truth, producer_map[pid].reason
        return "N", "all_non_decisive"

    elif policy_kind == "adjudicated":
        if adjudicator_handler is not None:
            result = adjudicator_handler(assessments)
            if isinstance(result, tuple):
                return result
            return result.truth if hasattr(result, "truth") else "N", None
        # No handler: fall back to paraconsistent_union
        return _aggregate_adequacy_by_policy(assessments, "paraconsistent_union")

    return "N", f"unknown_policy_{policy_kind}"


def evaluate_adequacy_set(
    anchor_ids: list[str],
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[dict[str, Any], MachineState, Diagnostics]:
    """Evaluate adequacy for a set of anchors.

    For each anchor, evaluates individual adequacy assessments, groups them
    by task, and aggregates using the anchor's adequacy_policy (or defaults
    to 'single' when only one assessment per task).

    Also evaluates joint adequacy groups.

    Diagnostic rules implemented:
    - Rule 24: lint.adequacy.missing_policy_multi_assessment
    - Rule 25: lint.adequacy.circular_basis
    """
    diags: Diagnostics = []
    bundle: BundleNode | None = services.get("__bundle__")
    if bundle is None:
        # No bundle available - cannot evaluate adequacy
        return {}, machine_state, diags

    # Build lookup maps
    anchors_by_id: dict[str, AnchorNode] = {a.id: a for a in bundle.anchors}
    policies_by_id: dict[str, ResolutionPolicyNode] = {}
    # Bundle may have multiple resolution policies; index them
    # The main one is bundle.resolutionPolicy, but anchors reference by id
    policies_by_id[bundle.resolutionPolicy.id] = bundle.resolutionPolicy
    # Also check if there are additional policies (some bundles declare extra ones)
    # Walk all fields looking for ResolutionPolicyNode objects stored as list
    # In practice, additional policies are stored outside the bundle model;
    # we look them up from services if provided
    extra_policies = services.get("__resolution_policies__", {})
    policies_by_id.update(extra_policies)

    all_claims: dict[str, Any] = {}
    for block in bundle.claimBlocks:
        for claim in block.claims:
            all_claims[claim.id] = claim

    adequacy_handler = services.get("adequacy_adjudicator")

    # Per-assessment results
    per_assessment: dict[str, AdequacyResult] = {}
    # Per-anchor, per-task aggregated results
    per_anchor_task: dict[str, AnchorAdequacyResult] = {}
    # Joint adequacy results
    joint_results: dict[str, JointAdequacyResult] = {}

    # Phase 1: evaluate individual assessments per anchor
    for anchor_id in anchor_ids:
        anchor = anchors_by_id.get(anchor_id)
        if anchor is None:
            continue

        # Group assessments by task
        by_task: dict[str, list[AdequacyAssessmentNode]] = {}
        for aa in anchor.adequacy:
            by_task.setdefault(aa.task, []).append(aa)

        for task, task_assessments in by_task.items():
            # Evaluate each assessment individually
            task_results: list[AdequacyResult] = []
            for aa in task_assessments:
                result, aa_diags = _evaluate_single_assessment(
                    aa, all_claims, anchors_by_id, services,
                )
                per_assessment[aa.id] = result
                task_results.append(result)
                diags.extend(aa_diags)

            # Determine aggregation policy
            if len(task_assessments) > 1:
                # Multiple same-task assessments: need adequacy_policy
                policy_id = anchor.adequacyPolicy
                if policy_id is None:
                    # Diagnostic rule 24: missing policy for multi-assessment
                    diags.append({
                        "severity": "warning",
                        "code": "lint.adequacy.missing_policy_multi_assessment",
                        "phase": "license",
                        "subject": anchor_id,
                        "message": (
                            f"Multiple same-task assessments for anchor {anchor_id} "
                            f"task {task} but no adequacy_policy declared"
                        ),
                    })
                    agg_truth: TruthValue = "N"
                    agg_reason: str | None = "missing_policy"
                else:
                    policy = policies_by_id.get(policy_id)
                    if policy is not None:
                        agg_truth, agg_reason = _aggregate_adequacy_by_policy(
                            task_results,
                            policy.kind,
                            policy_order=policy.order,
                            adjudicator_handler=adequacy_handler,
                        )
                    else:
                        # Policy referenced but not found - treat as missing
                        agg_truth = "N"
                        agg_reason = "missing_policy"
            else:
                # Single assessment: use directly
                agg_truth = task_results[0].truth
                agg_reason = task_results[0].reason

            key = f"{anchor_id}:{task}"
            provenance: list[str] = []
            for r in task_results:
                provenance.extend(r.provenance)
            per_anchor_task[key] = AnchorAdequacyResult(
                anchor_id=anchor_id,
                task=task,
                truth=agg_truth,
                reason=agg_reason,
                per_assessment=task_results,
                provenance=sorted(set(provenance)),
            )

    # Phase 2: evaluate joint adequacy groups
    for ja in bundle.jointAdequacies:
        ja_assessment_results: list[AdequacyResult] = []
        for aa in ja.assessments:
            result, aa_diags = _evaluate_single_assessment(
                aa, all_claims, anchors_by_id, services,
            )
            per_assessment[aa.id] = result
            ja_assessment_results.append(result)
            diags.extend(aa_diags)

        # Aggregate joint assessments
        if len(ja.assessments) > 1:
            policy_id = ja.adequacyPolicy
            if policy_id is None:
                diags.append({
                    "severity": "warning",
                    "code": "lint.adequacy.missing_policy_multi_assessment",
                    "phase": "license",
                    "subject": ja.id,
                    "message": (
                        f"Multiple assessments for joint adequacy {ja.id} "
                        f"but no adequacy_policy declared"
                    ),
                })
                ja_truth: TruthValue = "N"
                ja_reason: str | None = "missing_policy"
            else:
                policy = policies_by_id.get(policy_id)
                if policy is not None:
                    ja_truth, ja_reason = _aggregate_adequacy_by_policy(
                        ja_assessment_results,
                        policy.kind,
                        policy_order=policy.order,
                        adjudicator_handler=adequacy_handler,
                    )
                else:
                    ja_truth = "N"
                    ja_reason = "missing_policy"
        else:
            ja_truth = ja_assessment_results[0].truth
            ja_reason = ja_assessment_results[0].reason

        ja_provenance: list[str] = []
        for r in ja_assessment_results:
            ja_provenance.extend(r.provenance)
        joint_results[ja.id] = JointAdequacyResult(
            joint_id=ja.id,
            anchors=ja.anchors,
            truth=ja_truth,
            reason=ja_reason,
            per_assessment=ja_assessment_results,
            provenance=sorted(set(ja_provenance)),
        )

    # Store results in machine_state
    new_state = machine_state.model_copy(deep=True)
    new_state.adequacy_store = {
        "per_assessment": {k: v.model_dump() for k, v in per_assessment.items()},
        "per_anchor_task": {k: v.model_dump() for k, v in per_anchor_task.items()},
        "joint": {k: v.model_dump() for k, v in joint_results.items()},
    }

    results = {
        "per_assessment": per_assessment,
        "per_anchor_task": per_anchor_task,
        "joint": joint_results,
    }

    return results, new_state, diags


# Protocol #5: compose_license — no assigned runner phase (deferred to future milestone)
def compose_license(
    claim_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[LicenseResult, MachineState, Diagnostics]:
    """Stub: compose license for a claim. Requires domain logic."""
    raise NotImplementedError("compose_license requires domain-specific implementation")


def _get_evaluator_bindings(services: dict[str, Any]) -> EvaluatorBindings | None:
    """Extract evaluator bindings from services dict."""
    return services.get("evaluator_bindings")


def _dispatch_to_binding(
    expr: Any,
    expr_type: str,
    claim: ClaimNode,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TruthCore, MachineState, Diagnostics]:
    """Dispatch an expression to the evaluator binding handler.

    Returns N[missing_binding] if no handler is found.
    Never propagates exceptions from the handler.
    """
    diags: Diagnostics = []
    bindings = _get_evaluator_bindings(services)
    if bindings is None:
        return (
            TruthCore(truth="N", reason="missing_binding", provenance=[evaluator_id]),
            machine_state,
            diags,
        )

    try:
        handler = bindings.get_handler(evaluator_id, expr_type)
    except Exception:
        handler = None

    if handler is None:
        return (
            TruthCore(truth="N", reason="missing_binding", provenance=[evaluator_id]),
            machine_state,
            diags,
        )

    try:
        result = handler(expr, claim, step_ctx, machine_state)
        return result, machine_state, diags
    except Exception as exc:
        diags.append({
            "severity": "warning",
            "code": "binding_handler_error",
            "evaluator_id": evaluator_id,
            "expr_type": expr_type,
            "message": str(exc),
        })
        return (
            TruthCore(truth="N", reason="missing_binding", provenance=[evaluator_id]),
            machine_state,
            diags,
        )


# Truth ordering for logical operations: T > B > N > F
_TRUTH_ORDER: dict[TruthValue, int] = {"T": 3, "B": 2, "N": 1, "F": 0}
_ORDER_TO_TRUTH: dict[int, TruthValue] = {v: k for k, v in _TRUTH_ORDER.items()}


def _truth_min(values: list[TruthValue]) -> TruthValue:
    """AND semantics: min over the truth lattice T > B > N > F."""
    if not values:
        return "N"
    return _ORDER_TO_TRUTH[min(_TRUTH_ORDER[v] for v in values)]


def _truth_max(values: list[TruthValue]) -> TruthValue:
    """OR semantics: max over the truth lattice T > B > N > F."""
    if not values:
        return "N"
    return _ORDER_TO_TRUTH[max(_TRUTH_ORDER[v] for v in values)]


def _truth_flip(value: TruthValue) -> TruthValue:
    """NOT semantics: flip(T)=F, flip(F)=T, flip(B)=B, flip(N)=N."""
    if value == "T":
        return "F"
    if value == "F":
        return "T"
    return value  # B and N are fixed points


def _eval_logical_expr(
    expr: LogicalExprNode,
    claim: ClaimNode,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TruthCore, MachineState, Diagnostics]:
    """Evaluate a LogicalExpr by recursing into sub-expressions."""
    all_diags: Diagnostics = []
    sub_truths: list[TruthValue] = []
    provenance: set[str] = {evaluator_id}

    for sub_expr in expr.args:
        sub_core, machine_state, sub_diags = _eval_expr_inner(
            sub_expr, claim, evaluator_id, step_ctx, machine_state, services
        )
        all_diags.extend(sub_diags)
        sub_truths.append(sub_core.truth)
        provenance.update(sub_core.provenance)

    if expr.op == "and":
        result_truth = _truth_min(sub_truths)
    elif expr.op == "or":
        result_truth = _truth_max(sub_truths)
    elif expr.op == "not":
        result_truth = _truth_flip(sub_truths[0])
    elif expr.op == "implies":
        # A -> B = OR(NOT(A), B)
        not_a = _truth_flip(sub_truths[0])
        result_truth = _truth_max([not_a, sub_truths[1]])
    elif expr.op == "iff":
        # A <-> B = AND(IMPLIES(A,B), IMPLIES(B,A))
        implies_ab = _truth_max([_truth_flip(sub_truths[0]), sub_truths[1]])
        implies_ba = _truth_max([_truth_flip(sub_truths[1]), sub_truths[0]])
        result_truth = _truth_min([implies_ab, implies_ba])
    else:
        result_truth = "N"

    return (
        TruthCore(truth=result_truth, provenance=sorted(provenance)),
        machine_state,
        all_diags,
    )


def _eval_declaration_expr(
    expr: DeclarationExprNode,
    evaluator_id: str,
) -> TruthCore:
    """Evaluate a DeclarationExpr: return the declared truth value directly."""
    declared_map: dict[str, TruthValue] = {
        "T": "T", "F": "F", "B": "B", "N": "N",
        "true": "T", "false": "F", "both": "B", "neither": "N",
    }
    truth = declared_map.get(expr.declaredAs, "N")
    return TruthCore(
        truth=truth,
        reason=f"declared_as_{expr.declaredAs}",
        provenance=[evaluator_id],
    )


def _eval_judged_expr(
    expr: JudgedExprNode,
    claim: ClaimNode,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TruthCore, MachineState, Diagnostics]:
    """Evaluate a JudgedExpr: dispatch to judged evaluator binding, else eval inner."""
    diags: Diagnostics = []

    # Try dispatching to the judged evaluator binding using JudgedExpr type
    bindings = _get_evaluator_bindings(services)
    if bindings is not None:
        try:
            handler = bindings.get_handler(evaluator_id, "JudgedExpr")
        except Exception:
            handler = None

        if handler is not None:
            try:
                result = handler(expr, claim, step_ctx, machine_state)
                return result, machine_state, diags
            except Exception as exc:
                diags.append({
                    "severity": "warning",
                    "code": "judged_binding_error",
                    "evaluator_id": evaluator_id,
                    "message": str(exc),
                })

    # Fall back to evaluating the inner expression
    inner_core, machine_state, inner_diags = _eval_expr_inner(
        expr.expr, claim, evaluator_id, step_ctx, machine_state, services
    )
    diags.extend(inner_diags)
    return inner_core, machine_state, diags


def _eval_expr_inner(
    expr: Any,
    claim: ClaimNode,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TruthCore, MachineState, Diagnostics]:
    """Inner dispatch for evaluating an expression node.

    Routes based on expression type:
    - Leaf expressions (Predicate, Dynamic, Causal, Emergence, Criterion) -> binding dispatch
    - LogicalExpr -> internal recursive evaluation
    - DeclarationExpr -> direct truth return
    - JudgedExpr -> judged binding dispatch with inner fallback
    - NoteExpr -> safety fallback returning N[note_expr]
    """
    expr_type = getattr(expr, "node", None) or type(expr).__name__

    # --- Leaf dispatch to evaluator bindings ---
    if isinstance(expr, (PredicateExprNode, DynamicExprNode, CausalExprNode, EmergenceExprNode)):
        return _dispatch_to_binding(
            expr, expr_type, claim, evaluator_id, step_ctx, machine_state, services
        )

    # --- CriterionExpr: leaf dispatch ---
    if isinstance(expr, CriterionExprNode):
        return _dispatch_to_binding(
            expr, "CriterionExpr", claim, evaluator_id, step_ctx, machine_state, services
        )

    # --- LogicalExpr: internal recursive evaluation ---
    if isinstance(expr, LogicalExprNode):
        return _eval_logical_expr(
            expr, claim, evaluator_id, step_ctx, machine_state, services
        )

    # --- DeclarationExpr: return declared truth ---
    if isinstance(expr, DeclarationExprNode):
        core = _eval_declaration_expr(expr, evaluator_id)
        return core, machine_state, []

    # --- JudgedExpr: judged binding dispatch with inner fallback ---
    if isinstance(expr, JudgedExprNode):
        return _eval_judged_expr(
            expr, claim, evaluator_id, step_ctx, machine_state, services
        )

    # --- NoteExpr: safety fallback (should not normally reach here) ---
    if isinstance(expr, NoteExprNode):
        return (
            TruthCore(truth="N", reason="note_expr", provenance=[evaluator_id]),
            machine_state,
            [],
        )

    # --- Unknown expression type: localize to N[missing_binding] ---
    return (
        TruthCore(truth="N", reason="missing_binding", provenance=[evaluator_id]),
        machine_state,
        [],
    )


def eval_expr(
    claim: ClaimNode,
    evaluator_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TruthCore, MachineState, Diagnostics]:
    """Evaluate a claim expression via delegated leaf dispatch.

    Routes expression evaluation based on type:
    - Leaf expressions (Predicate, Dynamic, Causal, Emergence, Criterion):
      dispatched to evaluator binding handlers via services["evaluator_bindings"]
    - LogicalExpr: evaluated internally with recursive sub-expression evaluation
    - DeclarationExpr: returns declared truth value directly
    - JudgedExpr: dispatched to judged evaluator binding, falls back to inner expr
    - NoteExpr: safety fallback returning N[note_expr]
    - Missing handler: localizes to N[missing_binding], never propagates exceptions
    """
    expr = claim.expr
    return _eval_expr_inner(
        expr, claim, evaluator_id, step_ctx, machine_state, services
    )


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
