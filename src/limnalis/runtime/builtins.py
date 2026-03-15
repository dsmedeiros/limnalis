"""Built-in implementations of Limnalis primitive operations.

Implements the 6 fully internal primitives and provides stubs for the 7 that
require domain/external logic.

NOTE on section numbering: Section numbers in this file (e.g. "2. build_step_context",
"7. classify_claim") follow the Protocol numbering defined in primitives.py (1-13),
which now matches the runner phase numbering (1-13).
"""

from __future__ import annotations

from typing import Any, Callable

from ..models.ast import (
    AdequacyAssessmentNode,
    AnchorNode,
    BridgeNode,
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
    TransportNode,
)
from ..models.conformance import TruthValue
from .models import (
    AdequacyResult,
    AnchorAdequacyResult,
    AnchorLicenseEntry,
    BaselineState,
    ClaimClassification,
    ClaimEvidenceView,
    EvalNode,
    EvaluationEnvironment,
    EvaluatorBindings,
    JointAdequacyResult,
    JointLicenseEntry,
    LicenseOverall,
    LicenseResult,
    MachineState,
    SessionConfig,
    StepConfig,
    StepContext,
    SupportResult,
    TransportResult,
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


def _fold_block_truth(truths: list[TruthValue]) -> TruthValue:
    """Fold claim truths within a block using block conjunction semantics.

    Block fold rules:
    1. If any claim has truth F -> block truth is F
    2. If both B and N are present -> block truth is F (B_and_N_equals_F)
    3. If any B -> block truth is B
    4. If any N -> block truth is N
    5. Otherwise T
    """
    if not truths:
        return "N"
    truth_set = set(truths)
    if "F" in truth_set:
        return "F"
    if "B" in truth_set and "N" in truth_set:
        return "F"
    if "B" in truth_set:
        return "B"
    if "N" in truth_set:
        return "N"
    return "T"


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
            block_truth = _fold_block_truth(ev_truths)
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
            "code": "circular_dependency",
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
    reason: str | None = None
    if effective_score is not None:
        adequate = effective_score >= aa.threshold
        truth: TruthValue = "T" if adequate else "F"
        if not adequate:
            reason = "threshold_not_met"
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
        reason=reason,
        score=effective_score,
        threshold=aa.threshold,
        provenance=[aa.producer, aa.id],
    ), diags


def _aggregate_adequacy_by_policy(
    assessments: list[AdequacyResult],
    policy_kind: str,
    policy_order: list[str] | None = None,
    adjudicator_handler: Callable[..., Any] | None = None,
    policy_members: list[str] | None = None,
) -> tuple[TruthValue, str | None]:
    """Aggregate multiple assessment results under a given policy kind.

    Returns (truth, reason).
    """
    if not assessments:
        return "N", "no_assessments"

    if policy_kind == "single":
        # Single: use the assessment matching the configured member if specified
        if policy_members:
            target = policy_members[0]
            for a in assessments:
                if a.producer == target:
                    return a.truth, a.reason
        # Fall back to first assessment if no member specified or not found
        return assessments[0].truth, assessments[0].reason

    elif policy_kind == "paraconsistent_union":
        truths = [a.truth for a in assessments]
        agg = _aggregate_truth(truths)
        truth_set = set(truths)
        reason: str | None = None
        if "T" in truth_set and "F" in truth_set:
            agg = "B"
            reason = "adequacy_conflict"
        elif agg == "B":
            reason = "adequacy_conflict"
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
            if hasattr(result, "truth"):
                return result.truth, getattr(result, "reason", None)
            return "N", None
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

            # Check for method conflicts among same-task assessments
            if len(task_assessments) > 1:
                methods = {aa.method for aa in task_assessments if aa.method is not None}
                if len(methods) > 1:
                    # Method conflict detected: different methods for the same task.
                    # Preserve legacy per-assessment conflict marker on the first
                    # assessment while normalizing aggregation inputs so policy
                    # evaluation sees a consistent conflict set.
                    first_aa = task_assessments[0]
                    first_conflicted = AdequacyResult(
                        assessment_id=first_aa.id,
                        task=first_aa.task,
                        producer=first_aa.producer,
                        adequate=False,
                        truth="B",
                        reason="method_conflict",
                        score=per_assessment[first_aa.id].score,
                        threshold=first_aa.threshold,
                        provenance=per_assessment[first_aa.id].provenance,
                    )
                    per_assessment[first_aa.id] = first_conflicted

                    task_results = [
                        AdequacyResult(
                            assessment_id=aa.id,
                            task=aa.task,
                            producer=aa.producer,
                            adequate=False,
                            truth="B",
                            reason="method_conflict",
                            score=per_assessment[aa.id].score,
                            threshold=aa.threshold,
                            provenance=per_assessment[aa.id].provenance,
                        )
                        for aa in task_assessments
                    ]
                    diags.append({
                        "severity": "warning",
                        "subject": first_aa.id,
                        "code": "method_conflict",
                        "phase": "license",
                        "message": (
                            f"Assessment {first_aa.id} conflicts with other "
                            f"same-task assessments using different methods: "
                            f"{sorted(methods)}"
                        ),
                    })

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
                            policy_members=policy.members,
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
                        policy_members=policy.members,
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


# Severity ordering for license truth: F > B > N > T (worst wins)
_SEVERITY_ORDER: dict[str, int] = {"F": 3, "B": 2, "N": 1, "T": 0}


def _worst_truth(truths: list[TruthValue]) -> TruthValue:
    """Return the worst truth value from a list using severity ordering F > B > N > T."""
    if not truths:
        return "N"
    return max(truths, key=lambda t: _SEVERITY_ORDER.get(t, 0))


# Protocol #5: compose_license
def compose_license(
    claim_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[LicenseResult, MachineState, Diagnostics]:
    """Compose license for a claim based on its anchor adequacy results.

    Checks that all anchors in the claim's usesAnchors have adequate results
    for the resolved task. Handles individual anchor adequacy, joint adequacy
    groups, and missing/circular dependencies.
    """
    diags: Diagnostics = []
    bundle: BundleNode | None = services.get("__bundle__")
    if bundle is None:
        return (
            LicenseResult(
                claim_id=claim_id,
                overall=LicenseOverall(truth="N", reason="no_bundle"),
            ),
            machine_state,
            [{"severity": "error", "code": "compose_license_no_bundle",
              "message": "No bundle in services"}],
        )

    # Find the claim
    claim: ClaimNode | None = None
    for block in bundle.claimBlocks:
        for c in block.claims:
            if c.id == claim_id:
                claim = c
                break
        if claim is not None:
            break

    if claim is None:
        return (
            LicenseResult(
                claim_id=claim_id,
                overall=LicenseOverall(truth="N", reason="claim_not_found"),
            ),
            machine_state,
            [{"severity": "error", "code": "compose_license_claim_not_found",
              "subject": claim_id, "message": f"Claim {claim_id} not found"}],
        )

    # If claim uses no anchors, no license evaluation needed
    if not claim.usesAnchors:
        return (
            LicenseResult(claim_id=claim_id, overall=LicenseOverall(truth="T")),
            machine_state,
            diags,
        )

    # Resolve the task for this claim:
    # 1. annotation license_task
    # 2. frame.task fallback
    task: str | None = claim.annotations.get("license_task")
    if task is None:
        # Fall back to the bundle frame's task facet
        frame = bundle.frame
        if isinstance(frame, FrameNode):
            task = getattr(frame, "task", None)
        elif isinstance(frame, FramePatternNode):
            task = getattr(frame.facets, "task", None) if frame.facets else None

    if task is None:
        return (
            LicenseResult(
                claim_id=claim_id,
                overall=LicenseOverall(truth="N", reason="no_task_resolved"),
            ),
            machine_state,
            [{"severity": "warning", "code": "compose_license_no_task",
              "subject": claim_id,
              "message": f"No license task resolved for claim {claim_id}"}],
        )

    # Build lookup structures
    anchors_by_id: dict[str, AnchorNode] = {a.id: a for a in bundle.anchors}
    adequacy_store = machine_state.adequacy_store
    per_anchor_task: dict[str, dict[str, Any]] = adequacy_store.get("per_anchor_task", {})
    joint_store: dict[str, dict[str, Any]] = adequacy_store.get("joint", {})

    individual_entries: list[AnchorLicenseEntry] = []
    joint_entries: list[JointLicenseEntry] = []
    all_truths: list[TruthValue] = []
    overall_reason: str | None = None

    # Check for required joint adequacy groups
    # An anchor with requiresJointWith means its exact set must appear in a joint_adequacy
    uses_set = set(claim.usesAnchors)

    for anchor_id in claim.usesAnchors:
        anchor = anchors_by_id.get(anchor_id)
        if anchor is None:
            entry = AnchorLicenseEntry(
                anchor_id=anchor_id, task=task, truth="N", reason="anchor_not_found",
            )
            individual_entries.append(entry)
            all_truths.append("N")
            continue

        # Check if this anchor requires joint adequacy with others
        if anchor.requiresJointWith:
            # The anchor requires joint adequacy. Check that a joint adequacy group
            # covers both this anchor and its required partners that are in the claim's uses set
            joint_partners = set(anchor.requiresJointWith)
            # All joint partners must be in the claim's usesAnchors
            needed_joint_set = {anchor_id} | (joint_partners & uses_set)

            # Look for a joint adequacy group whose anchor set matches
            found_joint = False
            for ja in bundle.jointAdequacies:
                ja_anchor_set = set(ja.anchors)
                # The joint adequacy must exactly match the needed anchors
                if needed_joint_set == ja_anchor_set:
                    # Found a matching joint group - check its result
                    ja_key = ja.id
                    ja_result = joint_store.get(ja_key)
                    if ja_result is not None:
                        ja_truth: TruthValue = ja_result.get("truth", "N")
                        ja_reason = ja_result.get("reason")
                        joint_entries.append(JointLicenseEntry(
                            joint_id=ja.id, anchors=ja.anchors,
                            truth=ja_truth, reason=ja_reason,
                        ))
                        # Joint adequacy truth participates in overall license
                        all_truths.append(ja_truth)
                    found_joint = True
                    break

            if not found_joint:
                # No joint adequacy group found covering the needed set
                entry = AnchorLicenseEntry(
                    anchor_id=anchor_id, task=task,
                    truth="N", reason="missing_joint_adequacy",
                )
                individual_entries.append(entry)
                all_truths.append("N")
                diags.append({
                    "severity": "warning",
                    "code": "missing_joint_adequacy",
                    "subject": claim_id,
                    "message": (
                        f"Anchor {anchor_id} requires joint adequacy with "
                        f"{sorted(joint_partners)} but no matching group found"
                    ),
                })
                continue
            else:
                # Joint adequacy found — skip individual adequacy for this anchor
                continue

        # Look up individual anchor:task adequacy
        adeq_key = f"{anchor_id}:{task}"
        anchor_result = per_anchor_task.get(adeq_key)

        if anchor_result is None:
            # No adequacy result for this anchor:task
            entry = AnchorLicenseEntry(
                anchor_id=anchor_id, task=task,
                truth="N", reason="no_adequacy_result",
            )
            individual_entries.append(entry)
            all_truths.append("N")
            continue

        anchor_truth: TruthValue = anchor_result.get("truth", "N")
        anchor_reason = anchor_result.get("reason")

        # Check for circular dependency
        per_assessment_list = anchor_result.get("per_assessment", [])
        has_circular = any(
            a.get("reason") == "circular_dependency" for a in per_assessment_list
        )
        if has_circular:
            entry = AnchorLicenseEntry(
                anchor_id=anchor_id, task=task,
                truth="N", reason="circular_dependency",
            )
            individual_entries.append(entry)
            all_truths.append("N")
            overall_reason = "circular_dependency"
            continue

        entry = AnchorLicenseEntry(
            anchor_id=anchor_id, task=task,
            truth=anchor_truth, reason=anchor_reason,
        )
        individual_entries.append(entry)
        all_truths.append(anchor_truth)

    # Determine overall license truth (worst wins: F > B > N > T)
    overall_truth = _worst_truth(all_truths)

    # Set reason based on overall truth if not already set
    if overall_reason is None:
        if overall_truth == "F":
            # Find the reason from the failing entry (individual then joint)
            for e in individual_entries:
                if e.truth == "F":
                    overall_reason = e.reason or "threshold_not_met"
                    break
            if overall_reason is None:
                for e in joint_entries:
                    if e.truth == "F":
                        overall_reason = e.reason or "threshold_not_met"
                        break
        elif overall_truth == "B":
            for e in individual_entries:
                if e.truth == "B":
                    overall_reason = e.reason or "adequacy_conflict"
                    break
            if overall_reason is None:
                for e in joint_entries:
                    if e.truth == "B":
                        overall_reason = e.reason or "adequacy_conflict"
                        break
        elif overall_truth == "N":
            for e in individual_entries:
                if e.truth == "N":
                    overall_reason = e.reason
                    break
            if overall_reason is None:
                for e in joint_entries:
                    if e.truth == "N":
                        overall_reason = e.reason
                        break

    result = LicenseResult(
        claim_id=claim_id,
        overall=LicenseOverall(truth=overall_truth, reason=overall_reason),
        individual=individual_entries,
        joint=joint_entries,
        diagnostics=list(diags),  # copy to avoid shared-reference mutation
    )
    return result, machine_state, diags


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
    """Synthesize support assessment for a claim given its evidence view.

    Default support policy:
    - If the claim expr is a NoteExpr -> support="inapplicable"
    - If no explicit evidence -> support="absent"
    - If conflicts relations exist (cross_conflict_score > 0) -> support="conflicted"
    - If all evidence present and no conflicts -> support="supported"
    - Mixed support indicators (partial completeness or internal conflict) -> support="partial"

    Evidence policy override:
    - If the evaluator has an evidencePolicy and a matching handler exists in
      services["support_policy_handlers"], delegate to that handler.
    - If the policy URI is set but no handler is found, fall through to default.
    """
    diags: Diagnostics = []

    # --- NoteExpr guard: notes should not reach here (runner bypasses) but handle gracefully ---
    if isinstance(claim.expr, NoteExprNode):
        return (
            SupportResult(support="inapplicable", provenance=[evaluator_id, claim.id]),
            machine_state,
            diags,
        )

    # --- Evidence policy override path ---
    bundle: BundleNode | None = services.get("__bundle__")
    evaluator = None
    if bundle is not None:
        for ev in bundle.evaluators:
            if ev.id == evaluator_id:
                evaluator = ev
                break

    if evaluator is not None and evaluator.evidencePolicy is not None:
        policy_uri = evaluator.evidencePolicy
        policy_handlers = services.get("support_policy_handlers", {})
        handler = policy_handlers.get(policy_uri)
        if handler is not None:
            result = handler(
                claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state
            )
            return result, machine_state, diags

    # --- Default support policy ---
    return _default_support_policy(claim, evidence_view, evaluator_id, machine_state, diags)


def _default_support_policy(
    claim: ClaimNode,
    evidence_view: ClaimEvidenceView,
    evaluator_id: str,
    machine_state: MachineState,
    diags: Diagnostics,
) -> tuple[SupportResult, MachineState, Diagnostics]:
    """Default support policy based on declared evidence view.

    Decision order:
    1. No explicit evidence -> "absent"
    2. Conflicts relations present (cross_conflict_score is not None and > 0) -> "conflicted"
    3. Any evidence with completeness < 1 or internalConflict > 0 -> "partial"
    4. Otherwise -> "supported"
    """
    explicit = evidence_view.explicit_evidence

    # No evidence at all
    if not explicit:
        return (
            SupportResult(support="absent", provenance=[evaluator_id, claim.id]),
            machine_state,
            diags,
        )

    # Check for conflicts via relations
    has_conflicts = False
    for rel in evidence_view.relations:
        if rel.kind == "conflicts":
            has_conflicts = True
            break
    if not has_conflicts and evidence_view.cross_conflict_score is not None:
        if evidence_view.cross_conflict_score > 0:
            has_conflicts = True

    if has_conflicts:
        return (
            SupportResult(support="conflicted", provenance=[evaluator_id, claim.id]),
            machine_state,
            diags,
        )

    # Check for partial indicators: incomplete evidence or internal conflict
    has_partial = False
    for ev in explicit:
        if ev.completeness is not None and ev.completeness < 1.0:
            has_partial = True
            break
        if ev.internalConflict is not None and ev.internalConflict > 0:
            has_partial = True
            break

    if has_partial:
        return (
            SupportResult(support="partial", provenance=[evaluator_id, claim.id]),
            machine_state,
            diags,
        )

    # All evidence supports claim
    return (
        SupportResult(support="supported", provenance=[evaluator_id, claim.id]),
        machine_state,
        diags,
    )


def execute_transport(
    bridge: Any,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TransportResult, MachineState, Diagnostics]:
    """Execute transport query for a bridge.

    Implements all transport modes:
    - metadata_only: return metadata without truth transfer
    - pattern_only: compatibility fallback for bridges without transport handler
    - preserve: copy source truth to destination if preconditions hold
    - degrade: attempt preserve, apply degradation rules on failure
    - remap_recompute: remap source claim to destination frame and re-evaluate
    """
    diags: Diagnostics = []
    transport: TransportNode = bridge.transport
    mode = transport.mode

    # Retrieve the source aggregate eval for the claim being transported.
    # The runner stores per-claim aggregates in resolution_store and also in
    # services["__per_claim_aggregates__"] for transport access.
    per_claim_aggregates: dict[str, EvalNode] = services.get(
        "__per_claim_aggregates__", {}
    )

    # Build bridge metadata (always available)
    metadata = {
        "preserve": bridge.preserve,
        "lose": bridge.lose,
        "gain": bridge.gain,
        "risk": bridge.risk,
    }

    # ---------------------------------------------------------------
    # Locate source claim for this bridge from transport queries
    # (needed for all modes including metadata_only)
    # ---------------------------------------------------------------
    transport_queries: list[dict[str, Any]] = services.get("__transport_queries__", [])
    claim_id: str | None = None
    query_id: str | None = None
    for tq in transport_queries:
        if tq.get("bridgeId") == bridge.id:
            claim_id = tq.get("claimId")
            query_id = tq.get("id")
            break

    # ---------------------------------------------------------------
    # metadata_only
    # ---------------------------------------------------------------
    if mode == "metadata_only":
        # Include source aggregate if a transport query references a claim
        src_aggregate = None
        if claim_id is not None:
            src_aggregate = per_claim_aggregates.get(claim_id)
        result = TransportResult(
            status="metadata_only",
            srcAggregate=src_aggregate,
            metadata=metadata,
            provenance=[bridge.id, bridge.via],
        )
        machine_state.transport_store[bridge.id] = result
        if query_id:
            machine_state.transport_store[query_id] = result
        diags.extend(result.diagnostics)
        return result, machine_state, diags

    if claim_id is None:
        # No transport query for this bridge: pattern_only fallback
        result = TransportResult(
            status="pattern_only",
            metadata=metadata,
            provenance=[bridge.id],
        )
        machine_state.transport_store[bridge.id] = result
        return result, machine_state, diags

    # Get source aggregate for the claim
    src_aggregate = per_claim_aggregates.get(claim_id)
    if src_aggregate is None:
        # Source claim not evaluated
        result = TransportResult(
            status="unresolved",
            metadata=metadata,
            provenance=[bridge.id, claim_id],
            diagnostics=[{
                "severity": "error",
                "code": "transport_source_missing",
                "bridge_id": bridge.id,
                "claim_id": claim_id,
                "message": f"Source claim {claim_id} has no aggregate eval",
            }],
        )
        machine_state.transport_store[bridge.id] = result
        if query_id:
            machine_state.transport_store[query_id] = result
        diags.extend(result.diagnostics)
        return result, machine_state, diags

    # Get the claim's semantic requirements from the bundle
    bundle: BundleNode | None = services.get("__bundle__")
    claim_node: ClaimNode | None = None
    if bundle is not None:
        for block in bundle.claimBlocks:
            for c in block.claims:
                if c.id == claim_id:
                    claim_node = c
                    break
            if claim_node is not None:
                break

    semantic_requirements: list[str] = []
    if claim_node is not None:
        semantic_requirements = claim_node.semanticRequirements

    # Diagnostic rule 23: warn if semantic_requirements is empty under
    # preserve or degrade transport
    if mode in ("preserve", "degrade") and not semantic_requirements:
        diags.append({
            "severity": "warning",
            "code": "lint.transport.semantic_requirements_empty",
            "phase": "transport",
            "subject": claim_id,
            "message": (
                f"Claim {claim_id} evaluated under {mode} transport "
                "has empty semantic_requirements"
            ),
        })

    # ---------------------------------------------------------------
    # preserve
    # ---------------------------------------------------------------
    if mode == "preserve":
        result = _execute_preserve(
            bridge, src_aggregate, semantic_requirements, metadata, claim_id, diags,
        )
        machine_state.transport_store[bridge.id] = result
        if query_id:
            machine_state.transport_store[query_id] = result
        return result, machine_state, diags

    # ---------------------------------------------------------------
    # degrade
    # ---------------------------------------------------------------
    if mode == "degrade":
        result = _execute_degrade(
            bridge, src_aggregate, semantic_requirements, metadata, claim_id, diags,
        )
        machine_state.transport_store[bridge.id] = result
        if query_id:
            machine_state.transport_store[query_id] = result
        return result, machine_state, diags

    # ---------------------------------------------------------------
    # remap_recompute
    # ---------------------------------------------------------------
    if mode == "remap_recompute":
        result = _execute_remap_recompute(
            bridge, transport, src_aggregate, metadata, claim_id,
            step_ctx, machine_state, services, diags,
        )
        machine_state.transport_store[bridge.id] = result
        if query_id:
            machine_state.transport_store[query_id] = result
        return result, machine_state, diags

    # Unknown mode (should not happen given validation)
    result = TransportResult(
        status="unresolved",
        metadata=metadata,
        provenance=[bridge.id],
        diagnostics=[{
            "severity": "error",
            "code": "transport_unknown_mode",
            "bridge_id": bridge.id,
            "message": f"Unknown transport mode: {mode}",
        }],
    )
    machine_state.transport_store[bridge.id] = result
    if query_id:
        machine_state.transport_store[query_id] = result
    return result, machine_state, diags


def _check_preconditions(
    bridge: Any,
    src_aggregate: EvalNode,
) -> bool:
    """Evaluate transport preconditions.

    Preconditions are simple string identifiers. The default evaluation:
    - If no preconditions are specified, they are satisfied.
    - Otherwise, preconditions hold if the source truth is T or B.
    """
    preconditions = bridge.transport.preconditions
    if not preconditions:
        return True
    # Default precondition semantics: source must have decisive truth
    return src_aggregate.truth in ("T", "B")


def _requirements_intersect_lose(
    semantic_requirements: list[str],
    lose: list[str],
) -> bool:
    """Check if semantic_requirements intersects with the bridge lose set."""
    if not semantic_requirements or not lose:
        return False
    return bool(set(semantic_requirements) & set(lose))


def _execute_preserve(
    bridge: Any,
    src_aggregate: EvalNode,
    semantic_requirements: list[str],
    metadata: dict[str, Any],
    claim_id: str,
    diags: Diagnostics,
) -> TransportResult:
    """Execute preserve transport mode."""
    preconditions_hold = _check_preconditions(bridge, src_aggregate)
    requirements_lost = _requirements_intersect_lose(semantic_requirements, bridge.lose)

    if preconditions_hold and not requirements_lost:
        # Successful preserve: copy source aggregate to destination
        dst_aggregate = EvalNode(
            truth=src_aggregate.truth,
            reason=src_aggregate.reason,
            support=src_aggregate.support,
            confidence=src_aggregate.confidence,
            provenance=sorted(set(src_aggregate.provenance + [bridge.id, bridge.via])),
        )
        return TransportResult(
            status="preserved",
            srcAggregate=src_aggregate,
            dstAggregate=dst_aggregate,
            metadata=metadata,
            provenance=[bridge.id, bridge.via, claim_id],
        )
    else:
        # Failed preserve
        if not preconditions_hold:
            reason = "transport_precondition"
        else:
            reason = "transport_loss"
        dst_aggregate = EvalNode(
            truth="N",
            reason=reason,
            support=src_aggregate.support,
            provenance=sorted(set(src_aggregate.provenance + [bridge.id])),
        )
        return TransportResult(
            status="blocked",
            srcAggregate=src_aggregate,
            dstAggregate=dst_aggregate,
            metadata=metadata,
            provenance=[bridge.id, bridge.via, claim_id],
        )


def _degrade_truth(truth: TruthValue) -> tuple[TruthValue, str | None]:
    """Apply degradation rules to a truth value.

    T -> N[transport_loss]
    F -> N[transport_loss]
    B -> B[boundary_mix]
    N -> N
    """
    if truth == "T":
        return "N", "transport_loss"
    elif truth == "F":
        return "N", "transport_loss"
    elif truth == "B":
        return "B", "boundary_mix"
    else:  # N
        return "N", None


def _execute_degrade(
    bridge: Any,
    src_aggregate: EvalNode,
    semantic_requirements: list[str],
    metadata: dict[str, Any],
    claim_id: str,
    diags: Diagnostics,
) -> TransportResult:
    """Execute degrade transport mode.

    Attempts preserve first; on failure due to transport loss, applies
    degradation rules.
    """
    preconditions_hold = _check_preconditions(bridge, src_aggregate)
    requirements_lost = _requirements_intersect_lose(semantic_requirements, bridge.lose)

    if preconditions_hold and not requirements_lost:
        # Preserve succeeds -> preserve result
        dst_aggregate = EvalNode(
            truth=src_aggregate.truth,
            reason=src_aggregate.reason,
            support=src_aggregate.support,
            confidence=src_aggregate.confidence,
            provenance=sorted(set(src_aggregate.provenance + [bridge.id, bridge.via])),
        )
        return TransportResult(
            status="preserved",
            srcAggregate=src_aggregate,
            dstAggregate=dst_aggregate,
            metadata=metadata,
            provenance=[bridge.id, bridge.via, claim_id],
        )

    if not preconditions_hold:
        # Precondition failure: N[transport_precondition], no degradation
        dst_aggregate = EvalNode(
            truth="N",
            reason="transport_precondition",
            support=src_aggregate.support,
            provenance=sorted(set(src_aggregate.provenance + [bridge.id])),
        )
        return TransportResult(
            status="blocked",
            srcAggregate=src_aggregate,
            dstAggregate=dst_aggregate,
            metadata=metadata,
            provenance=[bridge.id, bridge.via, claim_id],
        )

    # Transport loss: apply degradation rules
    degraded_truth, degraded_reason = _degrade_truth(src_aggregate.truth)

    # Support degrades to partial when truth is degraded
    degraded_support = src_aggregate.support
    if degraded_truth != src_aggregate.truth or degraded_reason == "transport_loss":
        degraded_support = "partial"

    dst_aggregate = EvalNode(
        truth=degraded_truth,
        reason=degraded_reason,
        support=degraded_support,
        provenance=sorted(set(src_aggregate.provenance + [bridge.id, bridge.via])),
    )
    return TransportResult(
        status="degraded",
        srcAggregate=src_aggregate,
        dstAggregate=dst_aggregate,
        metadata=metadata,
        provenance=[bridge.id, bridge.via, claim_id],
    )


def _execute_remap_recompute(
    bridge: Any,
    transport: TransportNode,
    src_aggregate: EvalNode,
    metadata: dict[str, Any],
    claim_id: str,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
    diags: Diagnostics,
) -> TransportResult:
    """Execute remap_recompute transport mode.

    Resolves claim_map, constructs destination frame, maps source claim
    to destination claim/expression, evaluates under destination context.
    """
    claim_map_binding = transport.claimMap
    if claim_map_binding is None:
        return TransportResult(
            status="unresolved",
            srcAggregate=src_aggregate,
            metadata=metadata,
            provenance=[bridge.id, claim_id],
            diagnostics=[{
                "severity": "error",
                "code": "transport_mapping_missing",
                "bridge_id": bridge.id,
                "claim_id": claim_id,
                "message": "remap_recompute requires claimMap but none provided",
            }],
        )

    # Resolve the claim map handler from services
    claim_map_handler: Callable | None = services.get("__claim_map_handler__")

    # Construct destination frame from bridge.to
    dst_pattern = bridge.to

    # Determine destination evaluators: use transport.dstEvaluators or fall back
    # to bundle evaluators
    bundle: BundleNode | None = services.get("__bundle__")
    dst_evaluator_ids = transport.dstEvaluators
    if dst_evaluator_ids is None and bundle is not None:
        dst_evaluator_ids = [e.id for e in bundle.evaluators]
    if dst_evaluator_ids is None:
        dst_evaluator_ids = []

    # Build destination step context using bridge.to as frame
    dst_frame_dict: dict[str, Any] = {}
    if hasattr(dst_pattern, "facets") and dst_pattern.facets is not None:
        for facet in _FRAME_FACETS:
            val = getattr(dst_pattern.facets, facet, None)
            if val is not None:
                dst_frame_dict[facet] = val

    # Map source claim to destination using the claim_map_handler if available
    mapped_claim: str | None = None
    mapped_truth: TruthValue = "N"
    mapped_reason: str | None = "transport_mapping_missing"
    per_evaluator: dict[str, EvalNode] = {}

    if claim_map_handler is not None:
        try:
            map_result = claim_map_handler(
                claim_id, claim_map_binding, bridge, step_ctx, machine_state,
            )
            if isinstance(map_result, dict):
                mapped_claim = map_result.get("mappedClaim")
                mapped_truth = map_result.get("truth", "N")
                mapped_reason = map_result.get("reason")
                per_evaluator = map_result.get("per_evaluator", {})
            elif isinstance(map_result, tuple) and len(map_result) >= 2:
                mapped_truth = map_result[0]
                mapped_reason = map_result[1] if len(map_result) > 1 else None
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "transport_remap_error",
                "bridge_id": bridge.id,
                "claim_id": claim_id,
                "message": str(exc),
            })
    else:
        # No explicit handler; use default remap behavior.
        # Intentionally "F" (false), not "N" (unknown). Per the spec, a missing
        # __claim_map_handler__ means the mapping failed outright, and unmappable
        # claims are treated as false rather than unknown. The fixture corpus
        # (FIXTURE-001) expects "F" as the destination truth when no handler is
        # available (e.g., A10 transport expectations). Reviewed and confirmed
        # during PR #6 review round 2.
        mapped_truth = "F"
        mapped_reason = None
        mapped_claim = claim_id

    dst_aggregate = EvalNode(
        truth=mapped_truth,
        reason=mapped_reason,
        support=src_aggregate.support if src_aggregate else "absent",
        provenance=sorted(set(
            (src_aggregate.provenance if src_aggregate else [])
            + [bridge.id, bridge.via]
        )),
    )

    return TransportResult(
        status="transported",
        srcAggregate=src_aggregate,
        dstAggregate=dst_aggregate,
        metadata=metadata,
        mappedClaim=mapped_claim,
        per_evaluator=per_evaluator,
        provenance=[bridge.id, bridge.via, claim_id],
    )
