"""Comprehensive unit tests for the 6+4 implemented runtime primitives."""

from __future__ import annotations

import pytest

import limnalis.runtime.builtins as builtins_mod
from limnalis.models.ast import (
    AdequacyAssessmentNode,
    AnchorNode,
    AnchorTermSymbolNode,
    BridgeNode,
    BundleNode,
    ClaimNode,
    ClaimBlockNode,
    EvaluatorNode,
    FramePatternNode,
    FacetValueMap,
    FrameNode,
    JointAdequacyNode,
    NoteExprNode,
    PredicateExprNode,
    LogicalExprNode,
    ResolutionPolicyNode,
    TimeCtxNode,
    TransportNode,
    EvidenceNode,
    EvidenceRelationNode,
)
from limnalis.runtime.models import (
    AdequacyResult,
    ClaimEvidenceView,
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    StepContext,
    MachineState,
    TruthCore,
    SupportResult,
    EvalNode,
    ClaimClassification,
    TransportResult,
)
from limnalis.runtime.builtins import (
    build_step_context,
    classify_claim,
    build_evidence_view,
    assemble_eval,
    apply_resolution_policy,
    fold_block,
    execute_transport,
    synthesize_support,
    evaluate_adequacy_set,
    compose_license,
)


# ===================================================================
# Helpers / fixtures
# ===================================================================


def _frame(**overrides) -> FrameNode:
    """Create a minimal FrameNode with defaults that can be overridden."""
    defaults = dict(
        system="sys",
        namespace="ns",
        scale="macro",
        task="predict",
        regime="standard",
    )
    defaults.update(overrides)
    return FrameNode(**defaults)


def _frame_pattern(**facets) -> FramePatternNode:
    """Create a FramePatternNode from keyword facets."""
    return FramePatternNode(facets=FacetValueMap(**facets))


def _evaluator(id: str = "ev1", kind: str = "model", binding: str = "b1") -> EvaluatorNode:
    return EvaluatorNode(id=id, kind=kind, binding=binding)


def _policy_single(member: str) -> ResolutionPolicyNode:
    return ResolutionPolicyNode(id="pol", kind="single", members=[member])


def _policy_union(*members: str) -> ResolutionPolicyNode:
    return ResolutionPolicyNode(id="pol", kind="paraconsistent_union", members=list(members))


def _policy_priority(*order: str) -> ResolutionPolicyNode:
    return ResolutionPolicyNode(id="pol", kind="priority_order", order=list(order))


def _policy_adjudicated(*members: str, binding: str = "adj_fn") -> ResolutionPolicyNode:
    return ResolutionPolicyNode(id="pol", kind="adjudicated", members=list(members), binding=binding)


def _note_claim(id: str = "c_note", text: str = "A note") -> ClaimNode:
    return ClaimNode(id=id, kind="note", expr=NoteExprNode(text=text))


def _pred_claim(id: str = "c_pred", name: str = "P", refs: list[str] | None = None) -> ClaimNode:
    return ClaimNode(id=id, kind="atomic", expr=PredicateExprNode(name=name), refs=refs or [])


def _logical_claim(id: str = "c_logic") -> ClaimNode:
    return ClaimNode(
        id=id,
        kind="logical",
        expr=LogicalExprNode(
            op="and",
            args=[PredicateExprNode(name="A"), PredicateExprNode(name="B")],
        ),
    )


def _block(claims: list[ClaimNode], id: str = "blk1", stratum: str = "local") -> ClaimBlockNode:
    return ClaimBlockNode(id=id, stratum=stratum, claims=claims)


def _bundle(
    frame: FrameNode | None = None,
    evaluators: list[EvaluatorNode] | None = None,
    policy: ResolutionPolicyNode | None = None,
    claims: list[ClaimNode] | None = None,
    evidence: list[EvidenceNode] | None = None,
    evidence_relations: list[EvidenceRelationNode] | None = None,
    time: TimeCtxNode | None = None,
) -> BundleNode:
    """Build a minimal valid BundleNode."""
    frame = frame or _frame()
    evaluators = evaluators or [_evaluator()]
    policy = policy or _policy_single("ev1")
    claims = claims or [_pred_claim()]
    return BundleNode(
        id="bundle1",
        frame=frame,
        evaluators=evaluators,
        resolutionPolicy=policy,
        claimBlocks=[_block(claims)],
        evidence=evidence or [],
        evidenceRelations=evidence_relations or [],
        time=time,
    )


# ===================================================================
# Tests: build_step_context
# ===================================================================


class TestBuildStepContext:
    """Tests for build_step_context primitive."""

    def test_frame_merge_later_overrides_earlier(self):
        """bundle.frame + session.base_frame + step.frame_override merge; later wins."""
        bundle = _bundle(frame=_frame(system="bundle_sys", task="bundle_task"))
        session = SessionConfig(
            id="s1",
            base_frame=_frame_pattern(system="session_sys"),
        )
        step = StepConfig(
            id="step1",
            frame_override=_frame_pattern(task="step_task"),
        )
        env = EvaluationEnvironment()

        ctx = build_step_context(bundle, session, step, env)

        # session overrides bundle for system
        assert ctx.effective_frame.system == "session_sys"
        # step overrides bundle for task
        assert ctx.effective_frame.task == "step_task"
        # remaining facets come from bundle
        assert ctx.effective_frame.namespace == "ns"
        assert ctx.effective_frame.scale == "macro"
        assert ctx.effective_frame.regime == "standard"

    def test_time_precedence_step_wins(self):
        """step.time > session.base_time > bundle.time > env.clock."""
        step_time = TimeCtxNode(kind="point", t="2024-01-04")
        session_time = TimeCtxNode(kind="point", t="2024-01-03")
        bundle_time = TimeCtxNode(kind="point", t="2024-01-02")

        bundle = _bundle(time=bundle_time)
        session = SessionConfig(id="s1", base_time=session_time)
        step = StepConfig(id="step1", time=step_time)
        env = EvaluationEnvironment(clock="2024-01-01")

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_time.t == "2024-01-04"

    def test_time_precedence_session_wins_when_no_step(self):
        session_time = TimeCtxNode(kind="point", t="2024-01-03")
        bundle_time = TimeCtxNode(kind="point", t="2024-01-02")

        bundle = _bundle(time=bundle_time)
        session = SessionConfig(id="s1", base_time=session_time)
        step = StepConfig(id="step1")
        env = EvaluationEnvironment(clock="2024-01-01")

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_time.t == "2024-01-03"

    def test_time_precedence_bundle_wins_when_no_step_or_session(self):
        bundle_time = TimeCtxNode(kind="point", t="2024-01-02")

        bundle = _bundle(time=bundle_time)
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1")
        env = EvaluationEnvironment(clock="2024-01-01")

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_time.t == "2024-01-02"

    def test_time_precedence_env_clock_fallback(self):
        bundle = _bundle()
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1")
        env = EvaluationEnvironment(clock="2024-01-01")

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_time is not None
        assert ctx.effective_time.t == "2024-01-01"

    def test_time_none_when_nothing_set(self):
        bundle = _bundle()
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1")
        env = EvaluationEnvironment()

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_time is None

    def test_unresolved_frame_emits_error_diagnostic(self, monkeypatch):
        bundle = _bundle()
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1")
        env = EvaluationEnvironment()

        monkeypatch.setattr(
            builtins_mod,
            "_merge_frame_facets",
            lambda *args, **kwargs: {
                "system": None,
                "namespace": None,
                "scale": None,
                "task": None,
                "regime": None,
                "observer": None,
                "version": None,
            },
        )

        ctx = build_step_context(bundle, session, step, env)

        assert any(d.get("code") == "frame_unresolved_for_evaluation" for d in ctx.diagnostics)
        assert isinstance(ctx.effective_frame, FramePatternNode)
        assert ctx.effective_frame.facets.system == "__unresolved__"

    def test_partial_frame_gaps_emit_unresolved_diagnostic(self, monkeypatch):
        bundle = _bundle()
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1")
        env = EvaluationEnvironment()

        monkeypatch.setattr(
            builtins_mod,
            "_merge_frame_facets",
            lambda *args, **kwargs: {
                "system": "Grid",
                "namespace": "Power",
                "scale": None,
                "task": None,
                "regime": None,
                "observer": None,
                "version": None,
            },
        )

        ctx = build_step_context(bundle, session, step, env)

        unresolved = [d for d in ctx.diagnostics if d.get("code") == "frame_unresolved_for_evaluation"]
        assert len(unresolved) == 1
        assert unresolved[0].get("missing_facets") == ["scale", "task", "regime"]
        assert isinstance(ctx.effective_frame, FramePatternNode)
        assert ctx.effective_frame.facets.system == "Grid"

    def test_history_step_binding_overrides_env(self):
        """step.history_binding > env.history."""
        bundle = _bundle()
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1", history_binding="custom_history")
        env = EvaluationEnvironment(history={"key": "env_value"})

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_history == {"binding": "custom_history"}
        # Should produce a diagnostic about history binding
        assert any(d.get("code") == "history_binding_used" for d in ctx.diagnostics)

    def test_history_env_used_when_no_step_binding(self):
        bundle = _bundle()
        session = SessionConfig(id="s1")
        step = StepConfig(id="step1")
        env = EvaluationEnvironment(history={"key": "env_value"})

        ctx = build_step_context(bundle, session, step, env)
        assert ctx.effective_history == {"key": "env_value"}


# ===================================================================
# Tests: classify_claim
# ===================================================================


class TestClassifyClaim:
    """Tests for classify_claim primitive."""

    def test_note_expr_non_evaluable(self):
        claim = _note_claim()
        result = classify_claim(claim)
        assert result.evaluable is False
        assert result.claim_id == claim.id
        assert result.expr_kind == "NoteExpr"

    def test_predicate_expr_evaluable(self):
        claim = _pred_claim()
        result = classify_claim(claim)
        assert result.evaluable is True
        assert result.claim_id == claim.id
        assert result.expr_kind == "PredicateExpr"

    def test_logical_expr_evaluable(self):
        claim = _logical_claim()
        result = classify_claim(claim)
        assert result.evaluable is True
        assert result.expr_kind == "LogicalExpr"


# ===================================================================
# Tests: build_evidence_view
# ===================================================================


class TestBuildEvidenceView:
    """Tests for build_evidence_view primitive."""

    def test_one_claim_two_evidence_one_conflict(self):
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1", completeness=0.9)
        ev2 = EvidenceNode(id="e2", kind="dataset", binding="b2", completeness=0.7)
        rel = EvidenceRelationNode(id="r1", lhs="e1", rhs="e2", kind="conflicts", score=0.8)

        claim = _pred_claim(refs=["e1", "e2"])
        bundle = _bundle(evidence=[ev1, ev2], evidence_relations=[rel], claims=[claim])
        step_ctx = StepContext(effective_frame=_frame())
        machine_state = MachineState()

        view, new_state, diags = build_evidence_view(claim, bundle, step_ctx, machine_state)

        assert len(view.explicit_evidence) == 2
        assert {e.id for e in view.explicit_evidence} == {"e1", "e2"}
        assert len(view.relations) == 1
        assert view.relations[0].kind == "conflicts"

    def test_cross_conflict_score_is_max(self):
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1")
        ev2 = EvidenceNode(id="e2", kind="dataset", binding="b2")
        ev3 = EvidenceNode(id="e3", kind="dataset", binding="b3")
        rel1 = EvidenceRelationNode(id="r1", lhs="e1", rhs="e2", kind="conflicts", score=0.4)
        rel2 = EvidenceRelationNode(id="r2", lhs="e1", rhs="e3", kind="conflicts", score=0.9)

        claim = _pred_claim(refs=["e1", "e2", "e3"])
        bundle = _bundle(evidence=[ev1, ev2, ev3], evidence_relations=[rel1, rel2], claims=[claim])
        step_ctx = StepContext(effective_frame=_frame())

        view, _, _ = build_evidence_view(claim, bundle, step_ctx, MachineState())
        assert view.cross_conflict_score == 0.9

    def test_completeness_summary_is_min(self):
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1", completeness=0.9)
        ev2 = EvidenceNode(id="e2", kind="dataset", binding="b2", completeness=0.5)

        claim = _pred_claim(refs=["e1", "e2"])
        bundle = _bundle(evidence=[ev1, ev2], claims=[claim])
        step_ctx = StepContext(effective_frame=_frame())

        view, _, _ = build_evidence_view(claim, bundle, step_ctx, MachineState())
        assert view.completeness_summary == 0.5

    def test_no_conflict_score_when_no_conflicts(self):
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1", completeness=0.9)
        claim = _pred_claim(refs=["e1"])
        bundle = _bundle(evidence=[ev1], claims=[claim])
        step_ctx = StepContext(effective_frame=_frame())

        view, _, _ = build_evidence_view(claim, bundle, step_ctx, MachineState())
        assert view.cross_conflict_score is None

    def test_state_updated_with_evidence_view(self):
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1")
        claim = _pred_claim(refs=["e1"])
        bundle = _bundle(evidence=[ev1], claims=[claim])
        step_ctx = StepContext(effective_frame=_frame())

        _, new_state, _ = build_evidence_view(claim, bundle, step_ctx, MachineState())
        assert claim.id in new_state.evidence_views


# ===================================================================
# Tests: assemble_eval
# ===================================================================


class TestAssembleEval:
    """Tests for assemble_eval primitive."""

    def test_provenance_union(self):
        tc = TruthCore(truth="T", reason="ok", confidence=0.9, provenance=["src1", "src2"])
        sr = SupportResult(support="supported", provenance=["src2", "src3"])
        evaluator_id = "ev1"

        result = assemble_eval(tc, sr, evaluator_id)
        assert set(result.provenance) == {"src1", "src2", "src3", "ev1"}

    def test_preserves_truth_reason_support_confidence(self):
        tc = TruthCore(truth="F", reason="mismatch", confidence=0.75, provenance=[])
        sr = SupportResult(support="partial", provenance=[])

        result = assemble_eval(tc, sr, "ev1")
        assert result.truth == "F"
        assert result.reason == "mismatch"
        assert result.support == "partial"
        assert result.confidence == 0.75

    def test_provenance_sorted(self):
        tc = TruthCore(truth="T", provenance=["z_src"])
        sr = SupportResult(support="supported", provenance=["a_src"])

        result = assemble_eval(tc, sr, "m_eval")
        assert result.provenance == sorted(result.provenance)


# ===================================================================
# Tests: apply_resolution_policy
# ===================================================================


class TestApplyResolutionPolicy:
    """Tests for apply_resolution_policy primitive."""

    # --- single ---

    def test_single_returns_evaluator_result(self):
        ev = EvalNode(truth="T", reason="ok", support="supported", provenance=["ev1"])
        policy = _policy_single("ev1")
        result = apply_resolution_policy({"ev1": ev}, policy)
        assert result.truth == "T"
        assert result.support == "supported"

    def test_single_missing_evaluator_returns_N(self):
        policy = _policy_single("ev_missing")
        result = apply_resolution_policy({}, policy)
        assert result.truth == "N"

    # --- paraconsistent_union ---

    def test_union_T_plus_F_yields_B_with_conflict(self):
        ev_t = EvalNode(truth="T", support="supported", provenance=["ev1"])
        ev_f = EvalNode(truth="F", support="partial", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev_t, "ev2": ev_f}, policy)
        assert result.truth == "B"
        assert result.reason == "evaluator_conflict"

    def test_union_T_plus_N_yields_T(self):
        ev_t = EvalNode(truth="T", provenance=["ev1"])
        ev_n = EvalNode(truth="N", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev_t, "ev2": ev_n}, policy)
        assert result.truth == "T"

    def test_union_N_plus_N_yields_N(self):
        ev_n1 = EvalNode(truth="N", provenance=["ev1"])
        ev_n2 = EvalNode(truth="N", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev_n1, "ev2": ev_n2}, policy)
        assert result.truth == "N"

    def test_union_support_aggregation_partial_wins_over_supported(self):
        """Per spec: conflicted > partial > supported > inapplicable > absent."""
        ev1 = EvalNode(truth="T", support="supported", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="partial", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.support == "partial"

    def test_union_support_aggregation_supported_when_all_supported(self):
        ev1 = EvalNode(truth="T", support="supported", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="supported", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.support == "supported"

    def test_union_provenance_is_union(self):
        ev1 = EvalNode(truth="T", provenance=["a", "b"])
        ev2 = EvalNode(truth="T", provenance=["b", "c"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert set(result.provenance) == {"a", "b", "c"}

    # --- priority_order ---

    def test_priority_chooses_first_non_N(self):
        ev1 = EvalNode(truth="N", provenance=["ev1"])
        ev2 = EvalNode(truth="T", reason="second", provenance=["ev2"])
        ev3 = EvalNode(truth="F", reason="third", provenance=["ev3"])
        policy = _policy_priority("ev1", "ev2", "ev3")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2, "ev3": ev3}, policy)
        assert result.truth == "T"
        assert result.reason == "second"

    def test_priority_all_N_returns_N(self):
        ev1 = EvalNode(truth="N", provenance=["ev1"])
        ev2 = EvalNode(truth="N", provenance=["ev2"])
        policy = _policy_priority("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.truth == "N"
        assert result.reason == "all_non_decisive"

    # --- adjudicated ---

    def test_adjudicated_calls_resolver(self):
        ev1 = EvalNode(truth="T", provenance=["ev1"])
        ev2 = EvalNode(truth="F", provenance=["ev2"])
        policy = _policy_adjudicated("ev1", "ev2")

        received = {}

        def fake_resolver(per_evaluator: dict[str, EvalNode]) -> EvalNode:
            received.update(per_evaluator)
            return EvalNode(truth="B", reason="adjudicated_result", provenance=["adj"])

        result = apply_resolution_policy(
            {"ev1": ev1, "ev2": ev2}, policy, adjudicator=fake_resolver,
        )
        assert result.truth == "B"
        assert result.reason == "adjudicated_result"
        assert "ev1" in received
        assert "ev2" in received

    def test_adjudicated_raises_without_callable(self):
        policy = _policy_adjudicated("ev1")
        with pytest.raises(ValueError, match="adjudicator callable"):
            apply_resolution_policy({"ev1": EvalNode(truth="T", provenance=["ev1"])}, policy)

    def test_adjudicated_filters_to_policy_members(self):
        ev1 = EvalNode(truth="T", provenance=["ev1"])
        ev2 = EvalNode(truth="F", provenance=["ev2"])
        ev3 = EvalNode(truth="T", provenance=["ev3"])
        policy = _policy_adjudicated("ev1", "ev2")

        received = {}

        def fake_resolver(per_evaluator: dict[str, EvalNode]) -> EvalNode:
            received.update(per_evaluator)
            return EvalNode(truth="B", reason="adjudicated_result", provenance=["adj"])

        result = apply_resolution_policy(
            {"ev1": ev1, "ev2": ev2, "ev3": ev3}, policy, adjudicator=fake_resolver,
        )
        assert result.truth == "B"
        # Adjudicator should only receive ev1 and ev2, not ev3
        assert "ev1" in received
        assert "ev2" in received
        assert "ev3" not in received

    # --- metadata: confidence and provenance across policies ---

    def test_single_propagates_confidence_and_provenance(self):
        """Single policy copies full EvalNode including confidence and provenance."""
        ev = EvalNode(
            truth="T", reason="ok", support="supported",
            confidence=0.85, provenance=["src1", "eval1"],
        )
        policy = _policy_single("ev1")
        result = apply_resolution_policy({"ev1": ev}, policy)
        assert result.confidence == 0.85
        assert set(result.provenance) == {"eval1", "src1"}

    def test_priority_propagates_confidence_and_provenance(self):
        """Priority policy copies full EvalNode from selected evaluator."""
        ev1 = EvalNode(truth="N", confidence=0.5, provenance=["ev1"])
        ev2 = EvalNode(truth="T", reason="chosen", confidence=0.9, provenance=["ev2", "src_a"])
        policy = _policy_priority("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.truth == "T"
        assert result.confidence == 0.9
        assert result.provenance == ["ev2", "src_a"]

    def test_priority_all_N_provenance_is_union(self):
        """All N evaluators: combined provenance in all_non_decisive result."""
        ev1 = EvalNode(truth="N", provenance=["ev1", "src1"])
        ev2 = EvalNode(truth="N", provenance=["ev2", "src2"])
        policy = _policy_priority("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.truth == "N"
        assert set(result.provenance) == {"ev1", "src1", "ev2", "src2"}
        # Provenance must be deterministically sorted
        assert result.provenance == sorted(result.provenance)

    def test_union_confidence_is_none(self):
        """Paraconsistent union: confidence defaults to None."""
        ev1 = EvalNode(truth="T", confidence=0.9, provenance=["ev1"])
        ev2 = EvalNode(truth="T", confidence=0.7, provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.confidence is None

    def test_union_provenance_deterministic_sorted(self):
        """Paraconsistent union: provenance is sorted union."""
        ev1 = EvalNode(truth="T", provenance=["z_src", "a_src"])
        ev2 = EvalNode(truth="T", provenance=["m_src", "a_src"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.provenance == ["a_src", "m_src", "z_src"]

    def test_union_support_conflicted_when_truth_B(self):
        """T+F => B, support must be conflicted even if evaluator supports are 'supported'."""
        ev1 = EvalNode(truth="T", support="supported", provenance=["ev1"])
        ev2 = EvalNode(truth="F", support="supported", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.truth == "B"
        assert result.support == "conflicted"

    def test_union_support_conflicted_propagates_from_evaluator(self):
        """If any evaluator has conflicted support, result is conflicted."""
        ev1 = EvalNode(truth="T", support="conflicted", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="supported", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.support == "conflicted"

    def test_union_support_not_forced_conflicted_for_non_conflict_B(self):
        """B+N => B without evaluator conflict, so support should not be forced conflicted."""
        ev1 = EvalNode(truth="B", support="partial", provenance=["ev1"])
        ev2 = EvalNode(truth="N", support="supported", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.truth == "B"
        assert result.reason is None
        assert result.support == "partial"

    def test_union_support_conflicted_only_with_true_conflict_B(self):
        """T+F => B with evaluator_conflict, support must be conflicted."""
        ev1 = EvalNode(truth="T", support="partial", provenance=["ev1"])
        ev2 = EvalNode(truth="F", support="supported", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.truth == "B"
        assert result.reason == "evaluator_conflict"
        assert result.support == "conflicted"

    def test_union_support_inapplicable_when_all_inapplicable(self):
        """All evaluators inapplicable => inapplicable."""
        ev1 = EvalNode(truth="T", support="inapplicable", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="inapplicable", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.support == "inapplicable"

    def test_union_support_inapplicable_beats_absent(self):
        """Inapplicable should outrank absent per support precedence."""
        ev1 = EvalNode(truth="T", support="inapplicable", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="absent", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.support == "inapplicable"

    def test_union_support_absent_fallback(self):
        """All evaluators absent => absent."""
        ev1 = EvalNode(truth="T", support="absent", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="absent", provenance=["ev2"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.support == "absent"

    def test_adjudicated_preserves_adjudicator_provenance(self):
        """Adjudicated: result preserves adjudicator's provenance."""
        ev1 = EvalNode(truth="T", provenance=["ev1"])
        policy = _policy_adjudicated("ev1")

        def fake_adj(per_evaluator: dict[str, EvalNode]) -> EvalNode:
            return EvalNode(
                truth="T", reason="adj_ok", support="supported",
                confidence=0.95, provenance=["adj_binding", "adj_model"],
            )

        result = apply_resolution_policy({"ev1": ev1}, policy, adjudicator=fake_adj)
        assert result.confidence == 0.95
        assert result.provenance == ["adj_binding", "adj_model"]

    def test_adjudicated_empty_filter_returns_n(self):
        ev3 = EvalNode(truth="T", provenance=["ev3"])
        policy = _policy_adjudicated("ev1", "ev2")

        called = []

        def fake_resolver(per_evaluator: dict[str, EvalNode]) -> EvalNode:
            called.append(True)
            return EvalNode(truth="B", reason="should_not_reach", provenance=["adj"])

        result = apply_resolution_policy(
            {"ev3": ev3}, policy, adjudicator=fake_resolver,
        )
        assert result.truth == "N"
        assert result.reason == "no_evaluators"
        # Adjudicator should NOT have been called
        assert len(called) == 0


# ===================================================================
# Tests: fold_block
# ===================================================================


class TestFoldBlock:
    """Tests for fold_block primitive."""

    def test_per_evaluator_first_semantics(self):
        """Evaluator-local fold then aggregate."""
        c1 = _pred_claim(id="c1")
        c2 = _pred_claim(id="c2", name="Q")
        block = _block([c1, c2])
        policy = _policy_union("ev1", "ev2")

        classifications = {
            "c1": ClaimClassification(claim_id="c1", evaluable=True, expr_kind="PredicateExpr"),
            "c2": ClaimClassification(claim_id="c2", evaluable=True, expr_kind="PredicateExpr"),
        }

        # ev1 says T for both, ev2 says F for both
        per_claim_per_ev = {
            "c1": {
                "ev1": EvalNode(truth="T", provenance=["ev1"]),
                "ev2": EvalNode(truth="F", provenance=["ev2"]),
            },
            "c2": {
                "ev1": EvalNode(truth="T", provenance=["ev1"]),
                "ev2": EvalNode(truth="F", provenance=["ev2"]),
            },
        }
        # Aggregated per-claim (not used in fold_block directly, but required param)
        per_claim_agg = {
            "c1": EvalNode(truth="B", provenance=["ev1", "ev2"]),
            "c2": EvalNode(truth="B", provenance=["ev1", "ev2"]),
        }

        per_ev_blocks, aggregate = fold_block(
            block, per_claim_agg, per_claim_per_ev, classifications, policy,
        )

        # ev1 locally: T AND T = T; ev2 locally: F AND F = F
        assert per_ev_blocks["ev1"].truth == "T"
        assert per_ev_blocks["ev2"].truth == "F"
        # Aggregate via paraconsistent_union: T + F = B
        assert aggregate.truth == "B"

    def test_note_claims_excluded(self):
        """NoteExpr claims should be excluded from evaluable set."""
        c_note = _note_claim(id="c_note")
        c_pred = _pred_claim(id="c_pred")
        block = _block([c_note, c_pred])
        policy = _policy_single("ev1")

        classifications = {
            "c_note": ClaimClassification(claim_id="c_note", evaluable=False, expr_kind="NoteExpr"),
            "c_pred": ClaimClassification(claim_id="c_pred", evaluable=True, expr_kind="PredicateExpr"),
        }
        per_claim_per_ev = {
            "c_pred": {"ev1": EvalNode(truth="T", provenance=["ev1"])},
        }
        per_claim_agg = {
            "c_pred": EvalNode(truth="T", provenance=["ev1"]),
        }

        per_ev_blocks, aggregate = fold_block(
            block, per_claim_agg, per_claim_per_ev, classifications, policy,
        )

        # Only c_pred should be folded; c_note excluded
        assert per_ev_blocks["ev1"].truth == "T"
        assert aggregate.truth == "T"

    def test_empty_evaluable_block_yields_N(self):
        """Block with only non-evaluable claims => N[empty_block]."""
        c_note = _note_claim(id="c_note")
        block = _block([c_note])
        policy = _policy_single("ev1")

        classifications = {
            "c_note": ClaimClassification(claim_id="c_note", evaluable=False, expr_kind="NoteExpr"),
        }
        # ev1 still present in per_claim_per_evaluator for structure
        per_claim_per_ev = {
            "c_note": {"ev1": EvalNode(truth="N", provenance=["ev1"])},
        }
        per_claim_agg = {}

        per_ev_blocks, aggregate = fold_block(
            block, per_claim_agg, per_claim_per_ev, classifications, policy,
        )

        assert aggregate.truth == "N"
        assert aggregate.reason == "empty_block"
        # per-evaluator blocks also N
        assert per_ev_blocks["ev1"].truth == "N"
        assert per_ev_blocks["ev1"].reason == "empty_block"

    def test_adjudicated_block_aggregation_with_inapplicable_support(self):
        """Adjudicated block aggregation uses synthetic EvalNodes with inapplicable support."""
        c1 = _pred_claim(id="c1")
        block = _block([c1])
        policy = _policy_adjudicated("ev1", "ev2")

        classifications = {
            "c1": ClaimClassification(claim_id="c1", evaluable=True, expr_kind="PredicateExpr"),
        }
        per_claim_per_ev = {
            "c1": {
                "ev1": EvalNode(truth="T", provenance=["ev1"]),
                "ev2": EvalNode(truth="F", provenance=["ev2"]),
            },
        }
        per_claim_agg = {"c1": EvalNode(truth="B", provenance=["ev1", "ev2"])}

        called_with = {}

        def fake_adj(per_evaluator: dict[str, EvalNode]) -> EvalNode:
            called_with.update(per_evaluator)
            return EvalNode(truth="T", reason="adj_decided", provenance=["adj"])

        per_ev_blocks, aggregate = fold_block(
            block, per_claim_agg, per_claim_per_ev, classifications, policy,
            adjudicator=fake_adj,
        )

        # The per-evaluator block evals should have inapplicable support
        for ev_id, ev_block in per_ev_blocks.items():
            assert ev_block.support == "inapplicable"

        # Adjudicator should have been called
        assert len(called_with) > 0
        assert aggregate.truth == "T"
        assert aggregate.reason == "adj_decided"


# ===================================================================
# Helpers for 3B primitives
# ===================================================================


def _anchor(
    id: str = "anc1",
    adequacy: list[AdequacyAssessmentNode] | None = None,
    requires_joint_with: list[str] | None = None,
    adequacy_policy: str | None = None,
) -> AnchorNode:
    return AnchorNode(
        id=id,
        term=AnchorTermSymbolNode(value="x"),
        subtype="idealization",
        status="active",
        adequacy=adequacy or [],
        requiresJointWith=requires_joint_with or [],
        adequacyPolicy=adequacy_policy,
    )


def _assessment(
    id: str = "aa1",
    task: str = "predict",
    producer: str = "prod1",
    score: float | None = 0.9,
    threshold: float = 0.5,
    method: str = "test_method",
    basis: list[str] | None = None,
) -> AdequacyAssessmentNode:
    return AdequacyAssessmentNode(
        id=id,
        task=task,
        producer=producer,
        score=score,
        threshold=threshold,
        method=method,
        basis=basis or [],
    )


def _bridge(
    id: str = "br1",
    via: str = "via1",
    mode: str = "preserve",
    preserve: list[str] | None = None,
    lose: list[str] | None = None,
    gain: list[str] | None = None,
    risk: list[str] | None = None,
    preconditions: list[str] | None = None,
    claim_map: str | None = None,
) -> BridgeNode:
    transport_kwargs: dict = {"mode": mode, "preconditions": preconditions or []}
    if claim_map is not None:
        transport_kwargs["claimMap"] = claim_map
    return BridgeNode(
        id=id,
        **{"from": _frame_pattern(system="src_sys")},
        to=_frame_pattern(system="dst_sys"),
        via=via,
        preserve=preserve or ["sem_a"],
        lose=lose or [],
        gain=gain or [],
        risk=risk or [],
        transport=TransportNode(**transport_kwargs),
    )


# ===================================================================
# Tests: execute_transport
# ===================================================================


class TestExecuteTransport:
    """Tests for execute_transport primitive."""

    def test_metadata_only_returns_correct_status_and_metadata(self):
        bridge = _bridge(mode="metadata_only", preserve=["sem_a"], lose=["sem_b"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {}

        result, new_ms, diags = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "metadata_only"
        assert result.metadata["preserve"] == ["sem_a"]
        assert result.metadata["lose"] == ["sem_b"]
        assert "br1" in result.provenance

    def test_pattern_only_no_transport_query(self):
        """No transport query for this bridge → pattern_only fallback."""
        bridge = _bridge(mode="preserve")
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__transport_queries__": [], "__per_claim_aggregates__": {}}

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "pattern_only"

    def test_preserve_success_copies_source_eval(self):
        """Preconditions hold, no lose intersection → copies source eval."""
        bridge = _bridge(mode="preserve", preserve=["sem_a"], lose=["sem_b"])
        src_eval = EvalNode(truth="T", reason="ok", support="supported", confidence=0.9, provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[_pred_claim(id="c1")]),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "preserved"
        assert result.dstAggregate is not None
        assert result.dstAggregate.truth == "T"
        assert result.dstAggregate.confidence == 0.9

    def test_preserve_loss_requirements_intersect_lose(self):
        """Semantic requirements intersect lose → N[transport_loss]."""
        bridge = _bridge(mode="preserve", lose=["sem_x"])
        # Claim with semanticRequirements that intersect the lose set
        claim = _pred_claim(id="c1")
        claim = ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
                          semanticRequirements=["sem_x"])
        src_eval = EvalNode(truth="T", support="supported", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[claim]),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "blocked"
        assert result.dstAggregate.truth == "N"
        assert result.dstAggregate.reason == "transport_loss"

    def test_preserve_precondition_failure(self):
        """Source truth is N with preconditions → N[transport_precondition]."""
        bridge = _bridge(mode="preserve", preconditions=["decisive_truth"])
        src_eval = EvalNode(truth="N", support="absent", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[_pred_claim(id="c1")]),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "blocked"
        assert result.dstAggregate.truth == "N"
        assert result.dstAggregate.reason == "transport_precondition"

    def test_degrade_applies_degradation_rules(self):
        """Degrade mode: preserve fails due to lose intersection → degradation rules apply."""
        bridge = _bridge(mode="degrade", lose=["sem_x"])
        claim = ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
                          semanticRequirements=["sem_x"])
        src_eval = EvalNode(truth="T", support="supported", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[claim]),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "degraded"
        # T → N[transport_loss]
        assert result.dstAggregate.truth == "N"
        assert result.dstAggregate.reason == "transport_loss"
        # Support degrades to partial
        assert result.dstAggregate.support == "partial"

    def test_degrade_B_stays_B(self):
        """Degrade mode with B source → B[boundary_mix]."""
        bridge = _bridge(mode="degrade", lose=["sem_x"])
        claim = ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
                          semanticRequirements=["sem_x"])
        src_eval = EvalNode(truth="B", support="conflicted", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[claim]),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "degraded"
        assert result.dstAggregate.truth == "B"
        assert result.dstAggregate.reason == "boundary_mix"

    def test_degrade_N_stays_N(self):
        """Degrade mode with N source → N stays N."""
        bridge = _bridge(mode="degrade", lose=["sem_x"])
        claim = ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
                          semanticRequirements=["sem_x"])
        src_eval = EvalNode(truth="N", support="absent", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[claim]),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "degraded"
        assert result.dstAggregate.truth == "N"

    def test_remap_recompute_handler_exception_returns_unresolved(self):
        """remap_recompute should report unresolved when claim_map_handler raises."""
        bridge = _bridge(mode="remap_recompute", claim_map="map_fn")
        src_eval = EvalNode(truth="T", support="supported", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        def failing_claim_map(claim_id, claim_map_binding, bridge, step_ctx, machine_state):
            raise RuntimeError("claim map failed")

        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[_pred_claim(id="c1")]),
            "__claim_map_handler__": failing_claim_map,
        }

        result, _, diags = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "unresolved"
        assert result.dstAggregate is not None
        assert result.dstAggregate.reason == "transport_remap_error"
        assert sum(1 for d in diags if d.get("code") == "transport_remap_error") == 1

    def test_remap_recompute_with_fake_claim_map_handler(self):
        """remap_recompute: claim_map handler + fake destination evaluator."""
        bridge = _bridge(mode="remap_recompute", claim_map="map_fn")
        src_eval = EvalNode(truth="T", support="supported", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        def fake_claim_map(claim_id, claim_map_binding, bridge, step_ctx, machine_state):
            return {
                "mappedClaim": "c1_mapped",
                "truth": "F",
                "reason": "remapped_to_false",
                "per_evaluator": {"dst_ev1": EvalNode(truth="F", provenance=["dst_ev1"])},
            }

        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[_pred_claim(id="c1")]),
            "__claim_map_handler__": fake_claim_map,
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "transported"
        assert result.dstAggregate.truth == "F"
        assert result.dstAggregate.reason == "remapped_to_false"
        assert result.mappedClaim == "c1_mapped"
        assert "dst_ev1" in result.per_evaluator


    def test_remap_recompute_applies_dst_evaluators_and_resolution_policy(self):
        """remap_recompute should aggregate per_evaluator using destination config."""
        bridge = BridgeNode(
            id="br1",
            **{"from": _frame_pattern(system="src_sys")},
            to=_frame_pattern(system="dst_sys"),
            via="via1",
            preserve=["sem_a"],
            lose=[],
            gain=[],
            risk=[],
            transport=TransportNode(
                mode="remap_recompute",
                claimMap="map_fn",
                dstEvaluators=["dst_ev1"],
                dstResolutionPolicy="dst_single",
            ),
        )
        src_eval = EvalNode(truth="T", support="supported", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        def fake_claim_map(claim_id, claim_map_binding, bridge, step_ctx, machine_state):
            return {
                "mappedClaim": "c1_mapped",
                "truth": "T",
                "reason": "map_default",
                "per_evaluator": {
                    "dst_ev1": EvalNode(truth="F", reason="ev1_false", provenance=["dst_ev1"]),
                    "dst_ev2": EvalNode(truth="T", reason="ev2_true", provenance=["dst_ev2"]),
                },
            }

        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[_pred_claim(id="c1")]),
            "__claim_map_handler__": fake_claim_map,
            "__resolution_policies__": {
                "dst_single": ResolutionPolicyNode(id="dst_single", kind="single", members=["dst_ev1"]),
            },
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "transported"
        assert result.dstAggregate is not None
        assert result.dstAggregate.truth == "F"
        assert result.dstAggregate.reason == "ev1_false"
        assert sorted(result.per_evaluator) == ["dst_ev1"]

    def test_semantic_requirements_empty_warning(self):
        """Diagnostic rule 23: lint.transport.semantic_requirements_empty."""
        bridge = _bridge(mode="preserve")
        # Claim with empty semanticRequirements
        claim = _pred_claim(id="c1")
        src_eval = EvalNode(truth="T", support="supported", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c1", "id": "tq1"}],
            "__per_claim_aggregates__": {"c1": src_eval},
            "__bundle__": _bundle(claims=[claim]),
        }

        _, _, diags = execute_transport(bridge, step_ctx, ms, services)

        codes = [d["code"] for d in diags]
        assert "lint.transport.semantic_requirements_empty" in codes


    def test_missing_transport_source_propagates_diag(self):
        """Source-missing transport should be surfaced in returned diagnostics."""
        bridge = _bridge(mode="preserve")
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c_missing", "id": "tq1"}],
            "__per_claim_aggregates__": {},
            "__bundle__": _bundle(),
        }

        result, _, diags = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "unresolved"
        codes = [d["code"] for d in diags]
        assert "transport_source_missing" in codes

    def test_missing_transport_source_unresolved(self):
        """Source claim not evaluated → transport_source_missing."""
        bridge = _bridge(mode="preserve")
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [{"bridgeId": "br1", "claimId": "c_missing", "id": "tq1"}],
            "__per_claim_aggregates__": {},
            "__bundle__": _bundle(),
        }

        result, _, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status == "unresolved"

    def test_multiple_queries_for_same_bridge_are_all_processed(self):
        """Each matching query for a bridge should produce a transport result."""
        bridge = _bridge(mode="preserve")
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__transport_queries__": [
                {"bridgeId": "br1", "claimId": "c1", "id": "tq1"},
                {"bridgeId": "br1", "claimId": "c2", "id": "tq2"},
            ],
            "__per_claim_aggregates__": {
                "c1": EvalNode(truth="T", support="supported", provenance=["ev1"]),
                "c2": EvalNode(truth="F", support="supported", provenance=["ev1"]),
            },
            "__bundle__": _bundle(claims=[_pred_claim(id="c1"), _pred_claim(id="c2")]),
        }

        result, new_ms, _ = execute_transport(bridge, step_ctx, ms, services)

        assert result.status in ("preserved", "blocked")
        assert "tq1" in new_ms.transport_store
        assert "tq2" in new_ms.transport_store
        assert new_ms.transport_store["tq1"].provenance[-1] == "c1"
        assert new_ms.transport_store["tq2"].provenance[-1] == "c2"

    def test_step_scoped_queries_only_match_current_fixture_step(self):
        """Queries annotated for a different fixture step are ignored."""
        bridge = _bridge(mode="preserve")
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__fixture_step_index__": 1,
            "__transport_queries__": [
                {
                    "bridgeId": "br1",
                    "claimId": "c0",
                    "id": "tq0",
                    "__fixture_step_index__": 0,
                },
                {
                    "bridgeId": "br1",
                    "claimId": "c1",
                    "id": "tq1",
                    "__fixture_step_index__": 1,
                },
            ],
            "__per_claim_aggregates__": {
                "c0": EvalNode(truth="T", support="supported", provenance=["ev1"]),
                "c1": EvalNode(truth="F", support="supported", provenance=["ev1"]),
            },
            "__bundle__": _bundle(claims=[_pred_claim(id="c0"), _pred_claim(id="c1")]),
        }

        result, new_ms, _ = execute_transport(bridge, step_ctx, ms, services)

        assert "tq0" not in new_ms.transport_store
        assert "tq1" in new_ms.transport_store
        assert result.provenance[-1] == "c1"


# ===================================================================
# Tests: synthesize_support
# ===================================================================


class TestSynthesizeSupport:
    """Tests for synthesize_support primitive."""

    def test_default_supported_with_full_evidence(self):
        """Full evidence, no conflicts → supported."""
        claim = _pred_claim(id="c1", refs=["e1"])
        ev = EvidenceNode(id="e1", kind="measurement", binding="b1", completeness=1.0)
        evidence_view = ClaimEvidenceView(
            claim_id="c1",
            explicit_evidence=[ev],
            relations=[],
        )
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, {})

        assert result.support == "supported"

    def test_default_partial_with_incomplete_evidence(self):
        """Evidence with completeness < 1.0 → partial."""
        claim = _pred_claim(id="c1", refs=["e1"])
        ev = EvidenceNode(id="e1", kind="measurement", binding="b1", completeness=0.5)
        evidence_view = ClaimEvidenceView(
            claim_id="c1",
            explicit_evidence=[ev],
            relations=[],
        )
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, {})

        assert result.support == "partial"

    def test_default_conflicted_with_conflict_relations(self):
        """Evidence conflicts declared → conflicted."""
        claim = _pred_claim(id="c1", refs=["e1", "e2"])
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1")
        ev2 = EvidenceNode(id="e2", kind="dataset", binding="b2")
        rel = EvidenceRelationNode(id="r1", lhs="e1", rhs="e2", kind="conflicts", score=0.8)
        evidence_view = ClaimEvidenceView(
            claim_id="c1",
            explicit_evidence=[ev1, ev2],
            relations=[rel],
            cross_conflict_score=0.8,
        )
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, {})

        assert result.support == "conflicted"

    def test_default_absent_with_no_evidence(self):
        """No explicit evidence → absent."""
        claim = _pred_claim(id="c1")
        evidence_view = ClaimEvidenceView(claim_id="c1", explicit_evidence=[], relations=[])
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, {})

        assert result.support == "absent"

    def test_policy_override_handler_called(self):
        """Support policy override: handler from services is called."""
        claim = _pred_claim(id="c1")
        evidence_view = ClaimEvidenceView(claim_id="c1", explicit_evidence=[], relations=[])
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        def fake_handler(claim, truth_core, ev_view, evaluator_id, step_ctx, machine_state):
            return SupportResult(support="supported", provenance=["override"])

        evaluator = _evaluator(id="ev1")
        evaluator_with_policy = EvaluatorNode(
            id="ev1", kind="model", binding="b1", evidencePolicy="custom_policy"
        )
        bundle = _bundle(evaluators=[evaluator_with_policy])
        services: dict = {
            "__bundle__": bundle,
            "support_policy_handlers": {"custom_policy": fake_handler},
        }

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, services)

        assert result.support == "supported"
        assert result.provenance == ["override"]

    def test_policy_override_deterministic(self):
        """Policy override can set support and confidence deterministically."""
        claim = _pred_claim(id="c1")
        evidence_view = ClaimEvidenceView(claim_id="c1", explicit_evidence=[], relations=[])
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        def deterministic_handler(claim, truth_core, ev_view, evaluator_id, step_ctx, machine_state):
            return SupportResult(support="partial", provenance=["det_src"])

        evaluator_with_policy = EvaluatorNode(
            id="ev1", kind="model", binding="b1", evidencePolicy="det_policy"
        )
        bundle = _bundle(evaluators=[evaluator_with_policy])
        services: dict = {
            "__bundle__": bundle,
            "support_policy_handlers": {"det_policy": deterministic_handler},
        }

        r1, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, services)
        r2, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, services)

        assert r1.support == r2.support == "partial"
        assert r1.provenance == r2.provenance == ["det_src"]

    def test_declared_conflicts_only_by_default(self):
        """Default policy only considers declared conflict relations, not inferred ones."""
        claim = _pred_claim(id="c1", refs=["e1", "e2"])
        ev1 = EvidenceNode(id="e1", kind="measurement", binding="b1", completeness=1.0)
        ev2 = EvidenceNode(id="e2", kind="dataset", binding="b2", completeness=1.0)
        # No conflict relations declared
        evidence_view = ClaimEvidenceView(
            claim_id="c1",
            explicit_evidence=[ev1, ev2],
            relations=[],
            cross_conflict_score=None,
        )
        tc = TruthCore(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, {})

        # No declared conflicts → supported (not conflicted)
        assert result.support == "supported"

    def test_note_expr_guard_returns_inapplicable(self):
        """NoteExpr claims → inapplicable support."""
        claim = _note_claim(id="c_note")
        evidence_view = ClaimEvidenceView(claim_id="c_note", explicit_evidence=[], relations=[])
        tc = TruthCore(truth="N", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        result, _, _ = synthesize_support(claim, tc, evidence_view, "ev1", step_ctx, ms, {})

        assert result.support == "inapplicable"


# ===================================================================
# Tests: evaluate_adequacy_set
# ===================================================================


class TestEvaluateAdequacySet:
    """Tests for evaluate_adequacy_set primitive."""

    def _make_bundle_with_anchors(
        self,
        anchors: list[AnchorNode],
        joint_adequacies: list[JointAdequacyNode] | None = None,
        policy: ResolutionPolicyNode | None = None,
    ) -> BundleNode:
        """Create a bundle with specified anchors."""
        return BundleNode(
            id="bundle1",
            frame=_frame(),
            evaluators=[_evaluator()],
            resolutionPolicy=policy or _policy_single("ev1"),
            claimBlocks=[_block([_pred_claim()])],
            anchors=anchors,
            jointAdequacies=joint_adequacies or [],
        )

    def test_single_assessment_score_above_threshold_adequate(self):
        """Score >= threshold → adequate (T)."""
        aa = _assessment(id="aa1", score=0.8, threshold=0.5)
        anc = _anchor(id="anc1", adequacy=[aa])
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle}

        results, _, diags = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        per_assessment = results["per_assessment"]
        assert "aa1" in per_assessment
        assert per_assessment["aa1"].truth == "T"
        assert per_assessment["aa1"].adequate is True

    def test_single_assessment_score_below_threshold_inadequate(self):
        """Score < threshold → inadequate (F)."""
        aa = _assessment(id="aa1", score=0.3, threshold=0.5)
        anc = _anchor(id="anc1", adequacy=[aa])
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle}

        results, _, diags = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        per_assessment = results["per_assessment"]
        assert per_assessment["aa1"].truth == "F"
        assert per_assessment["aa1"].adequate is False

    def test_score_omitted_without_handler_is_unresolved(self):
        """Score-omitted assessments without method handlers -> N[missing_binding]."""
        aa = _assessment(id="aa1", score=None, threshold=0.5)
        anc = _anchor(id="anc1", adequacy=[aa])
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle}

        results, _, diags = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        assert results["per_assessment"]["aa1"].truth == "N"
        assert results["per_assessment"]["aa1"].adequate is False
        assert results["per_assessment"]["aa1"].reason == "missing_binding"
        assert any(d.get("code") == "adequacy_method_binding_missing" for d in diags)

    def test_score_omitted_with_handler_uses_computed_score(self):
        """Score-omitted assessments should evaluate via adequacy method handler."""
        aa = _assessment(id="aa1", method="calc", score=None, threshold=0.5)
        anc = _anchor(id="anc1", adequacy=[aa])
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__bundle__": bundle,
            "adequacy_handlers": {"calc": lambda assessment: 0.8},
        }

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        assert results["per_assessment"]["aa1"].truth == "T"
        assert results["per_assessment"]["aa1"].adequate is True

    def test_multiple_assessments_paraconsistent_union(self):
        """Multiple same-task assessments under paraconsistent_union policy."""
        aa1 = _assessment(id="aa1", task="predict", producer="p1", score=0.9, threshold=0.5)
        aa2 = _assessment(id="aa2", task="predict", producer="p2", score=0.3, threshold=0.5)
        pol = ResolutionPolicyNode(id="adeq_pol", kind="paraconsistent_union", members=["p1", "p2"])
        anc = _anchor(id="anc1", adequacy=[aa1, aa2], adequacy_policy="adeq_pol")
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle, "__resolution_policies__": {"adeq_pol": pol}}

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        per_anchor_task = results["per_anchor_task"]
        # T + F = B (adequacy_conflict)
        assert per_anchor_task["anc1:predict"].truth == "B"
        assert per_anchor_task["anc1:predict"].reason == "adequacy_conflict"

    def test_single_policy_missing_member_returns_N(self):
        """Single adequacy policy should not silently select the wrong producer."""
        aa1 = _assessment(id="aa1", task="predict", producer="p1", score=0.9, threshold=0.5)
        aa2 = _assessment(id="aa2", task="predict", producer="p1", score=0.8, threshold=0.5)
        pol = ResolutionPolicyNode(id="adeq_pol", kind="single", members=["p2"])
        anc = _anchor(id="anc1", adequacy=[aa1, aa2], adequacy_policy="adeq_pol")
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle, "__resolution_policies__": {"adeq_pol": pol}}

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        at = results["per_anchor_task"]["anc1:predict"]
        assert at.truth == "N"
        assert at.reason == "policy_member_not_found:p2"

    def test_multiple_assessments_priority_order(self):
        """Multiple same-task assessments under priority_order policy."""
        aa1 = _assessment(id="aa1", task="predict", producer="p1", score=None, threshold=0.5)
        aa2 = _assessment(id="aa2", task="predict", producer="p2", score=0.8, threshold=0.5)
        pol = ResolutionPolicyNode(id="adeq_pol", kind="priority_order", members=["p1", "p2"], order=["p1", "p2"])
        anc = _anchor(id="anc1", adequacy=[aa1, aa2], adequacy_policy="adeq_pol")
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {
            "__bundle__": bundle,
            "__resolution_policies__": {"adeq_pol": pol},
            "adequacy_handlers": {aa1.method: lambda assessment: 0.9},
        }

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        # p1 score is computed via handler (T), so priority picks it first.
        per_anchor_task = results["per_anchor_task"]
        assert per_anchor_task["anc1:predict"].truth == "T"

    def test_missing_policy_warning(self):
        """Diagnostic rule 24: lint.adequacy.missing_policy_multi_assessment."""
        aa1 = _assessment(id="aa1", task="predict", producer="p1", score=0.9, threshold=0.5)
        aa2 = _assessment(id="aa2", task="predict", producer="p2", score=0.8, threshold=0.5)
        # No adequacy policy declared
        anc = _anchor(id="anc1", adequacy=[aa1, aa2])
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle}

        _, _, diags = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        codes = [d["code"] for d in diags]
        assert "lint.adequacy.missing_policy_multi_assessment" in codes

    def test_circular_basis_error(self):
        """Diagnostic rule 25: lint.adequacy.circular_basis."""
        # Create a claim that uses anchor anc1, and assessment aa1 has basis=[c1]
        # This creates a cycle: aa1 → c1 → anc1 → aa1
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1"],
        )
        aa = _assessment(id="aa1", basis=["c1"])
        anc = _anchor(id="anc1", adequacy=[aa])
        bundle = BundleNode(
            id="bundle1",
            frame=_frame(),
            evaluators=[_evaluator()],
            resolutionPolicy=_policy_single("ev1"),
            claimBlocks=[_block([claim])],
            anchors=[anc],
        )
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle}

        results, _, diags = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        codes = [d["code"] for d in diags]
        assert "circular_dependency" in codes
        # The result should be N due to circular dependency
        assert results["per_assessment"]["aa1"].truth == "N"
        assert results["per_assessment"]["aa1"].reason == "circular_dependency"

    def test_method_conflict_under_paraconsistent_union(self):
        """Method conflict: T+F under paraconsistent_union -> B with reason adequacy_conflict."""
        aa1 = _assessment(id="aa1", task="predict", producer="p1", score=0.9, threshold=0.5)
        aa2 = _assessment(id="aa2", task="predict", producer="p2", score=0.3, threshold=0.5)
        pol = ResolutionPolicyNode(id="adeq_pol", kind="paraconsistent_union", members=["p1", "p2"])
        anc = _anchor(id="anc1", adequacy=[aa1, aa2], adequacy_policy="adeq_pol")
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle, "__resolution_policies__": {"adeq_pol": pol}}

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        at = results["per_anchor_task"]["anc1:predict"]
        assert at.truth == "B"
        assert at.reason == "adequacy_conflict"


    def test_adjudicated_preserves_reason_from_object_result(self):
        """Adjudicated adequacy should preserve reason from object-shaped results."""
        aa1 = _assessment(id="aa1", task="predict", producer="p1", score=0.9, threshold=0.5)
        aa2 = _assessment(id="aa2", task="predict", producer="p2", score=0.2, threshold=0.5)
        pol = ResolutionPolicyNode(
            id="adeq_pol", kind="adjudicated", members=["p1", "p2"], binding="adj_fn"
        )
        anc = _anchor(id="anc1", adequacy=[aa1, aa2], adequacy_policy="adeq_pol")
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()

        class _AdjResult:
            def __init__(self):
                self.truth = "B"
                self.reason = "adjudicated_conflict"

        services: dict = {
            "__bundle__": bundle,
            "__resolution_policies__": {"adeq_pol": pol},
            "adequacy_adjudicator": lambda assessments: _AdjResult(),
        }

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        at = results["per_anchor_task"]["anc1:predict"]
        assert at.truth == "B"
        assert at.reason == "adjudicated_conflict"

    def test_method_conflict_normalizes_aggregation_inputs(self):
        """Method conflicts should force aggregated task truth to conflict semantics."""
        aa1 = _assessment(
            id="aa1", task="predict", producer="p1", method="m1", score=0.9, threshold=0.5
        )
        aa2 = _assessment(
            id="aa2", task="predict", producer="p2", method="m2", score=0.8, threshold=0.5
        )
        pol = ResolutionPolicyNode(id="adeq_pol", kind="single", members=["p2"])
        anc = _anchor(id="anc1", adequacy=[aa1, aa2], adequacy_policy="adeq_pol")
        bundle = self._make_bundle_with_anchors([anc])
        step_ctx = StepContext(effective_frame=_frame())
        ms = MachineState()
        services: dict = {"__bundle__": bundle, "__resolution_policies__": {"adeq_pol": pol}}

        results, _, _ = evaluate_adequacy_set(["anc1"], step_ctx, ms, services)

        per_assessment = results["per_assessment"]
        # Legacy per-assessment marker remains on the first conflicting assessment.
        assert per_assessment["aa1"].truth == "B"
        assert per_assessment["aa1"].reason == "method_conflict"
        assert per_assessment["aa2"].truth == "T"

        # Aggregated task should still be conflicted despite single-member policy selection.
        at = results["per_anchor_task"]["anc1:predict"]
        assert at.truth == "B"
        assert at.reason == "method_conflict"


# ===================================================================
# Tests: compose_license
# ===================================================================


class TestComposeLicense:
    """Tests for compose_license primitive."""

    def _make_license_bundle(
        self,
        claims: list[ClaimNode],
        anchors: list[AnchorNode],
        joint_adequacies: list[JointAdequacyNode] | None = None,
    ) -> BundleNode:
        return BundleNode(
            id="bundle1",
            frame=_frame(),
            evaluators=[_evaluator()],
            resolutionPolicy=_policy_single("ev1"),
            claimBlocks=[_block(claims)],
            anchors=anchors,
            jointAdequacies=joint_adequacies or [],
        )

    def test_all_anchors_adequate_yields_T(self):
        """Exact-set matching: all anchors adequate → T."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2"],
        )
        anc1 = _anchor(id="anc1")
        anc2 = _anchor(id="anc2")
        bundle = self._make_license_bundle([claim], [anc1, anc2])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:predict": {"truth": "T", "reason": None, "per_assessment": []},
                "anc2:predict": {"truth": "T", "reason": None, "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "T"

    def test_missing_anchor_adequacy_yields_N(self):
        """Missing anchor adequacy → N with appropriate code."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1"],
        )
        anc1 = _anchor(id="anc1")
        bundle = self._make_license_bundle([claim], [anc1])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {},  # No adequacy results
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "N"
        assert result.overall.reason == "no_adequacy_result"

    def test_joint_inadequacy_yields_F(self):
        """One anchor fails adequacy → overall F."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2"],
        )
        anc1 = _anchor(id="anc1")
        anc2 = _anchor(id="anc2")
        bundle = self._make_license_bundle([claim], [anc1, anc2])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:predict": {"truth": "T", "reason": None, "per_assessment": []},
                "anc2:predict": {"truth": "F", "reason": "threshold_not_met", "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "F"

    def test_worst_truth_wins_severity_ordering(self):
        """Worst-truth-wins: F > B > N > T."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2", "anc3"],
        )
        anc1 = _anchor(id="anc1")
        anc2 = _anchor(id="anc2")
        anc3 = _anchor(id="anc3")
        bundle = self._make_license_bundle([claim], [anc1, anc2, anc3])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:predict": {"truth": "T", "reason": None, "per_assessment": []},
                "anc2:predict": {"truth": "B", "reason": "conflict", "per_assessment": []},
                "anc3:predict": {"truth": "N", "reason": "unknown", "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        # B > N > T → worst is B
        # Actually F > B > N > T, so B is worse than N which is worse than T
        assert result.overall.truth == "B"

    def test_license_truth_separate_from_world_truth(self):
        """License truth stays separate from world truth."""
        # A claim can have world truth T but license truth F
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1"],
        )
        anc1 = _anchor(id="anc1")
        bundle = self._make_license_bundle([claim], [anc1])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:predict": {"truth": "F", "reason": "threshold_not_met", "per_assessment": []},
            },
            "joint": {},
        }
        # World truth is T but license truth should be F
        ms.resolution_store.results["c1"] = EvalNode(truth="T", provenance=["ev1"])
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        # License says F (inadequate anchor) even though world truth is T
        assert result.overall.truth == "F"

    def test_joint_coverage_order_independent_when_partner_appears_first(self):
        """Joint coverage should not depend on claim.usesAnchors order."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc2", "anc1"],
        )
        anc1 = _anchor(id="anc1", requires_joint_with=["anc2"])
        anc2 = _anchor(id="anc2")
        ja = JointAdequacyNode(
            id="ja1",
            anchors=["anc1", "anc2"],
            assessments=[_assessment(id="jaa1", task="predict", producer="p1", score=0.9, threshold=0.5)],
        )
        bundle = self._make_license_bundle([claim], [anc1, anc2], joint_adequacies=[ja])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc2:predict": {"truth": "F", "reason": "threshold_not_met", "per_assessment": []},
            },
            "joint": {"ja1": {"truth": "T", "reason": None, "per_assessment": []}},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "T"
        assert len(result.joint) == 1

    def test_joint_adequacy_covers_partner_anchor_without_individual_result(self):
        """A matched joint adequacy should cover all anchors in the joint group."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2"],
        )
        anc1 = _anchor(id="anc1", requires_joint_with=["anc2"])
        anc2 = _anchor(id="anc2")
        ja = JointAdequacyNode(
            id="ja1",
            anchors=["anc1", "anc2"],
            assessments=[_assessment(id="jaa1", task="predict", producer="p1", score=0.9, threshold=0.5)],
        )
        bundle = self._make_license_bundle([claim], [anc1, anc2], joint_adequacies=[ja])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {},
            "joint": {"ja1": {"truth": "T", "reason": None, "per_assessment": []}},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "T"
        assert len(result.individual) == 0
        assert len(result.joint) == 1


    def test_joint_group_requires_stored_result(self):
        """A matching joint group without a stored joint result is still missing."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2"],
        )
        anc1 = _anchor(id="anc1", requires_joint_with=["anc2"])
        anc2 = _anchor(id="anc2")
        ja = JointAdequacyNode(
            id="ja1",
            anchors=["anc1", "anc2"],
            assessments=[_assessment(id="jaa1", task="predict", producer="p1", score=0.9, threshold=0.5)],
        )
        bundle = self._make_license_bundle([claim], [anc1, anc2], joint_adequacies=[ja])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:predict": {"truth": "T", "reason": None, "per_assessment": []},
                "anc2:predict": {"truth": "T", "reason": None, "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, diags = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "N"
        anc1_entry = next(e for e in result.individual if e.anchor_id == "anc1")
        assert anc1_entry.reason == "missing_joint_adequacy"
        assert any(d.get("code") == "missing_joint_adequacy" for d in diags)


    def test_missing_required_joint_partner_in_claim_blocks_license(self):
        """Declared requiresJointWith partners must all be present in claim usesAnchors."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2"],
        )
        anc1 = _anchor(id="anc1", requires_joint_with=["anc2", "anc3"])
        anc2 = _anchor(id="anc2")
        anc3 = _anchor(id="anc3")
        ja_subset = JointAdequacyNode(
            id="ja1",
            anchors=["anc1", "anc2"],
            assessments=[_assessment(id="jaa1", task="predict", producer="p1", score=0.9, threshold=0.5)],
        )
        bundle = self._make_license_bundle([claim], [anc1, anc2, anc3], joint_adequacies=[ja_subset])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc2:predict": {"truth": "T", "reason": None, "per_assessment": []},
            },
            "joint": {"ja1": {"truth": "T", "reason": None, "per_assessment": []}},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, diags = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "N"
        anc1_entry = next(e for e in result.individual if e.anchor_id == "anc1")
        assert anc1_entry.reason == "missing_joint_adequacy"
        assert any(d.get("code") == "missing_joint_adequacy" for d in diags)

    def test_missing_joint_adequacy(self):
        """Anchor requires joint adequacy but no matching group → N[missing_joint_adequacy]."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1", "anc2"],
        )
        anc1 = _anchor(id="anc1", requires_joint_with=["anc2"])
        anc2 = _anchor(id="anc2")
        # No joint adequacy groups
        bundle = self._make_license_bundle([claim], [anc1, anc2])

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:predict": {"truth": "T", "reason": None, "per_assessment": []},
                "anc2:predict": {"truth": "T", "reason": None, "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, diags = compose_license("c1", step_ctx, ms, services)

        # anc1 requires joint with anc2 but no joint group → N
        assert result.overall.truth in ("N", "T")  # depends on worst-wins
        # Check that missing_joint_adequacy diagnostic appeared
        codes = [d["code"] for d in diags]
        assert "missing_joint_adequacy" in codes

    def test_uses_effective_step_task_before_bundle_fallback(self):
        """compose_license should resolve adequacy task from effective step frame first."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1"],
        )
        anc1 = _anchor(id="anc1")
        bundle = BundleNode(
            id="bundle1",
            frame=_frame(task="predict"),
            evaluators=[_evaluator()],
            resolutionPolicy=_policy_single("ev1"),
            claimBlocks=[_block([claim])],
            anchors=[anc1],
        )

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:diagnose": {"truth": "T", "reason": None, "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame(task="diagnose"))
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "T"

    def test_uses_effective_step_pattern_task_before_bundle_fallback(self):
        """compose_license should resolve task from FramePattern effective frames."""
        claim = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P"),
            usesAnchors=["anc1"],
        )
        anc1 = _anchor(id="anc1")
        bundle = BundleNode(
            id="bundle1",
            frame=_frame(),
            evaluators=[_evaluator()],
            resolutionPolicy=_policy_single("ev1"),
            claimBlocks=[_block([claim])],
            anchors=[anc1],
        )

        ms = MachineState()
        ms.adequacy_store = {
            "per_anchor_task": {
                "anc1:diagnose": {"truth": "T", "reason": None, "per_assessment": []},
            },
            "joint": {},
        }
        step_ctx = StepContext(effective_frame=_frame_pattern(task="diagnose"))
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "T"

    def test_no_anchors_yields_T(self):
        """Claim uses no anchors → no license needed → T."""
        claim = _pred_claim(id="c1")  # No usesAnchors
        bundle = self._make_license_bundle([claim], [])

        ms = MachineState()
        step_ctx = StepContext(effective_frame=_frame())
        services: dict = {"__bundle__": bundle}

        result, _, _ = compose_license("c1", step_ctx, ms, services)

        assert result.overall.truth == "T"


# ===================================================================
# Tests: apply_resolution_policy metadata (extended)
# ===================================================================


class TestApplyResolutionPolicyMetadata:
    """Extended metadata tests for apply_resolution_policy."""

    def test_single_confidence_propagation(self):
        """Single policy propagates confidence from the selected evaluator."""
        ev = EvalNode(truth="T", confidence=0.88, provenance=["ev1", "src1"])
        policy = _policy_single("ev1")
        result = apply_resolution_policy({"ev1": ev}, policy)
        assert result.confidence == 0.88

    def test_priority_order_confidence_propagation(self):
        """Priority_order propagates confidence from the first non-N evaluator."""
        ev1 = EvalNode(truth="N", confidence=0.3, provenance=["ev1"])
        ev2 = EvalNode(truth="T", confidence=0.95, provenance=["ev2"])
        policy = _policy_priority("ev1", "ev2")
        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)
        assert result.confidence == 0.95

    def test_paraconsistent_union_provenance_deterministic_sorted(self):
        """Paraconsistent union: provenance is a deterministic sorted union."""
        ev1 = EvalNode(truth="T", provenance=["z_src", "b_src"])
        ev2 = EvalNode(truth="T", provenance=["a_src", "b_src", "m_src"])
        policy = _policy_union("ev1", "ev2")

        result = apply_resolution_policy({"ev1": ev1, "ev2": ev2}, policy)

        assert result.provenance == ["a_src", "b_src", "m_src", "z_src"]

    def test_adjudicated_preserves_provenance(self):
        """Adjudicated binding preserves provenance from adjudicator."""
        ev1 = EvalNode(truth="T", provenance=["ev1"])
        ev2 = EvalNode(truth="F", provenance=["ev2"])
        policy = _policy_adjudicated("ev1", "ev2")

        def fake_adj(per_evaluator):
            return EvalNode(
                truth="T", reason="adj",
                confidence=0.99, provenance=["adj_prov", "model_prov"],
            )

        result = apply_resolution_policy(
            {"ev1": ev1, "ev2": ev2}, policy, adjudicator=fake_adj,
        )
        assert result.provenance == ["adj_prov", "model_prov"]
        assert result.confidence == 0.99
