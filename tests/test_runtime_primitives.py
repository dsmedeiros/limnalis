"""Comprehensive unit tests for the 6 implemented runtime primitives."""

from __future__ import annotations

import pytest

from limnalis.models.ast import (
    BundleNode,
    ClaimNode,
    ClaimBlockNode,
    EvaluatorNode,
    ResolutionPolicyNode,
    FrameNode,
    FramePatternNode,
    FacetValueMap,
    TimeCtxNode,
    NoteExprNode,
    PredicateExprNode,
    LogicalExprNode,
    EvidenceNode,
    EvidenceRelationNode,
)
from limnalis.runtime.models import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    StepContext,
    MachineState,
    TruthCore,
    SupportResult,
    EvalNode,
    ClaimClassification,
)
from limnalis.runtime.builtins import (
    build_step_context,
    classify_claim,
    build_evidence_view,
    assemble_eval,
    apply_resolution_policy,
    fold_block,
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

    def test_union_support_inapplicable_when_all_inapplicable(self):
        """All evaluators inapplicable => inapplicable."""
        ev1 = EvalNode(truth="T", support="inapplicable", provenance=["ev1"])
        ev2 = EvalNode(truth="T", support="inapplicable", provenance=["ev2"])
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
