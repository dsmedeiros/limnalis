"""Built-in implementations of Limnalis primitive operations.

Implements 12 of the 13 primitives fully; only resolve_ref remains a stub
requiring domain/external logic.

NOTE on section numbering: Section numbers in this file (e.g. "2. build_step_context",
"7. classify_claim") follow the Protocol numbering defined in primitives.py (1-13),
which now matches the runner phase numbering (1-13).
"""

from __future__ import annotations

from typing import Any, Callable

from ..models.ast import (
    AdequacyAssessmentNode,
    AnchorNode,
    BaselineNode,
    BridgeNode,
    BundleNode,
    CausalExprNode,
    ClaimBlockNode,
    ClaimNode,
    CriterionExprNode,
    DeclarationExprNode,
    DegradationPolicyNode,
    DestinationCompletionPolicy,
    DynamicExprNode,
    EmergenceExprNode,
    EvidenceNode,
    EvidenceRelationNode,
    FacetValueMap,
    FrameNode,
    FrameOrPatternNode,
    FramePatternNode,
    InferredEvidenceRelation,
    JointAdequacyNode,
    JudgedExprNode,
    LogicalExprNode,
    NoteExprNode,
    PredicateExprNode,
    ResolutionPolicyNode,
    TimeCtxNode,
    TransportHop,
    TransportNode,
    TransportPlan,
)
from ..models.conformance import (
    AdequacyExecutionTrace,
    BasisResolutionEntry,
    TransportTrace,
    TruthValue,
)
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
    TransportChainResult,
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

    required_facets = ("system", "namespace", "scale", "task", "regime")
    missing_required = [f for f in required_facets if merged_facets.get(f) is None]
    if missing_required:
        diags.append({
            "severity": "error",
            "code": "frame_unresolved_for_evaluation",
            "step_id": step.id,
            "missing_facets": missing_required,
            "message": (
                "Required frame facets are unresolved after merging "
                "bundle/session/step frame inputs."
            ),
        })
        if all(v is None for v in merged_facets.values()):
            # Keep StepContext valid while clearly marking the frame as unresolved.
            merged_facets["system"] = "__unresolved__"

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
    - else inapplicable if any inapplicable
    - else absent
    """
    supports = [e.support for e in evals if e.support is not None]
    if not supports:
        return None

    # Only force conflicted for real evaluator conflicts (T/F disagreement).
    # Aggregate B can also arise from non-conflict inputs (e.g., B+N), and in
    # those cases support severity should be inherited from evaluator supports.
    truth_set = {e.truth for e in evals}
    if aggregate_truth == "B" and "T" in truth_set and "F" in truth_set:
        return "conflicted"

    if "conflicted" in supports:
        return "conflicted"
    if "partial" in supports:
        return "partial"
    if "supported" in supports:
        return "supported"
    if "inapplicable" in supports:
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
            unique_reasons = sorted(set(reasons))
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
    """Resolve a baseline: determine its runtime state based on kind and evaluationMode.

    State logic:
      - evaluationMode=on_reference (any kind)    -> deferred (lazy)
      - kind=moving + evaluationMode != tracked    -> unresolved + diagnostic
      - everything else (point/fixed, moving+tracked) -> ready
    """
    diags: Diagnostics = []

    # Look up the BaselineNode from the bundle injected into services
    bundle: BundleNode | None = services.get("__bundle__")
    baseline_node: BaselineNode | None = None
    if bundle is not None:
        for bl in bundle.baselines:
            if bl.id == baseline_id:
                baseline_node = bl
                break

    if baseline_node is None:
        # No baseline definition found; mark unresolved with diagnostic
        diags.append({
            "severity": "warning",
            "code": "baseline_not_found",
            "subject": baseline_id,
            "phase": "baseline",
            "message": f"baseline '{baseline_id}' not found in bundle definitions",
        })
        machine_state.baseline_store[baseline_id] = BaselineState(
            baseline_id=baseline_id, status="unresolved"
        )
        return None, machine_state, diags

    # Determine baseline state
    kind = baseline_node.kind
    eval_mode = baseline_node.evaluationMode

    if eval_mode == "on_reference":
        # Any baseline with lazy evaluation mode is deferred regardless of kind
        status = "deferred"
    elif kind == "moving" and eval_mode != "tracked":
        # Invalid: moving baselines require evaluationMode='tracked' (or on_reference)
        status = "unresolved"
        diags.append({
            "severity": "error",
            "code": "baseline_mode_invalid",
            "subject": baseline_id,
            "phase": "baseline",
            "message": f"invalid baseline '{baseline_id}': moving baselines require evaluationMode='tracked'",
        })
    else:
        # Non-moving baselines or moving+tracked are immediately ready
        status = "ready"

    machine_state.baseline_store[baseline_id] = BaselineState(
        baseline_id=baseline_id, status=status
    )

    return None, machine_state, diags


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
        # No explicit score and no usable method binding -> unresolved adequacy.
        adequate = False
        truth = "N"
        reason = "missing_binding"
        diags.append({
            "severity": "error",
            "code": "adequacy_method_binding_missing",
            "phase": "license",
            "subject": aa.id,
            "message": f"No adequacy handler produced score for method '{aa.method}'",
        })

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
            return "N", f"policy_member_not_found:{target}"
        # Fall back to first assessment only when member configuration is absent
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
    # 2. effective step frame task
    # 3. bundle frame task fallback
    task: str | None = claim.annotations.get("license_task")
    if task is None:
        effective_frame = step_ctx.effective_frame
        if isinstance(effective_frame, FrameNode):
            task = getattr(effective_frame, "task", None)
        elif isinstance(effective_frame, FramePatternNode):
            task = (
                getattr(effective_frame.facets, "task", None)
                if effective_frame.facets
                else None
            )
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
    anchors_covered_by_joint: set[str] = set()
    missing_joint_partners: dict[str, list[str]] = {}
    processed_joint_ids: set[str] = set()

    # Precompute matched joint coverage for requiring anchors so coverage
    # is independent of claim.usesAnchors ordering.
    for anchor_id in claim.usesAnchors:
        anchor = anchors_by_id.get(anchor_id)
        if anchor is None or not anchor.requiresJointWith:
            continue

        joint_partners = set(anchor.requiresJointWith)
        missing_from_claim = joint_partners - uses_set
        if missing_from_claim:
            missing_joint_partners[anchor_id] = sorted(joint_partners)
            continue

        needed_joint_set = {anchor_id} | joint_partners

        found_joint_with_result = False
        for ja in bundle.jointAdequacies:
            ja_anchor_set = set(ja.anchors)
            if needed_joint_set == ja_anchor_set:
                ja_result = joint_store.get(ja.id)
                if ja_result is not None:
                    found_joint_with_result = True
                    anchors_covered_by_joint.update(ja_anchor_set & uses_set)
                    if ja.id not in processed_joint_ids:
                        ja_truth: TruthValue = ja_result.get("truth", "N")
                        ja_reason = ja_result.get("reason")
                        joint_entries.append(JointLicenseEntry(
                            joint_id=ja.id,
                            anchors=ja.anchors,
                            truth=ja_truth,
                            reason=ja_reason,
                        ))
                        all_truths.append(ja_truth)
                        processed_joint_ids.add(ja.id)
                    break

        if not found_joint_with_result:
            missing_joint_partners[anchor_id] = sorted(joint_partners)

    for anchor_id in claim.usesAnchors:
        anchor = anchors_by_id.get(anchor_id)
        if anchor is None:
            entry = AnchorLicenseEntry(
                anchor_id=anchor_id, task=task, truth="N", reason="anchor_not_found",
            )
            individual_entries.append(entry)
            all_truths.append("N")
            continue

        if anchor_id in missing_joint_partners:
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
                    f"{missing_joint_partners[anchor_id]} but no matching group found"
                ),
            })
            continue

        # Anchors covered by a matched joint adequacy group do not require
        # separate per-anchor adequacy lookup for this claim.
        if anchor_id in anchors_covered_by_joint:
            continue

        # Requiring anchors have already been handled by joint precomputation.
        if anchor.requiresJointWith:
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

    Notes:
    - Multiple transport queries may target a single bridge; all matching
      queries are evaluated and stored in transport_store keyed by query id.
    - The function return value remains a single TransportResult for compatibility
      and corresponds to the first matching query (or a pattern fallback when
      no matching query exists).
    """
    diags: Diagnostics = []
    transport: TransportNode = bridge.transport
    mode = transport.mode

    # Retrieve source aggregate evals for transported claims.
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

    # All matching queries for this bridge (not just the first).
    transport_queries: list[dict[str, Any]] = services.get("__transport_queries__", [])
    current_step_index = services.get("__fixture_step_index__")

    def _query_matches_current_step(query: dict[str, Any]) -> bool:
        query_step_index = query.get("__fixture_step_index__")
        if query_step_index is None:
            return True
        if not isinstance(current_step_index, int):
            return False
        return query_step_index == current_step_index

    matching_queries = [
        tq for tq in transport_queries
        if tq.get("bridgeId") == bridge.id and _query_matches_current_step(tq)
    ]

    # ---------------------------------------------------------------
    # metadata_only
    # ---------------------------------------------------------------
    if mode == "metadata_only":
        if matching_queries:
            first_result: TransportResult | None = None
            for tq in matching_queries:
                claim_id = tq.get("claimId")
                query_id = tq.get("id")
                src_aggregate = (
                    per_claim_aggregates.get(claim_id)
                    if claim_id is not None
                    else None
                )
                result = TransportResult(
                    status="metadata_only",
                    srcAggregate=src_aggregate,
                    metadata=metadata,
                    provenance=[bridge.id, bridge.via],
                )
                if first_result is None:
                    first_result = result
                    machine_state.transport_store[bridge.id] = result
                if query_id:
                    machine_state.transport_store[query_id] = result
                diags.extend(result.diagnostics)
            return first_result or TransportResult(  # defensive fallback
                status="metadata_only",
                metadata=metadata,
                provenance=[bridge.id, bridge.via],
            ), machine_state, diags

        # No matching query: retain metadata-only bridge-level behavior.
        result = TransportResult(
            status="metadata_only",
            srcAggregate=None,
            metadata=metadata,
            provenance=[bridge.id, bridge.via],
        )
        machine_state.transport_store[bridge.id] = result
        diags.extend(result.diagnostics)
        return result, machine_state, diags

    if not matching_queries:
        # No transport query for this bridge: pattern_only fallback
        result = TransportResult(
            status="pattern_only",
            metadata=metadata,
            provenance=[bridge.id],
        )
        machine_state.transport_store[bridge.id] = result
        return result, machine_state, diags

    bundle: BundleNode | None = services.get("__bundle__")
    first_result: TransportResult | None = None

    for tq in matching_queries:
        claim_id = tq.get("claimId")
        query_id = tq.get("id")

        # Missing claim id in query -> unresolved for that query.
        if not claim_id:
            result = TransportResult(
                status="unresolved",
                metadata=metadata,
                provenance=[bridge.id],
                diagnostics=[{
                    "severity": "error",
                    "code": "transport_query_claim_missing",
                    "bridge_id": bridge.id,
                    "query_id": query_id,
                    "message": "Transport query is missing claimId",
                }],
            )
            diags.extend(result.diagnostics)
            if first_result is None:
                first_result = result
                machine_state.transport_store[bridge.id] = result
            if query_id:
                machine_state.transport_store[query_id] = result
            continue

        # Get source aggregate for this claim
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
            diags.extend(result.diagnostics)
            if first_result is None:
                first_result = result
                machine_state.transport_store[bridge.id] = result
            if query_id:
                machine_state.transport_store[query_id] = result
            continue

        # Get semantic requirements from bundle claim definition.
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

        if mode == "preserve":
            result = _execute_preserve(
                bridge, src_aggregate, semantic_requirements, metadata, claim_id, diags,
            )
        elif mode == "degrade":
            result = _execute_degrade(
                bridge, src_aggregate, semantic_requirements, metadata, claim_id, diags,
            )
        elif mode == "remap_recompute":
            result = _execute_remap_recompute(
                bridge,
                transport,
                src_aggregate,
                metadata,
                claim_id,
                step_ctx,
                machine_state,
                services,
                diags,
            )
        else:
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

        if first_result is None:
            first_result = result
            machine_state.transport_store[bridge.id] = result
        if query_id:
            machine_state.transport_store[query_id] = result
        diags.extend(result.diagnostics)

    if first_result is None:
        # Defensive fallback; should not happen due to matching_queries check.
        first_result = TransportResult(
            status="pattern_only",
            metadata=metadata,
            provenance=[bridge.id],
        )
        machine_state.transport_store[bridge.id] = first_result

    return first_result, machine_state, diags


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
            diag = {
                "severity": "error",
                "code": "transport_remap_error",
                "bridge_id": bridge.id,
                "claim_id": claim_id,
                "message": str(exc),
            }
            dst_aggregate = EvalNode(
                truth="N",
                reason="transport_remap_error",
                support=src_aggregate.support if src_aggregate else "absent",
                provenance=sorted(set(
                    (src_aggregate.provenance if src_aggregate else [])
                    + [bridge.id, bridge.via]
                )),
            )
            return TransportResult(
                status="unresolved",
                srcAggregate=src_aggregate,
                dstAggregate=dst_aggregate,
                metadata=metadata,
                mappedClaim=None,
                per_evaluator={},
                provenance=[bridge.id, bridge.via, claim_id],
                diagnostics=[diag],
            )
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

    # Honor destination evaluator / resolution policy configuration when
    # claim-map handlers provide per-evaluator destination results.
    # Preserve legacy behavior (mapped truth/reason) unless destination
    # transport config explicitly requests evaluator/policy recomputation.
    should_apply_dst_config = (
        transport.dstEvaluators is not None
        or transport.dstResolutionPolicy is not None
    )
    if per_evaluator and should_apply_dst_config:
        normalized_per_evaluator: dict[str, EvalNode] = {}
        for eid, ev in per_evaluator.items():
            if isinstance(ev, EvalNode):
                normalized_per_evaluator[eid] = ev
            elif isinstance(ev, dict):
                normalized_per_evaluator[eid] = EvalNode(**ev)

        selected_per_evaluator = normalized_per_evaluator
        if dst_evaluator_ids:
            selected_per_evaluator = {
                eid: ev for eid, ev in normalized_per_evaluator.items()
                if eid in set(dst_evaluator_ids)
            }
            if not selected_per_evaluator:
                mapped_truth = "N"
                mapped_reason = "no_evaluators"
                diags.append({
                    "severity": "warning",
                    "code": "transport_dst_evaluators_missing",
                    "bridge_id": bridge.id,
                    "claim_id": claim_id,
                    "message": (
                        "No mapped per_evaluator results match configured "
                        f"dstEvaluators={dst_evaluator_ids}"
                    ),
                })

        if selected_per_evaluator:
            policies_by_id: dict[str, ResolutionPolicyNode] = {}
            if bundle is not None:
                policies_by_id[bundle.resolutionPolicy.id] = bundle.resolutionPolicy
            extra_policies = services.get("__resolution_policies__", {})
            if isinstance(extra_policies, dict):
                policies_by_id.update(extra_policies)

            selected_policy: ResolutionPolicyNode | None = None
            if transport.dstResolutionPolicy is not None:
                selected_policy = policies_by_id.get(transport.dstResolutionPolicy)
                if selected_policy is None:
                    mapped_truth = "N"
                    mapped_reason = "missing_resolution_policy"
                    diags.append({
                        "severity": "error",
                        "code": "transport_resolution_policy_missing",
                        "bridge_id": bridge.id,
                        "claim_id": claim_id,
                        "message": (
                            "Destination resolution policy not found: "
                            f"{transport.dstResolutionPolicy}"
                        ),
                    })
            elif bundle is not None:
                selected_policy = bundle.resolutionPolicy

            if selected_policy is not None:
                try:
                    adjudicator = services.get("transport_adjudicator")
                    agg = apply_resolution_policy(
                        selected_per_evaluator,
                        selected_policy,
                        adjudicator,
                    )
                    mapped_truth = agg.truth
                    mapped_reason = agg.reason
                except Exception as exc:
                    mapped_truth = "N"
                    mapped_reason = "resolution_error"
                    diags.append({
                        "severity": "error",
                        "code": "transport_resolution_error",
                        "bridge_id": bridge.id,
                        "claim_id": claim_id,
                        "message": str(exc),
                    })

        # Return the same evaluator projection that destination configuration
        # selected, rather than leaking unconfigured evaluator outputs.
        per_evaluator = selected_per_evaluator

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


# ===================================================================
# T2: Advanced Transport Engine — helper functions
# ===================================================================


def _build_transport_trace(
    hop_results: list[tuple[TransportHop, TransportResult]],
    precondition_outcomes: dict[str, bool] | None = None,
    mapping_steps: list[str] | None = None,
) -> TransportTrace:
    """Build a rich TransportTrace from execution state.

    Populates hops, precondition_outcomes, mapping_steps, total_loss, total_gain
    from the per-hop execution results.
    """
    hops: list[dict[str, Any]] = []
    per_hop_evals: dict[str, dict[str, Any]] = {}
    total_loss: list[str] = []
    total_gain: list[str] = []

    for hop, result in hop_results:
        hop_entry: dict[str, Any] = {
            "bridge_id": hop.bridge_id,
            "src_frame": hop.src_frame,
            "dst_frame": hop.dst_frame,
            "status": result.status,
            "loss": hop.loss,
            "gain": hop.gain,
            "risk": hop.risk,
            "provenance": result.provenance,
        }
        hops.append(hop_entry)
        per_hop_evals[hop.bridge_id] = {
            "status": result.status,
            "srcAggregate": result.srcAggregate.model_dump() if result.srcAggregate else None,
            "dstAggregate": result.dstAggregate.model_dump() if result.dstAggregate else None,
        }
        # Accumulate loss/gain across hops (deduplicated)
        for item in hop.loss:
            if item not in total_loss:
                total_loss.append(item)
        for item in hop.gain:
            if item not in total_gain:
                total_gain.append(item)

    return TransportTrace(
        hops=hops,
        precondition_outcomes=precondition_outcomes or {},
        mapping_steps=mapping_steps or [],
        per_hop_evals=per_hop_evals,
        total_loss=total_loss,
        total_gain=total_gain,
    )


def execute_transport_chain(
    plan: TransportPlan,
    bridges: dict[str, BridgeNode],
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
) -> tuple[TransportChainResult, MachineState, Diagnostics]:
    """Execute a sequence of bridges as a chained transport plan.

    Iterates through plan.hops, executing each bridge's transport in sequence.
    Per-hop: runs preconditions, executes transport mode, records loss/gain/risk.

    Supports:
    - failure_mode="fail_fast": stop on first failure
    - failure_mode="best_effort": continue on failure, record failures

    Returns a consolidated TransportChainResult with full TransportTrace.
    """
    diags: Diagnostics = []
    hop_results: list[tuple[TransportHop, TransportResult]] = []
    precondition_outcomes: dict[str, bool] = {}
    all_provenance: list[str] = [plan.id]
    overall_status: str = "transported"

    for hop in plan.hops:
        bridge = bridges.get(hop.bridge_id)
        if bridge is None:
            diags.append({
                "severity": "error",
                "code": "transport_chain_bridge_missing",
                "plan_id": plan.id,
                "bridge_id": hop.bridge_id,
                "message": f"Bridge {hop.bridge_id} not found for transport chain hop",
            })
            hop_result = TransportResult(
                status="unresolved",
                metadata={},
                provenance=[hop.bridge_id],
                diagnostics=[{
                    "severity": "error",
                    "code": "transport_chain_bridge_missing",
                    "bridge_id": hop.bridge_id,
                    "message": f"Bridge {hop.bridge_id} not found",
                }],
            )
            hop_results.append((hop, hop_result))
            overall_status = "blocked"
            if plan.failure_mode == "fail_fast":
                break
            continue

        # Check preconditions for this hop
        per_claim_aggregates: dict[str, EvalNode] = services.get(
            "__per_claim_aggregates__", {}
        )
        # Use a synthetic EvalNode for precondition checking based on
        # the current chain state. If we have results from the previous
        # hop, use its dstAggregate as the "source" for the next hop.
        precondition_src: EvalNode
        if hop_results and hop_results[-1][1].dstAggregate is not None:
            precondition_src = hop_results[-1][1].dstAggregate
        else:
            # Use first available aggregate or a neutral N node
            precondition_src = EvalNode(truth="N", reason="chain_start")

        precondition_ok = _check_preconditions(bridge, precondition_src)
        precondition_outcomes[hop.bridge_id] = precondition_ok

        if not precondition_ok:
            hop_result = TransportResult(
                status="blocked",
                srcAggregate=precondition_src,
                dstAggregate=EvalNode(
                    truth="N",
                    reason="transport_precondition",
                    provenance=[hop.bridge_id],
                ),
                metadata={
                    "preserve": bridge.preserve,
                    "lose": bridge.lose,
                    "gain": bridge.gain,
                    "risk": bridge.risk,
                },
                provenance=[hop.bridge_id, bridge.via],
            )
            hop_results.append((hop, hop_result))
            overall_status = "blocked"
            if plan.failure_mode == "fail_fast":
                break
            continue

        # Execute the bridge transport
        try:
            hop_result, machine_state, hop_diags = execute_transport(
                bridge, step_ctx, machine_state, services,
            )
            diags.extend(hop_diags)
        except Exception as exc:
            hop_result = TransportResult(
                status="unresolved",
                metadata={},
                provenance=[hop.bridge_id],
                diagnostics=[{
                    "severity": "error",
                    "code": "transport_chain_hop_error",
                    "bridge_id": hop.bridge_id,
                    "message": str(exc),
                }],
            )
            diags.append({
                "severity": "error",
                "code": "transport_chain_hop_error",
                "plan_id": plan.id,
                "bridge_id": hop.bridge_id,
                "message": str(exc),
            })

        hop_results.append((hop, hop_result))
        all_provenance.extend(hop_result.provenance)

        # Check for failure
        if hop_result.status in ("blocked", "unresolved"):
            overall_status = "blocked"
            if plan.failure_mode == "fail_fast":
                break

    # If no hops failed, determine overall status from individual results
    if overall_status != "blocked":
        statuses = {r.status for _, r in hop_results}
        if "degraded" in statuses:
            overall_status = "degraded"
        elif "transported" in statuses:
            overall_status = "transported"
        elif "preserved" in statuses:
            overall_status = "preserved"

    # Build trace and attach to metadata
    trace = _build_transport_trace(hop_results, precondition_outcomes)
    chain_metadata: dict[str, Any] = {
        "transport_trace": trace.model_dump(),
    }

    chain_result = TransportChainResult(
        plan_id=plan.id,
        status=overall_status,  # type: ignore[arg-type]
        per_hop=[r for _, r in hop_results],
        metadata=chain_metadata,
        provenance=sorted(set(all_provenance)),
        diagnostics=list(diags),
    )

    return chain_result, machine_state, diags


def execute_transport_with_degradation_policy(
    bridge: BridgeNode,
    step_ctx: StepContext,
    machine_state: MachineState,
    services: dict[str, Any],
    degradation_policy: DegradationPolicyNode | None = None,
) -> tuple[TransportResult, MachineState, Diagnostics]:
    """Execute transport with optional degradation policy override.

    Extends the existing degrade path:
    - If kind="default" or no policy, use current behavior via execute_transport.
    - If kind="custom" with a binding, look up the binding in services and call it.
    - Preserve the preserve_fields from the policy.
    - Check max_loss if specified; if degradation exceeds max_loss, produce a
      diagnostic and set status to "blocked".
    - Record which degradation policy was used in provenance.
    """
    diags: Diagnostics = []

    # No policy or default: delegate to existing execute_transport
    if degradation_policy is None or degradation_policy.kind == "default":
        result, machine_state, tr_diags = execute_transport(
            bridge, step_ctx, machine_state, services,
        )
        diags.extend(tr_diags)
        if degradation_policy is not None:
            result.degradation_policy_used = degradation_policy.id
        return result, machine_state, diags

    # Custom degradation policy
    assert degradation_policy.kind == "custom"

    binding_name = degradation_policy.binding
    if binding_name is None:
        diags.append({
            "severity": "error",
            "code": "degradation_policy_no_binding",
            "policy_id": degradation_policy.id,
            "message": "Custom degradation policy requires a binding",
        })
        result, machine_state, tr_diags = execute_transport(
            bridge, step_ctx, machine_state, services,
        )
        diags.extend(tr_diags)
        result.degradation_policy_used = degradation_policy.id
        return result, machine_state, diags

    # Look up the binding handler in services
    degradation_handlers: dict[str, Callable] = services.get(
        "__degradation_handlers__", {}
    )
    handler = degradation_handlers.get(binding_name)

    if handler is None:
        diags.append({
            "severity": "warning",
            "code": "degradation_binding_not_found",
            "policy_id": degradation_policy.id,
            "binding": binding_name,
            "message": f"Degradation binding '{binding_name}' not found in services; "
                       "falling back to default behavior",
        })
        result, machine_state, tr_diags = execute_transport(
            bridge, step_ctx, machine_state, services,
        )
        diags.extend(tr_diags)
        result.degradation_policy_used = degradation_policy.id
        return result, machine_state, diags

    # Call the custom degradation handler
    try:
        custom_result = handler(bridge, step_ctx, machine_state, services, degradation_policy)
    except Exception as exc:
        diags.append({
            "severity": "error",
            "code": "degradation_binding_error",
            "policy_id": degradation_policy.id,
            "binding": binding_name,
            "message": str(exc),
        })
        result, machine_state, tr_diags = execute_transport(
            bridge, step_ctx, machine_state, services,
        )
        diags.extend(tr_diags)
        result.degradation_policy_used = degradation_policy.id
        return result, machine_state, diags

    # Normalize the custom result
    if isinstance(custom_result, TransportResult):
        result = custom_result
    elif isinstance(custom_result, dict):
        result = TransportResult.model_validate(custom_result)
    elif isinstance(custom_result, tuple) and len(custom_result) >= 1:
        result = custom_result[0] if isinstance(custom_result[0], TransportResult) else TransportResult.model_validate(custom_result[0])
        if len(custom_result) >= 2:
            machine_state = custom_result[1]
        if len(custom_result) >= 3:
            diags.extend(custom_result[2])
    else:
        diags.append({
            "severity": "error",
            "code": "degradation_binding_invalid_result",
            "policy_id": degradation_policy.id,
            "message": f"Custom degradation handler returned unexpected type: {type(custom_result).__name__}",
        })
        result, machine_state, tr_diags = execute_transport(
            bridge, step_ctx, machine_state, services,
        )
        diags.extend(tr_diags)
        result.degradation_policy_used = degradation_policy.id
        return result, machine_state, diags

    result.degradation_policy_used = degradation_policy.id

    # Enforce preserve_fields: if the policy specifies fields to preserve,
    # copy them from the source aggregate to the destination aggregate
    if degradation_policy.preserve_fields and result.srcAggregate and result.dstAggregate:
        for field_name in degradation_policy.preserve_fields:
            src_val = getattr(result.srcAggregate, field_name, None)
            if src_val is not None and hasattr(result.dstAggregate, field_name):
                object.__setattr__(result.dstAggregate, field_name, src_val)

    # Check max_loss constraint
    if degradation_policy.max_loss is not None and result.status == "degraded":
        # Compute a simple loss metric: count of items in bridge.lose
        # relative to total facets (preserve + lose)
        total_facets = len(bridge.preserve) + len(bridge.lose)
        if total_facets > 0:
            loss_ratio = len(bridge.lose) / total_facets
        else:
            loss_ratio = 0.0

        if loss_ratio > degradation_policy.max_loss:
            diags.append({
                "severity": "error",
                "code": "degradation_exceeds_max_loss",
                "policy_id": degradation_policy.id,
                "loss_ratio": loss_ratio,
                "max_loss": degradation_policy.max_loss,
                "message": (
                    f"Degradation loss ratio {loss_ratio:.2f} exceeds "
                    f"max_loss {degradation_policy.max_loss:.2f}"
                ),
            })
            result.status = "blocked"  # type: ignore[assignment]

    return result, machine_state, diags


def validate_claim_map_result(
    claim_map_output: dict[str, Any] | None,
    bridge: BridgeNode,
    transport: TransportNode,
    claim_id: str,
    services: dict[str, Any],
) -> Diagnostics:
    """Validate claim-map results for remap_recompute mode.

    Checks:
    - claim_map output is non-empty
    - mapped claims reference valid destination frame evaluators (if known)

    Returns diagnostics for any validation failures.
    """
    diags: Diagnostics = []

    # Check that claim_map output is non-empty
    if claim_map_output is None or not claim_map_output:
        diags.append({
            "severity": "error",
            "code": "transport_mapping_missing",
            "bridge_id": bridge.id,
            "claim_id": claim_id,
            "message": f"Claim map produced empty output for claim {claim_id}",
        })
        return diags

    # Check mapped claim reference
    mapped_claim = claim_map_output.get("mappedClaim")
    if mapped_claim is None:
        diags.append({
            "severity": "error",
            "code": "transport_mapping_missing",
            "bridge_id": bridge.id,
            "claim_id": claim_id,
            "message": f"Claim map produced no mappedClaim for claim {claim_id}",
        })

    # Check that per_evaluator results reference valid destination evaluators
    per_evaluator = claim_map_output.get("per_evaluator", {})
    dst_evaluators = transport.dstEvaluators
    if dst_evaluators is not None and per_evaluator:
        dst_evaluator_set = set(dst_evaluators)
        invalid_evaluators = [
            eid for eid in per_evaluator if eid not in dst_evaluator_set
        ]
        if invalid_evaluators:
            diags.append({
                "severity": "warning",
                "code": "transport_mapping_invalid",
                "bridge_id": bridge.id,
                "claim_id": claim_id,
                "invalid_evaluators": invalid_evaluators,
                "message": (
                    f"Claim map produced results for evaluators "
                    f"{invalid_evaluators} not in dstEvaluators {dst_evaluators}"
                ),
            })

    return diags


def apply_destination_completion_policy(
    result: TransportResult,
    completion_policy: DestinationCompletionPolicy,
    bridge: BridgeNode,
    services: dict[str, Any],
) -> tuple[TransportResult, Diagnostics]:
    """Apply a destination completion policy after transport execution.

    Strategies:
    - none: do nothing
    - infer_defaults: fill missing destination facets from policy.defaults
    - require_explicit: produce diagnostic if any destination facets are missing
    - binding: call the binding from services

    Records completion actions in the result's provenance and completion_actions.
    """
    diags: Diagnostics = []

    if completion_policy.strategy == "none":
        result.completion_actions.append("completion:none")
        return result, diags

    if completion_policy.strategy == "infer_defaults":
        # Fill missing destination facets from policy.defaults
        if completion_policy.defaults:
            applied_defaults: list[str] = []
            dst_metadata = dict(result.metadata)

            for key, default_value in completion_policy.defaults.items():
                if key not in dst_metadata or dst_metadata[key] is None:
                    dst_metadata[key] = default_value
                    applied_defaults.append(key)

            result.metadata = dst_metadata
            if applied_defaults:
                result.completion_actions.append(
                    f"completion:infer_defaults:{','.join(applied_defaults)}"
                )
            else:
                result.completion_actions.append("completion:infer_defaults:no_missing")
        else:
            result.completion_actions.append("completion:infer_defaults:no_defaults")
        return result, diags

    if completion_policy.strategy == "require_explicit":
        # Check that all expected destination facets are present
        missing_facets: list[str] = []
        # Check against bridge.preserve as the expected destination facets
        dst_metadata = result.metadata
        for facet in bridge.preserve:
            if facet not in dst_metadata or dst_metadata.get(facet) is None:
                missing_facets.append(facet)

        if missing_facets:
            diags.append({
                "severity": "error",
                "code": "destination_completion_missing_facets",
                "policy_id": completion_policy.id,
                "bridge_id": bridge.id,
                "missing_facets": missing_facets,
                "message": (
                    f"Destination missing required facets: {missing_facets}"
                ),
            })
            result.completion_actions.append(
                f"completion:require_explicit:missing:{','.join(missing_facets)}"
            )
        else:
            result.completion_actions.append("completion:require_explicit:ok")
        return result, diags

    if completion_policy.strategy == "binding":
        binding_name = completion_policy.binding
        if binding_name is None:
            diags.append({
                "severity": "error",
                "code": "destination_completion_no_binding",
                "policy_id": completion_policy.id,
                "message": "Binding completion strategy requires a binding name",
            })
            result.completion_actions.append("completion:binding:no_binding")
            return result, diags

        completion_handlers: dict[str, Callable] = services.get(
            "__completion_handlers__", {}
        )
        handler = completion_handlers.get(binding_name)

        if handler is None:
            diags.append({
                "severity": "warning",
                "code": "destination_completion_binding_not_found",
                "policy_id": completion_policy.id,
                "binding": binding_name,
                "message": f"Completion binding '{binding_name}' not found in services",
            })
            result.completion_actions.append(f"completion:binding:not_found:{binding_name}")
            return result, diags

        try:
            updated_result = handler(result, bridge, services, completion_policy)
            if isinstance(updated_result, TransportResult):
                result = updated_result
            elif isinstance(updated_result, dict):
                # Merge updates into existing result metadata
                result.metadata.update(updated_result)
            result.completion_actions.append(f"completion:binding:{binding_name}")
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "destination_completion_binding_error",
                "policy_id": completion_policy.id,
                "binding": binding_name,
                "message": str(exc),
            })
            result.completion_actions.append(f"completion:binding:error:{binding_name}")

        return result, diags

    # Unknown strategy
    diags.append({
        "severity": "error",
        "code": "destination_completion_unknown_strategy",
        "policy_id": completion_policy.id,
        "strategy": completion_policy.strategy,
        "message": f"Unknown completion strategy: {completion_policy.strategy}",
    })
    return result, diags


# ===================================================================
# SUMMARY POLICY FRAMEWORK (post-evaluation, non-normative)
# ===================================================================
#
# This section implements the summary policy layer described in T3.
# Summaries are additive artifacts produced AFTER normal evaluation.
# They do NOT modify fold_block, apply_resolution_policy, or any
# existing evaluation functions.
# ===================================================================

from typing import Protocol as TypingProtocol, runtime_checkable

from ..models.conformance import SummaryRequest, SummaryResult


# ---------------------------------------------------------------------------
# Severity ordering for truth values: F > B > N > T (worst-first)
# ---------------------------------------------------------------------------

_SUMMARY_SEVERITY_ORDER: dict[str, int] = {"F": 0, "B": 1, "N": 2, "T": 3}
_SUMMARY_SEVERITY_RANK_TO_TRUTH: dict[int, str] = {
    v: k for k, v in _SUMMARY_SEVERITY_ORDER.items()
}


def _summary_worst_truth(truths: list[str]) -> str:
    """Return the worst truth value using severity ordering F > B > N > T."""
    if not truths:
        return "N"
    return min(truths, key=lambda t: _SUMMARY_SEVERITY_ORDER.get(t, 2))


# ---------------------------------------------------------------------------
# SummaryPolicyProtocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SummaryPolicyProtocol(TypingProtocol):
    """Protocol for summary policy implementations.

    Summary policies are post-evaluation artifacts that consume completed
    evaluation results and produce non-normative SummaryResult instances.
    """

    def summarize(
        self,
        request: SummaryRequest,
        eval_results: dict[str, Any],
        services: dict[str, Any],
    ) -> SummaryResult: ...


# ---------------------------------------------------------------------------
# Helper: extract truths from eval_results for various scopes
# ---------------------------------------------------------------------------


def _extract_truths_for_scope(
    scope: str,
    target_ids: list[str],
    eval_results: dict[str, Any],
) -> list[str]:
    """Extract truth values from eval_results based on scope.

    eval_results is expected to contain keys like:
      - "per_claim_aggregates": dict[str, EvalNode]
      - "per_block_aggregates": dict[str, EvalNode]
      - "block_results": list[BlockResult]
      - "claim_results": list[ClaimResult]
    """
    truths: list[str] = []

    if scope == "block":
        # Aggregate truths from claims within the specified block(s)
        per_claim = eval_results.get("per_claim_aggregates", {})
        block_results = eval_results.get("block_results", [])
        for br in block_results:
            block_id = br.block_id if hasattr(br, "block_id") else br.get("block_id", "")
            if target_ids and block_id not in target_ids:
                continue
            claims = br.claims if hasattr(br, "claims") else br.get("claims", [])
            for cid in claims:
                agg = per_claim.get(cid)
                if agg is not None:
                    t = agg.truth if hasattr(agg, "truth") else agg.get("truth", "N")
                    truths.append(t)

    elif scope == "bundle":
        # Aggregate truths from all block aggregates
        per_block = eval_results.get("per_block_aggregates", {})
        for block_id, agg in per_block.items():
            if target_ids and block_id not in target_ids:
                continue
            t = agg.truth if hasattr(agg, "truth") else agg.get("truth", "N")
            truths.append(t)

    elif scope == "claim_collection":
        # Aggregate truths from specified claim aggregates
        per_claim = eval_results.get("per_claim_aggregates", {})
        for cid in target_ids:
            agg = per_claim.get(cid)
            if agg is not None:
                t = agg.truth if hasattr(agg, "truth") else agg.get("truth", "N")
                truths.append(t)

    elif scope == "session":
        # Aggregate truths from all block aggregates across the session
        per_block = eval_results.get("per_block_aggregates", {})
        for agg in per_block.values():
            t = agg.truth if hasattr(agg, "truth") else agg.get("truth", "N")
            truths.append(t)

    return truths


def _extract_block_aggregate(
    target_ids: list[str],
    eval_results: dict[str, Any],
) -> tuple[str | None, float | None]:
    """Extract aggregate truth and support for block scope."""
    per_block = eval_results.get("per_block_aggregates", {})
    for bid in target_ids:
        agg = per_block.get(bid)
        if agg is not None:
            t = agg.truth if hasattr(agg, "truth") else agg.get("truth")
            s = agg.support if hasattr(agg, "support") else agg.get("support")
            return t, None  # support is a SupportValue string, not a float
    return None, None


# ---------------------------------------------------------------------------
# PassthroughNormativePolicy
# ---------------------------------------------------------------------------


class PassthroughNormativePolicy:
    """Exposes existing canonical fold/aggregate results as a summary.

    Simply passes through the normative evaluation results without
    performing any additional computation.
    """

    def summarize(
        self,
        request: SummaryRequest,
        eval_results: dict[str, Any],
        services: dict[str, Any],
    ) -> SummaryResult:
        scope = request.scope
        target_ids = request.target_ids

        if scope == "block":
            per_block = eval_results.get("per_block_aggregates", {})
            # Use first matching target
            for bid in target_ids:
                agg = per_block.get(bid)
                if agg is not None:
                    truth = agg.truth if hasattr(agg, "truth") else agg.get("truth")
                    return SummaryResult(
                        policy_id="passthrough_normative",
                        scope=scope,
                        normative=False,
                        summary_truth=truth,
                        detail={"source": "block_aggregate", "block_id": bid},
                        provenance=["passthrough from normative fold"],
                    )
            # No matching block found
            return SummaryResult(
                policy_id="passthrough_normative",
                scope=scope,
                normative=False,
                summary_truth="N",
                detail={"source": "block_aggregate", "note": "no matching block"},
                provenance=["passthrough from normative fold"],
            )

        elif scope == "bundle":
            per_block = eval_results.get("per_block_aggregates", {})
            truths = []
            for bid, agg in per_block.items():
                if target_ids and bid not in target_ids:
                    continue
                t = agg.truth if hasattr(agg, "truth") else agg.get("truth", "N")
                truths.append(t)
            agg_truth = _summary_worst_truth(truths) if truths else "N"
            return SummaryResult(
                policy_id="passthrough_normative",
                scope=scope,
                normative=False,
                summary_truth=agg_truth,
                detail={"source": "bundle_aggregate", "block_count": len(truths)},
                provenance=["passthrough from normative fold"],
            )

        elif scope == "claim_collection":
            per_claim = eval_results.get("per_claim_aggregates", {})
            truths = []
            for cid in target_ids:
                agg = per_claim.get(cid)
                if agg is not None:
                    t = agg.truth if hasattr(agg, "truth") else agg.get("truth", "N")
                    truths.append(t)
            agg_truth = _summary_worst_truth(truths) if truths else "N"
            return SummaryResult(
                policy_id="passthrough_normative",
                scope=scope,
                normative=False,
                summary_truth=agg_truth,
                detail={"source": "claim_collection_aggregate", "claim_count": len(truths)},
                provenance=["passthrough from normative fold"],
            )

        else:
            # session or unknown — aggregate all blocks
            per_block = eval_results.get("per_block_aggregates", {})
            truths = [
                (agg.truth if hasattr(agg, "truth") else agg.get("truth", "N"))
                for agg in per_block.values()
            ]
            agg_truth = _summary_worst_truth(truths) if truths else "N"
            return SummaryResult(
                policy_id="passthrough_normative",
                scope=scope,
                normative=False,
                summary_truth=agg_truth,
                detail={"source": "session_aggregate", "block_count": len(truths)},
                provenance=["passthrough from normative fold"],
            )


# ---------------------------------------------------------------------------
# SeverityMaxPolicy
# ---------------------------------------------------------------------------


class SeverityMaxPolicy:
    """Summarize using severity ordering: F > B > N > T.

    Returns the worst truth value across the scoped results.
    """

    def summarize(
        self,
        request: SummaryRequest,
        eval_results: dict[str, Any],
        services: dict[str, Any],
    ) -> SummaryResult:
        truths = _extract_truths_for_scope(
            request.scope, request.target_ids, eval_results
        )
        worst = _summary_worst_truth(truths) if truths else "N"
        count = len(truths)
        return SummaryResult(
            policy_id="severity_max",
            scope=request.scope,
            normative=False,
            summary_truth=worst,
            detail={"worst_truth": worst, "result_count": count},
            provenance=[f"severity_max over {count} results"],
        )


# ---------------------------------------------------------------------------
# MajorityVotePolicy
# ---------------------------------------------------------------------------


class MajorityVotePolicy:
    """Count truth values and return the one with the highest count.

    Breaks ties using severity ordering (F > B > N > T).
    """

    def summarize(
        self,
        request: SummaryRequest,
        eval_results: dict[str, Any],
        services: dict[str, Any],
    ) -> SummaryResult:
        truths = _extract_truths_for_scope(
            request.scope, request.target_ids, eval_results
        )
        votes: dict[str, int] = {"T": 0, "F": 0, "N": 0, "B": 0}
        for t in truths:
            if t in votes:
                votes[t] += 1
            else:
                votes[t] = votes.get(t, 0) + 1

        count = len(truths)
        if count == 0:
            return SummaryResult(
                policy_id="majority_vote",
                scope=request.scope,
                normative=False,
                summary_truth="N",
                detail={"votes": votes},
                provenance=[f"majority_vote over {count} results"],
            )

        # Find the maximum vote count
        max_count = max(votes.values())
        # Collect all truths with that count
        tied = [t for t, c in votes.items() if c == max_count]
        # Break ties using severity ordering (worst wins)
        winner = _summary_worst_truth(tied)

        return SummaryResult(
            policy_id="majority_vote",
            scope=request.scope,
            normative=False,
            summary_truth=winner,
            detail={"votes": votes},
            provenance=[f"majority_vote over {count} results"],
        )


# ---------------------------------------------------------------------------
# Summary policy registry
# ---------------------------------------------------------------------------


def get_builtin_summary_policies() -> dict[str, SummaryPolicyProtocol]:
    """Return a dict of built-in summary policies keyed by policy id."""
    return {
        "passthrough_normative": PassthroughNormativePolicy(),
        "severity_max": SeverityMaxPolicy(),
        "majority_vote": MajorityVotePolicy(),
    }


# ---------------------------------------------------------------------------
# execute_summary: single summary request execution
# ---------------------------------------------------------------------------


def execute_summary(
    request: SummaryRequest,
    eval_results: dict[str, Any],
    services: dict[str, Any],
    policies: dict[str, SummaryPolicyProtocol],
) -> SummaryResult:
    """Execute a single summary request against the given policies.

    Looks up the requested policy by request.policy_id in the policies dict,
    calls policy.summarize(), and returns the SummaryResult.

    If the policy is not found, returns a SummaryResult with a diagnostic
    keyed "summary_policy_not_found".
    """
    policy = policies.get(request.policy_id)
    if policy is None:
        return SummaryResult(
            policy_id=request.policy_id,
            scope=request.scope,
            normative=False,
            summary_truth=None,
            diagnostics=[
                {
                    "severity": "error",
                    "code": "summary_policy_not_found",
                    "policy_id": request.policy_id,
                    "message": f"Summary policy '{request.policy_id}' not found",
                }
            ],
        )
    return policy.summarize(request, eval_results, services)


# ---------------------------------------------------------------------------
# run_summaries: batch summary execution (post-evaluation entry point)
# ---------------------------------------------------------------------------


def run_summaries(
    requests: list[SummaryRequest],
    eval_results: dict[str, Any],
    services: dict[str, Any],
    policies: dict[str, SummaryPolicyProtocol] | None = None,
) -> list[SummaryResult]:
    """Execute a batch of summary requests against completed evaluation results.

    This is the main integration point, called AFTER a bundle/session evaluation.
    It does NOT modify eval_results — it purely reads them and produces
    non-normative SummaryResult artifacts.

    Args:
        requests: List of SummaryRequest describing what summaries to produce.
        eval_results: Completed evaluation results (from runner). Expected keys:
            - "per_claim_aggregates": dict[str, EvalNode]
            - "per_block_aggregates": dict[str, EvalNode]
            - "block_results": list[BlockResult]
            - "claim_results": list[ClaimResult]
        services: Service dict (passed through to policies).
        policies: Optional dict of policy_id -> policy. If None, uses
            get_builtin_summary_policies().

    Returns:
        List of SummaryResult, one per request.
    """
    if policies is None:
        policies = get_builtin_summary_policies()

    return [
        execute_summary(request, eval_results, services, policies)
        for request in requests
    ]


# ===================================================================
# T4: EVIDENCE INFERENCE LAYER + STRONGER ADEQUACY EXECUTION
# ===================================================================
#
# Part A: Evidence inference (opt-in).
# Part B: Basis-driven adequacy execution with contested aggregation.
#
# These are additive functions. They do NOT modify existing
# primitives, PrimitiveSet, or runner phases.
# ===================================================================

from typing import Protocol as _TypingProtocol, runtime_checkable as _runtime_checkable


# ---------------------------------------------------------------------------
# Part A: Evidence Inference
# ---------------------------------------------------------------------------


@_runtime_checkable
class EvidenceInferencePolicyProtocol(_TypingProtocol):
    """Protocol for evidence inference policies.

    Implementations receive declared evidence and relations, then produce
    inferred evidence relations that complement (but do not replace) the
    declared ones.
    """

    def infer(
        self,
        evidence: list[EvidenceNode],
        declared_relations: list[EvidenceRelationNode],
        services: dict[str, Any],
    ) -> list[InferredEvidenceRelation]: ...


class TransitivityInferencePolicy:
    """Deterministic transitivity-based inference policy.

    Rules:
    - If A conflicts with B, and B conflicts with C, infer A may corroborate C.
    - If A corroborates B, and B corroborates C, infer A corroborates C (transitive).

    Confidence is the product of the chain scores (0.5 for None scores).
    """

    def infer(
        self,
        evidence: list[EvidenceNode],
        declared_relations: list[EvidenceRelationNode],
        services: dict[str, Any],
    ) -> list[InferredEvidenceRelation]:
        inferred: list[InferredEvidenceRelation] = []
        # Track already-declared pairs to avoid redundant inferences
        declared_pairs: set[tuple[str, str, str]] = set()
        for r in declared_relations:
            declared_pairs.add((r.lhs, r.rhs, r.kind))
            declared_pairs.add((r.rhs, r.lhs, r.kind))

        evidence_ids = {e.id for e in evidence}
        seen_inferred: set[tuple[str, str, str]] = set()
        counter = 0

        for rel1 in declared_relations:
            for rel2 in declared_relations:
                if rel1.id == rel2.id:
                    continue

                # Find shared pivot: rel1 connects (A, B), rel2 connects (B, C)
                # Check all orientations where B is shared
                pairs = self._find_transitive_pairs(rel1, rel2)
                for a, c, inferred_kind, r1, r2 in pairs:
                    if a == c:
                        continue
                    if a not in evidence_ids or c not in evidence_ids:
                        continue
                    # Canonical ordering for dedup
                    key = (min(a, c), max(a, c), inferred_kind)
                    if key in declared_pairs or key in seen_inferred:
                        continue
                    seen_inferred.add(key)

                    score1 = r1.score if r1.score is not None else 0.5
                    score2 = r2.score if r2.score is not None else 0.5
                    confidence = score1 * score2

                    counter += 1
                    inferred.append(InferredEvidenceRelation(
                        id=f"inferred-{counter}",
                        lhs=a,
                        rhs=c,
                        kind=inferred_kind,
                        confidence=confidence,
                        method="transitivity",
                        declared=False,
                        provenance=[
                            f"inferred via transitivity from {r1.id} + {r2.id}"
                        ],
                    ))

        return inferred

    @staticmethod
    def _find_transitive_pairs(
        rel1: EvidenceRelationNode,
        rel2: EvidenceRelationNode,
    ) -> list[tuple[str, str, str, EvidenceRelationNode, EvidenceRelationNode]]:
        """Find (A, C, inferred_kind, rel1, rel2) from two relations sharing a pivot B."""
        results: list[tuple[str, str, str, EvidenceRelationNode, EvidenceRelationNode]] = []

        # Gather edges: each relation (lhs, rhs, kind) is undirected
        edges1 = [(rel1.lhs, rel1.rhs), (rel1.rhs, rel1.lhs)]
        edges2 = [(rel2.lhs, rel2.rhs), (rel2.rhs, rel2.lhs)]

        for a, b1 in edges1:
            for b2, c in edges2:
                if b1 != b2:
                    continue
                # a -- rel1.kind -- b -- rel2.kind -- c
                inferred_kind = TransitivityInferencePolicy._combine_kinds(
                    rel1.kind, rel2.kind
                )
                if inferred_kind is not None:
                    results.append((a, c, inferred_kind, rel1, rel2))

        return results

    @staticmethod
    def _combine_kinds(kind1: str, kind2: str) -> str | None:
        """Combine two relation kinds to determine the inferred kind.

        - conflicts + conflicts -> corroborates (enemy of my enemy)
        - corroborates + corroborates -> corroborates (transitive)
        """
        if kind1 == "conflicts" and kind2 == "conflicts":
            return "corroborates"
        if kind1 == "corroborates" and kind2 == "corroborates":
            return "corroborates"
        return None


def build_evidence_view_with_inference(
    claim_id: str,
    evidence_nodes: list[EvidenceNode],
    declared_relations: list[EvidenceRelationNode],
    inference_policy: EvidenceInferencePolicyProtocol | None,
    services: dict[str, Any],
) -> tuple[ClaimEvidenceView, list[InferredEvidenceRelation], Diagnostics]:
    """Build an evidence view with optional inference.

    If inference_policy is None, behaves like the declared-only path.
    If provided, also runs inference and returns inferred relations separately.
    Inferred relations do NOT appear in ClaimEvidenceView.relations (declared-only).
    """
    diags: Diagnostics = []

    # Build evidence lookup
    evidence_by_id: dict[str, EvidenceNode] = {e.id: e for e in evidence_nodes}

    # Relevant relations for this claim's evidence
    explicit_ids: set[str] = {e.id for e in evidence_nodes}
    relevant_relations: list[EvidenceRelationNode] = [
        r for r in declared_relations
        if r.lhs in explicit_ids or r.rhs in explicit_ids
    ]

    # Cross-conflict score
    conflict_scores = [
        r.score for r in relevant_relations
        if r.kind == "conflicts" and r.score is not None
    ]
    cross_conflict_score = max(conflict_scores) if conflict_scores else None

    # Completeness summary
    completeness_values = [
        e.completeness for e in evidence_nodes if e.completeness is not None
    ]
    completeness_summary = min(completeness_values) if completeness_values else None

    view = ClaimEvidenceView(
        claim_id=claim_id,
        explicit_evidence=list(evidence_nodes),
        related_evidence=[],
        relations=relevant_relations,
        cross_conflict_score=cross_conflict_score,
        completeness_summary=completeness_summary,
    )

    # Run inference if policy provided
    inferred: list[InferredEvidenceRelation] = []
    if inference_policy is not None:
        try:
            inferred = inference_policy.infer(evidence_nodes, declared_relations, services)
        except Exception as exc:
            diags.append({
                "severity": "warning",
                "code": "evidence_inference_error",
                "claim_id": claim_id,
                "message": str(exc),
            })

    return view, inferred, diags


def get_evidence_view_combined(
    evidence_view: ClaimEvidenceView,
    inferred_relations: list[InferredEvidenceRelation],
) -> dict[str, Any]:
    """Combine declared evidence view with inferred relations.

    Returns a dict with both perspectives:
    - declared_only: the original ClaimEvidenceView
    - inferred: list of InferredEvidenceRelation
    - combined_relations: declared + inferred (all relation objects)
    """
    combined: list[Any] = list(evidence_view.relations) + list(inferred_relations)
    return {
        "declared_only": evidence_view,
        "inferred": inferred_relations,
        "combined_relations": combined,
    }


def get_builtin_inference_policies() -> dict[str, EvidenceInferencePolicyProtocol]:
    """Return a dict of built-in evidence inference policies keyed by id."""
    return {
        "transitivity": TransitivityInferencePolicy(),
    }


# ---------------------------------------------------------------------------
# Part B: Stronger Adequacy Execution
# ---------------------------------------------------------------------------


def detect_basis_circularity(
    assessment: AdequacyAssessmentNode,
) -> tuple[bool, Diagnostics]:
    """Check if an assessment's basis references include its own id or task.

    Returns (is_circular, diagnostics).
    """
    diags: Diagnostics = []
    # Self-referencing: basis contains the assessment's own id
    if assessment.id in assessment.basis:
        diags.append({
            "severity": "error",
            "code": "circular_basis",
            "subject": assessment.id,
            "message": f"Assessment {assessment.id} has circular basis: "
                       f"references itself",
        })
        return True, diags

    # Also check if the assessment's task appears as a basis reference
    # (a weaker form of circularity)
    if assessment.task in assessment.basis:
        diags.append({
            "severity": "warning",
            "code": "circular_basis",
            "subject": assessment.id,
            "message": f"Assessment {assessment.id} has basis referencing its own "
                       f"task '{assessment.task}'",
        })
        return True, diags

    return False, diags


def execute_adequacy_with_basis(
    assessment: AdequacyAssessmentNode,
    basis_claims: list[str],
    basis_results: dict[str, Any],
    services: dict[str, Any],
) -> tuple[AdequacyExecutionTrace, Diagnostics]:
    """Execute adequacy with basis resolution.

    Resolves each basis item, builds BasisResolutionEntry for each,
    optionally calls method bindings, compares computed vs declared scores,
    and detects failure kinds.
    """
    diags: Diagnostics = []

    # Detect circularity
    is_circular, circ_diags = detect_basis_circularity(assessment)
    diags.extend(circ_diags)
    if is_circular:
        return AdequacyExecutionTrace(
            assessment_id=assessment.id,
            method=assessment.method,
            basis_resolution=[],
            computed_score=None,
            declared_score=assessment.score if assessment.score != "N" else None,
            score_divergence=None,
            threshold=assessment.threshold,
            adequate=False,
            failure_kind="circular_basis",
            provenance=[assessment.id, assessment.producer],
            diagnostics=list(diags),
        ), diags

    # Resolve basis items
    basis_entries: list[BasisResolutionEntry] = []
    has_unresolved = False
    for basis_id in basis_claims:
        result = basis_results.get(basis_id)
        if result is not None:
            # Determine truth from result
            if hasattr(result, "truth"):
                truth_val = str(result.truth)
            elif isinstance(result, dict):
                truth_val = str(result.get("truth", "N"))
            else:
                truth_val = "N"
            basis_entries.append(BasisResolutionEntry(
                basis_id=basis_id,
                resolved=True,
                truth=truth_val,
                source="claim",
                provenance=[basis_id],
            ))
        else:
            has_unresolved = True
            basis_entries.append(BasisResolutionEntry(
                basis_id=basis_id,
                resolved=False,
                truth=None,
                source="claim",
                provenance=[basis_id],
            ))

    # Determine declared score
    declared_score: float | None = None
    if assessment.score is not None and assessment.score != "N":
        declared_score = float(assessment.score)

    # Try to compute score via method binding
    computed_score: float | None = None
    method_handler = services.get("adequacy_handlers", {}).get(assessment.method)
    if method_handler is not None:
        try:
            computed = method_handler(assessment)
            if isinstance(computed, (int, float)):
                computed_score = float(computed)
        except Exception as exc:
            diags.append({
                "severity": "warning",
                "code": "adequacy_method_error",
                "subject": assessment.id,
                "message": str(exc),
            })

    # If no computed score, use declared
    effective_score = computed_score if computed_score is not None else declared_score

    # Score divergence
    score_divergence: float | None = None
    if computed_score is not None and declared_score is not None:
        score_divergence = abs(computed_score - declared_score)

    # Determine adequacy and failure kind
    adequate: bool | None = None
    failure_kind = None
    tolerance = services.get("adequacy_divergence_tolerance", 0.1)

    if has_unresolved:
        adequate = False
        failure_kind = "basis_failure"
    elif effective_score is not None:
        adequate = effective_score >= assessment.threshold
        if not adequate:
            failure_kind = "threshold"
        elif score_divergence is not None and score_divergence > tolerance:
            failure_kind = "method_conflict"
    else:
        adequate = False
        failure_kind = "policy_failure"

    trace = AdequacyExecutionTrace(
        assessment_id=assessment.id,
        method=assessment.method,
        basis_resolution=basis_entries,
        computed_score=computed_score,
        declared_score=declared_score,
        score_divergence=score_divergence,
        threshold=assessment.threshold,
        adequate=adequate,
        failure_kind=failure_kind,
        provenance=[assessment.id, assessment.producer],
        diagnostics=list(diags),
    )
    return trace, diags


def aggregate_contested_adequacy(
    assessments: list[AdequacyAssessmentNode],
    basis_results: dict[str, Any],
    resolution_kind: str,
    services: dict[str, Any],
) -> tuple[AdequacyExecutionTrace, Diagnostics]:
    """Multi-producer adequacy aggregation.

    resolution_kind is one of:
    - "single": use the first assessment only
    - "paraconsistent_union": all must agree; disagreement -> truth="B"
    - "priority_order": use first adequate, or first if all inadequate
    - "adjudicated": delegate to adjudicator in services; fallback to paraconsistent_union
    """
    diags: Diagnostics = []

    if not assessments:
        return AdequacyExecutionTrace(
            assessment_id="__empty__",
            method="none",
            adequate=False,
            failure_kind="policy_failure",
            provenance=[],
            diagnostics=[{
                "severity": "warning",
                "code": "no_assessments",
                "message": "No assessments provided for aggregation",
            }],
        ), diags

    # Execute each assessment individually
    traces: list[AdequacyExecutionTrace] = []
    for aa in assessments:
        trace, aa_diags = execute_adequacy_with_basis(
            aa, aa.basis, basis_results, services,
        )
        traces.append(trace)
        diags.extend(aa_diags)

    if resolution_kind == "single":
        result_trace = traces[0]
        return result_trace, diags

    elif resolution_kind == "paraconsistent_union":
        return _aggregate_paraconsistent(assessments, traces, diags)

    elif resolution_kind == "priority_order":
        # Use first adequate trace, or first if all inadequate
        for trace in traces:
            if trace.adequate:
                return trace, diags
        return traces[0], diags

    elif resolution_kind == "adjudicated":
        adjudicator = services.get("adequacy_adjudicator")
        if adjudicator is not None:
            try:
                result = adjudicator(assessments, traces)
                if isinstance(result, AdequacyExecutionTrace):
                    return result, diags
                if isinstance(result, tuple) and len(result) >= 1:
                    return result[0], diags
            except Exception as exc:
                diags.append({
                    "severity": "warning",
                    "code": "adjudicator_error",
                    "message": str(exc),
                })
        # Fallback to paraconsistent_union
        return _aggregate_paraconsistent(assessments, traces, diags)

    # Unknown resolution kind
    diags.append({
        "severity": "error",
        "code": "unknown_resolution_kind",
        "message": f"Unknown resolution kind: {resolution_kind}",
    })
    return traces[0], diags


def _aggregate_paraconsistent(
    assessments: list[AdequacyAssessmentNode],
    traces: list[AdequacyExecutionTrace],
    diags: Diagnostics,
) -> tuple[AdequacyExecutionTrace, Diagnostics]:
    """Paraconsistent union aggregation for adequacy traces.

    All must agree on adequacy. If they disagree, failure_kind="method_conflict".
    """
    adequacy_values = [t.adequate for t in traces if t.adequate is not None]
    all_agree = len(set(adequacy_values)) <= 1

    if all_agree and adequacy_values:
        # All agree
        adequate = adequacy_values[0]
        failure_kind = traces[0].failure_kind if not adequate else None
    else:
        # Disagreement
        adequate = False
        failure_kind = "method_conflict"

    # Merge basis resolutions and provenance
    all_basis: list[BasisResolutionEntry] = []
    all_provenance: list[str] = []
    for t in traces:
        all_basis.extend(t.basis_resolution)
        all_provenance.extend(t.provenance)

    # Use first assessment as representative
    first = assessments[0]
    first_trace = traces[0]

    return AdequacyExecutionTrace(
        assessment_id=first.id,
        method=first.method,
        basis_resolution=all_basis,
        computed_score=first_trace.computed_score,
        declared_score=first_trace.declared_score,
        score_divergence=first_trace.score_divergence,
        threshold=first.threshold,
        adequate=adequate,
        failure_kind=failure_kind,
        provenance=sorted(set(all_provenance)),
        diagnostics=list(diags),
    ), diags
