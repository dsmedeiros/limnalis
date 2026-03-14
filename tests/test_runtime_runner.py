"""Unit tests for the Limnalis step runner."""

from __future__ import annotations

import pytest

from limnalis.models.ast import (
    BundleNode,
    ClaimNode,
    ClaimBlockNode,
    EvaluatorNode,
    ResolutionPolicyNode,
    FrameNode,
    NoteExprNode,
    PredicateExprNode,
    TimeCtxNode,
)
from limnalis.runtime.models import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    MachineState,
    TruthCore,
    SupportResult,
    EvalNode,
    ClaimEvidenceView,
    StepContext,
)
from limnalis.runtime.runner import (
    run_step,
    run_session,
    run_bundle,
    PrimitiveSet,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame(**overrides):
    defaults = dict(system="sys", namespace="ns", scale="macro", task="predict", regime="standard")
    defaults.update(overrides)
    return FrameNode(**defaults)


def _bundle(claims=None, evaluators=None, policy=None):
    frame = _frame()
    evaluators = evaluators or [EvaluatorNode(id="ev1", kind="model", binding="b1")]
    policy = policy or ResolutionPolicyNode(id="pol", kind="single", members=["ev1"])
    claims = claims or [ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"))]
    return BundleNode(
        id="test_bundle",
        frame=frame,
        evaluators=evaluators,
        resolutionPolicy=policy,
        claimBlocks=[ClaimBlockNode(id="blk1", stratum="local", claims=claims)],
    )


def _env():
    return EvaluationEnvironment()


def _session(steps=None):
    steps = steps or [StepConfig(id="step1")]
    return SessionConfig(id="sess1", steps=steps)


def _step(id="step1"):
    return StepConfig(id=id)


# ---------------------------------------------------------------------------
# Phase trace order
# ---------------------------------------------------------------------------


EXPECTED_PRIMITIVES = [
    "resolve_ref",
    "build_step_context",
    "resolve_baseline",
    "evaluate_adequacy_set",
    "build_evidence_view",
    "classify_claim",
    "eval_expr",
    "synthesize_support",
    "assemble_eval",
    "apply_resolution_policy",
    "fold_block",
    "execute_transport",
]


class TestPhaseTraceOrder:
    """Verify the runner executes all 12 phases in order."""

    def test_trace_contains_all_12_phases(self):
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env())

        assert len(result.trace) == 12
        phases = [event.phase for event in result.trace]
        assert phases == list(range(1, 13))

    def test_trace_primitive_names_match(self):
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env())

        primitive_names = [event.primitive for event in result.trace]
        assert primitive_names == EXPECTED_PRIMITIVES

    def test_trace_phases_are_monotonically_increasing(self):
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env())

        phases = [event.phase for event in result.trace]
        for i in range(1, len(phases)):
            assert phases[i] > phases[i - 1]


# ---------------------------------------------------------------------------
# Non-evaluable NoteExpr claims bypass
# ---------------------------------------------------------------------------


class TestNoteExprBypass:
    """Verify NoteExpr claims are classified as non-evaluable and get N truth."""

    def test_note_expr_classified_non_evaluable(self):
        note_claim = ClaimNode(id="note1", kind="note", expr=NoteExprNode(text="just a note"))
        pred_claim = ClaimNode(id="pred1", kind="atomic", expr=PredicateExprNode(name="P"))
        bundle = _bundle(claims=[note_claim, pred_claim])

        result = run_step(bundle, _session(), _step(), _env())

        assert "note1" in result.per_claim_classifications
        assert result.per_claim_classifications["note1"].evaluable is False

    def test_predicate_expr_classified_evaluable(self):
        note_claim = ClaimNode(id="note1", kind="note", expr=NoteExprNode(text="just a note"))
        pred_claim = ClaimNode(id="pred1", kind="atomic", expr=PredicateExprNode(name="P"))
        bundle = _bundle(claims=[note_claim, pred_claim])

        result = run_step(bundle, _session(), _step(), _env())

        assert "pred1" in result.per_claim_classifications
        assert result.per_claim_classifications["pred1"].evaluable is True

    def test_note_expr_gets_n_truth_with_reason(self):
        note_claim = ClaimNode(id="note1", kind="note", expr=NoteExprNode(text="just a note"))
        pred_claim = ClaimNode(id="pred1", kind="atomic", expr=PredicateExprNode(name="P"))
        bundle = _bundle(claims=[note_claim, pred_claim])

        result = run_step(bundle, _session(), _step(), _env())

        assert "note1" in result.per_claim_per_evaluator
        eval_node = result.per_claim_per_evaluator["note1"]["ev1"]
        assert eval_node.truth == "N"
        assert eval_node.reason == "non_evaluable_note"

    def test_note_expr_support_is_inapplicable(self):
        note_claim = ClaimNode(id="note1", kind="note", expr=NoteExprNode(text="just a note"))
        bundle = _bundle(claims=[note_claim])

        result = run_step(bundle, _session(), _step(), _env())

        eval_node = result.per_claim_per_evaluator["note1"]["ev1"]
        assert eval_node.support == "inapplicable"


# ---------------------------------------------------------------------------
# Custom injected primitives
# ---------------------------------------------------------------------------


class TestCustomInjectedPrimitives:
    """Verify that custom primitives injected via PrimitiveSet flow through."""

    def test_custom_eval_expr_returns_t(self):
        def custom_eval_expr(claim, evaluator_id, step_ctx, machine_state, services):
            return TruthCore(truth="T", reason="custom_true"), machine_state, []

        primitives = PrimitiveSet(eval_expr=custom_eval_expr)
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env(), primitives=primitives)

        # The evaluable claim c1 should have truth T from our custom primitive
        eval_node = result.per_claim_per_evaluator["c1"]["ev1"]
        assert eval_node.truth == "T"
        assert eval_node.reason == "custom_true"

    def test_custom_synthesize_support_returns_supported(self):
        def custom_eval_expr(claim, evaluator_id, step_ctx, machine_state, services):
            return TruthCore(truth="T", reason="custom"), machine_state, []

        def custom_synthesize_support(
            claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state, services
        ):
            return SupportResult(support="supported"), machine_state, []

        primitives = PrimitiveSet(
            eval_expr=custom_eval_expr,
            synthesize_support=custom_synthesize_support,
        )
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env(), primitives=primitives)

        eval_node = result.per_claim_per_evaluator["c1"]["ev1"]
        assert eval_node.truth == "T"
        assert eval_node.support == "supported"

    def test_custom_primitives_flow_to_aggregates(self):
        def custom_eval_expr(claim, evaluator_id, step_ctx, machine_state, services):
            return TruthCore(truth="T", reason="custom"), machine_state, []

        def custom_synthesize_support(
            claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state, services
        ):
            return SupportResult(support="supported"), machine_state, []

        primitives = PrimitiveSet(
            eval_expr=custom_eval_expr,
            synthesize_support=custom_synthesize_support,
        )
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env(), primitives=primitives)

        # Resolution policy (single with ev1) should propagate T through
        assert "c1" in result.per_claim_aggregates
        assert result.per_claim_aggregates["c1"].truth == "T"

    def test_custom_eval_expr_trace_shows_ok(self):
        def custom_eval_expr(claim, evaluator_id, step_ctx, machine_state, services):
            return TruthCore(truth="T"), machine_state, []

        primitives = PrimitiveSet(eval_expr=custom_eval_expr)
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env(), primitives=primitives)

        # Phase 7 (eval_expr) should show "ok" since our custom primitive succeeded
        eval_expr_trace = [t for t in result.trace if t.primitive == "eval_expr"][0]
        assert eval_expr_trace.result_summary == "ok"


# ---------------------------------------------------------------------------
# run_session and run_bundle
# ---------------------------------------------------------------------------


class TestRunSession:
    """Verify run_session executes all steps and returns SessionResult."""

    def test_run_session_executes_all_steps(self):
        steps = [StepConfig(id="s1"), StepConfig(id="s2"), StepConfig(id="s3")]
        session = SessionConfig(id="sess1", steps=steps)
        bundle = _bundle()

        result = run_session(bundle, session, _env())

        assert result.session_id == "sess1"
        assert len(result.step_results) == 3
        assert [sr.step_id for sr in result.step_results] == ["s1", "s2", "s3"]

    def test_run_session_each_step_has_full_trace(self):
        steps = [StepConfig(id="s1"), StepConfig(id="s2")]
        session = SessionConfig(id="sess1", steps=steps)
        bundle = _bundle()

        result = run_session(bundle, session, _env())

        for step_result in result.step_results:
            assert len(step_result.trace) == 12

    def test_run_session_empty_steps_produces_diagnostic(self):
        session = SessionConfig(id="sess_empty", steps=[])
        bundle = _bundle()

        result = run_session(bundle, session, _env())

        assert result.session_id == "sess_empty"
        assert len(result.step_results) == 0
        assert any(d["code"] == "empty_session" for d in result.diagnostics)


class TestRunBundle:
    """Verify run_bundle executes all sessions."""

    def test_run_bundle_executes_all_sessions(self):
        s1 = SessionConfig(id="sess1", steps=[StepConfig(id="s1")])
        s2 = SessionConfig(id="sess2", steps=[StepConfig(id="s2")])
        bundle = _bundle()

        result = run_bundle(bundle, [s1, s2], _env())

        assert result.bundle_id == "test_bundle"
        assert len(result.session_results) == 2
        assert [sr.session_id for sr in result.session_results] == ["sess1", "sess2"]

    def test_run_bundle_no_sessions_produces_diagnostic(self):
        bundle = _bundle()

        result = run_bundle(bundle, [], _env())

        assert result.bundle_id == "test_bundle"
        assert len(result.session_results) == 0
        assert any(d["code"] == "no_sessions" for d in result.diagnostics)

    def test_run_bundle_nested_step_results(self):
        s1 = SessionConfig(id="sess1", steps=[StepConfig(id="s1"), StepConfig(id="s2")])
        bundle = _bundle()

        result = run_bundle(bundle, [s1], _env())

        assert len(result.session_results) == 1
        assert len(result.session_results[0].step_results) == 2
