"""Unit tests for the Limnalis step runner."""

from __future__ import annotations

import pytest

from limnalis.models.ast import (
    BaselineNode,
    BaselineRefTermNode,
    BridgeNode,
    BundleNode,
    ClaimNode,
    ClaimBlockNode,
    CriterionRefNode,
    EvaluatorNode,
    FramePatternNode,
    JudgedExprNode,
    ListTermNode,
    LogicalExprNode,
    ResolutionPolicyNode,
    FrameNode,
    NoteExprNode,
    PredicateExprNode,
    SymbolTermNode,
    TimeCtxNode,
    TransportNode,
)
from limnalis.runtime.builtins import (
    _collect_baseline_refs,
    materialize_referenced_baselines,
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


def _bundle(claims=None, evaluators=None, policy=None, bridges=None):
    frame = _frame()
    evaluators = evaluators or [EvaluatorNode(id="ev1", kind="model", binding="b1")]
    policy = policy or ResolutionPolicyNode(id="pol", kind="single", members=["ev1"])
    claims = claims or [ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"))]
    return BundleNode(
        id="test_bundle",
        frame=frame,
        evaluators=evaluators,
        resolutionPolicy=policy,
        bridges=bridges or [],
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
    "build_step_context",
    "resolve_ref",
    "resolve_baseline",
    "evaluate_adequacy_set",
    "compose_license",
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
    """Verify the runner executes all 13 phases in order."""

    def test_trace_contains_all_13_phases(self):
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env())

        assert len(result.trace) == 13
        phases = [event.phase for event in result.trace]
        assert phases == list(range(1, 14))

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

    def test_note_expr_receives_license_result(self):
        note_claim = ClaimNode(id="note1", kind="note", expr=NoteExprNode(text="just a note"))
        bundle = _bundle(claims=[note_claim])

        result = run_step(bundle, _session(), _step(), _env())

        assert "note1" in result.per_claim_licenses
        assert result.per_claim_licenses["note1"].overall.truth == "T"
        claim_result = next(cr for cr in result.claim_results if cr.claim_id == "note1")
        assert claim_result.license is not None
        assert claim_result.license.overall.truth == "T"


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


class TestServiceAdjudicatorWiring:
    """Verify services['adjudicator'] is used when no explicit adjudicator is passed."""

    def test_run_step_uses_services_adjudicator_for_adjudicated_policy(self):
        bundle = _bundle(
            policy=ResolutionPolicyNode(
                id="pol",
                kind="adjudicated",
                members=["ev1"],
                binding="test://adjudicator/service",
            )
        )

        def service_adjudicator(per_evaluator):
            return EvalNode(truth="T", reason="from_service", provenance=["service_adj"])

        result = run_step(
            bundle,
            _session(),
            _step(),
            _env(),
            services={"adjudicator": service_adjudicator},
        )

        assert result.per_claim_aggregates["c1"].truth == "T"
        assert result.per_claim_aggregates["c1"].reason == "from_service"


# ---------------------------------------------------------------------------
# Fold block fallback
# ---------------------------------------------------------------------------


class TestFoldBlockFallback:
    """Verify phase 11 writes fallback entries when fold_block raises."""

    def test_fold_block_error_produces_fallback_aggregate(self):
        def failing_fold_block(block, per_claim_agg, per_claim_per_ev, classifications, policy, adjudicator=None):
            raise RuntimeError("simulated fold failure")

        primitives = PrimitiveSet(fold_block=failing_fold_block)
        bundle = _bundle()
        result = run_step(bundle, _session(), _step(), _env(), primitives=primitives)

        # Block should still appear in aggregates with fallback N truth
        assert "blk1" in result.per_block_aggregates
        assert result.per_block_aggregates["blk1"].truth == "N"
        assert "fold_error" in result.per_block_aggregates["blk1"].reason

        # Per-evaluator should have empty dict fallback
        assert "blk1" in result.per_block_per_evaluator
        assert result.per_block_per_evaluator["blk1"] == {}

        # Diagnostic should be recorded
        fold_diags = [d for d in result.diagnostics if d.get("primitive") == "fold_block"]
        assert len(fold_diags) == 1
        assert fold_diags[0]["severity"] == "error"


class TestTransportErrorIsolation:
    """Verify phase 13 isolates errors per bridge."""

    @staticmethod
    def _bridge(bridge_id: str) -> BridgeNode:
        fp = FramePatternNode(
            facets={
                "system": "sys",
                "namespace": "ns",
                "scale": "macro",
                "task": "predict",
                "regime": "standard",
            }
        )
        return BridgeNode(
            id=bridge_id,
            from_=fp,
            to=fp,
            via="test",
            preserve=[],
            lose=[],
            transport=TransportNode(mode="metadata_only"),
        )

    def test_transport_continues_after_per_bridge_error(self):
        def flaky_execute_transport(bridge, step_ctx, machine_state, services):
            if bridge.id == "b1":
                raise RuntimeError("boom")
            return {"status": "transported"}, machine_state, []

        bundle = _bundle(bridges=[self._bridge("b1"), self._bridge("b2")])
        primitives = PrimitiveSet(execute_transport=flaky_execute_transport)

        result = run_step(bundle, _session(), _step(), _env(), primitives=primitives)

        phase_errors = [
            d for d in result.diagnostics
            if d.get("code") == "phase_error" and d.get("primitive") == "execute_transport"
        ]
        assert len(phase_errors) == 1
        assert phase_errors[0].get("bridge_id") == "b1"
        assert result.transport_results["b2"].status == "transported"

        transport_trace = [t for t in result.trace if t.primitive == "execute_transport"][0]
        assert transport_trace.result_summary.startswith("ok")


# ---------------------------------------------------------------------------
# run_session and run_bundle
# ---------------------------------------------------------------------------


class TestServicesBundleIsolation:
    """Verify run_step always injects the current bundle into services."""

    def test_run_step_overwrites_bundle_in_reused_services(self):
        shared_services: dict = {}

        bundle1 = _bundle(claims=[ClaimNode(id="c1", kind="atomic", expr=PredicateExprNode(name="P"))])
        run_step(bundle1, _session(), _step("s1"), _env(), services=shared_services)
        assert shared_services.get("__bundle__") is bundle1

        bundle2 = _bundle(claims=[ClaimNode(id="c2", kind="atomic", expr=PredicateExprNode(name="Q"))])
        run_step(bundle2, _session(), _step("s2"), _env(), services=shared_services)

        assert shared_services.get("__bundle__") is bundle2

class TestFixtureStepIndexService:
    """Verify run_step exposes a monotonic fixture step index in services."""

    def test_run_step_increments_fixture_step_index_on_reused_services(self):
        shared_services: dict = {}
        bundle = _bundle()
        session = _session()

        run_step(bundle, session, _step("s1"), _env(), services=shared_services)
        assert shared_services.get("__fixture_step_index__") == 0
        assert shared_services.get("__fixture_step_counter__") == 1

        run_step(bundle, session, _step("s2"), _env(), services=shared_services)
        assert shared_services.get("__fixture_step_index__") == 1
        assert shared_services.get("__fixture_step_counter__") == 2


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
            assert len(step_result.trace) == 13

    def test_run_session_empty_steps_produces_diagnostic(self):
        session = SessionConfig(id="sess_empty", steps=[])
        bundle = _bundle()

        result = run_session(bundle, session, _env())

        assert result.session_id == "sess_empty"
        assert len(result.step_results) == 0
        assert any(d["code"] == "empty_session" for d in result.diagnostics)



    def test_run_session_serializes_plain_dict_baseline_state(self):
        bundle = _bundle()
        session = SessionConfig(id="sess1", steps=[StepConfig(id="s1")])

        def baseline_dict_injector(claim, ev_id, step_ctx, machine, services):
            machine.baseline_store["bl_custom"] = {"status": "tracked", "source": "custom"}
            return TruthCore(truth="N", reason="fixture"), machine, []

        primitives = PrimitiveSet(eval_expr=baseline_dict_injector)

        result = run_session(bundle, session, _env(), primitives=primitives)

        assert result.baseline_states["bl_custom"] == {"status": "tracked", "source": "custom"}

    def test_run_session_aggregates_state_across_steps(self):
        bundle = _bundle()
        session = SessionConfig(id="sess1", steps=[StepConfig(id="s1"), StepConfig(id="s2")])

        def step_state_injector(claim, ev_id, step_ctx, machine, services):
            step_index = services.get("__fixture_step_index__", 0)
            if step_index == 0:
                machine.baseline_store["bl_s1"] = {"status": "ready"}
                machine.adequacy_store["per_assessment"] = {"aa_s1": {"truth": "T"}}
            else:
                machine.baseline_store["bl_s2"] = {"status": "deferred"}
                machine.adequacy_store["per_assessment"] = {"aa_s2": {"truth": "F"}}
            return TruthCore(truth="N", reason="fixture"), machine, []

        primitives = PrimitiveSet(eval_expr=step_state_injector)

        result = run_session(bundle, session, _env(), primitives=primitives)

        assert result.baseline_states["bl_s1"] == {"status": "ready"}
        assert result.baseline_states["bl_s2"] == {"status": "deferred"}
        assert result.adequacy_store["per_assessment"]["aa_s1"]["truth"] == "T"
        assert result.adequacy_store["per_assessment"]["aa_s2"]["truth"] == "F"

    def test_run_session_does_not_expose_internal_fixture_adequacy_keys(self):
        bundle = _bundle()
        session = SessionConfig(id="sess1", steps=[StepConfig(id="s1")])

        result = run_session(bundle, session, _env())

        assert "__fixture_step_index__" not in result.adequacy_store

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


# ---------------------------------------------------------------------------
# claim_subset (spec §16.2 / §16.2.1) and shared_state (spec §16.6.3) helpers
# ---------------------------------------------------------------------------


def _baseline(baseline_id="bl1", mode="fixed", kind="point"):
    return BaselineNode(
        id=baseline_id,
        kind=kind,
        criterion=CriterionRefNode(ref="test://baseline/context_v1"),
        frame=FramePatternNode(facets={"system": "sys"}),
        evaluationMode=mode,
    )


def _baseline_claim(claim_id="c_bl", baseline_id="bl1"):
    """A claim whose expression references a baseline via BaselineRefTerm."""
    return ClaimNode(
        id=claim_id,
        kind="atomic",
        expr=PredicateExprNode(
            name="matches_baseline",
            args=[
                SymbolTermNode(value="sensor_A"),
                BaselineRefTermNode(id=baseline_id),
            ],
        ),
    )


def _multi_block_bundle(blocks, baselines=None):
    """BundleNode with explicit claim blocks and optional baselines."""
    return BundleNode(
        id="test_bundle",
        frame=_frame(),
        evaluators=[EvaluatorNode(id="ev1", kind="model", binding="b1")],
        resolutionPolicy=ResolutionPolicyNode(id="pol", kind="single", members=["ev1"]),
        baselines=baselines or [],
        claimBlocks=blocks,
    )


def _counting_context_resolver(counter):
    """Criterion resolver stub: counts calls, value depends on step context.

    Returns "<baseline_id>@<effective_time.t>" so a context change between
    steps produces a different value — the discriminating observable for
    shared_state semantics (spec §16.6.3).
    """
    def resolver(baseline_node, step_ctx, services):
        counter["calls"] += 1
        t = None
        if step_ctx is not None and step_ctx.effective_time is not None:
            t = step_ctx.effective_time.t
        return f"{baseline_node.id}@{t}"
    return resolver


def _two_step_session(shared_state=True):
    """Session with two steps under different time contexts."""
    return SessionConfig(
        id="sess1",
        shared_state=shared_state,
        steps=[
            StepConfig(id="t0", time=TimeCtxNode(kind="point", t="2026-03-06T09:00:00Z")),
            StepConfig(id="t1", time=TimeCtxNode(kind="point", t="2026-03-06T09:05:00Z")),
        ],
    )


# ---------------------------------------------------------------------------
# claim_subset (spec §16.2 / §16.2.1)
# ---------------------------------------------------------------------------


class TestClaimSubset:
    """EvaluationStep.claim_subset semantics per spec §16.2 / §16.2.1.

    claim_subset limits which claims are evaluated in the step: excluded
    claims do not appear in per-claim results and are excluded from block
    folding. It never forces eager baseline materialization.
    """

    def _claims(self, *ids):
        return [
            ClaimNode(id=cid, kind="atomic", expr=PredicateExprNode(name=f"P_{cid}"))
            for cid in ids
        ]

    def test_none_claim_subset_evaluates_all_claims(self):
        """None means no restriction (§16.2: claim_subset is optional)."""
        bundle = _bundle(claims=self._claims("c1", "c2"))

        result = run_step(bundle, _session(), StepConfig(id="s1"), _env())

        assert set(result.per_claim_classifications.keys()) == {"c1", "c2"}
        assert set(result.per_claim_per_evaluator.keys()) == {"c1", "c2"}
        assert [cr.claim_id for cr in result.claim_results] == ["c1", "c2"]
        assert result.block_results[0].claims == ["c1", "c2"]

    def test_subset_restricts_results_to_named_claims(self):
        """Only named claims are evaluated; excluded claims are absent
        from every per-claim result surface (§16.2.1)."""
        bundle = _bundle(claims=self._claims("c1", "c2", "c3"))
        step = StepConfig(id="s1", claim_subset=["c2"])

        result = run_step(bundle, _session(), step, _env())

        assert set(result.per_claim_classifications.keys()) == {"c2"}
        assert set(result.per_claim_per_evaluator.keys()) == {"c2"}
        assert set(result.per_claim_aggregates.keys()) == {"c2"}
        assert set(result.per_claim_licenses.keys()) == {"c2"}
        assert [cr.claim_id for cr in result.claim_results] == ["c2"]
        assert result.block_results[0].claims == ["c2"]

    def test_excluded_claims_are_excluded_from_block_folding(self):
        """Block folds over the subset only: a T claim excluded from the
        subset must not influence the block truth (§16.2.1, §16.6.9)."""
        def eval_c1_true_c2_false(claim, ev_id, step_ctx, machine, services):
            truth = "T" if claim.id == "c1" else "F"
            return TruthCore(truth=truth), machine, []

        bundle = _bundle(claims=self._claims("c1", "c2"))
        primitives = PrimitiveSet(eval_expr=eval_c1_true_c2_false)

        unrestricted = run_step(bundle, _session(), StepConfig(id="s1"), _env(),
                                primitives=primitives)
        assert unrestricted.per_block_aggregates["blk1"].truth == "F"

        subset = run_step(bundle, _session(),
                          StepConfig(id="s1", claim_subset=["c1"]), _env(),
                          primitives=primitives)
        assert subset.per_block_aggregates["blk1"].truth == "T"

    def test_block_with_all_claims_excluded_folds_to_empty_block(self):
        """If every evaluable claim of a block is excluded the block's
        evaluable set is empty and folds to N[empty_block] (§16.6.9)."""
        blocks = [
            ClaimBlockNode(id="blk_a", stratum="local", claims=self._claims("c1")),
            ClaimBlockNode(id="blk_b", stratum="local", claims=self._claims("c2")),
        ]
        bundle = _multi_block_bundle(blocks)
        step = StepConfig(id="s1", claim_subset=["c1"])

        result = run_step(bundle, _session(), step, _env())

        assert result.per_block_aggregates["blk_b"].truth == "N"
        assert result.per_block_aggregates["blk_b"].reason == "empty_block"
        for ev_node in result.per_block_per_evaluator["blk_b"].values():
            assert ev_node.truth == "N"
            assert ev_node.reason == "empty_block"
        # The non-excluded block still folds normally.
        assert result.per_block_aggregates["blk_a"].reason != "empty_block"
        blk_b_result = next(br for br in result.block_results if br.block_id == "blk_b")
        assert blk_b_result.claims == []

    def test_empty_subset_evaluates_zero_claims(self):
        """[] evaluates zero claims — the literal reading of §16.2.1's
        restriction rule. The spec is silent on the empty list; it is
        deliberately NOT treated as "no restriction" (use None for that).
        Every block then folds to N[empty_block] (§16.6.9)."""
        bundle = _bundle(claims=self._claims("c1", "c2"))
        step = StepConfig(id="s1", claim_subset=[])

        result = run_step(bundle, _session(), step, _env())

        assert result.per_claim_classifications == {}
        assert result.per_claim_per_evaluator == {}
        assert result.per_claim_aggregates == {}
        assert result.claim_results == []
        assert result.block_results[0].claims == []
        assert result.per_block_aggregates["blk1"].truth == "N"
        assert result.per_block_aggregates["blk1"].reason == "empty_block"

    def test_unknown_claim_id_warns_and_is_ignored(self):
        """Ids naming no bundle claim are ignored with a step-scoped
        warning diagnostic in the claim phase (§16.2.1 implementation
        contract)."""
        bundle = _bundle(claims=self._claims("c1"))
        step = StepConfig(id="s1", claim_subset=["c1", "ghost"])

        result = run_step(bundle, _session(), step, _env())

        # The known claim is still evaluated; the unknown id is nowhere.
        assert set(result.per_claim_per_evaluator.keys()) == {"c1"}
        assert "ghost" not in result.per_claim_aggregates

        warnings = [
            d for d in result.diagnostics
            if d.get("code") == "claim_subset_unknown_id"
        ]
        assert len(warnings) == 1
        assert warnings[0]["severity"] == "warning"
        assert warnings[0]["phase"] == "claim"
        assert warnings[0]["subject"] == "ghost"
        assert warnings[0]["step_id"] == "s1"

    def test_no_unknown_id_diagnostic_without_subset(self):
        bundle = _bundle(claims=self._claims("c1"))

        result = run_step(bundle, _session(), StepConfig(id="s1"), _env())

        assert not any(
            d.get("code") == "claim_subset_unknown_id" for d in result.diagnostics
        )

    def test_subset_does_not_force_eager_baseline_materialization(self):
        """claim_subset does not itself force eager baseline
        materialization (§16.2.1): a baseline whose only referencing claim
        is excluded is never resolved; without the restriction it resolves
        lazily at first relevant use."""
        baseline = _baseline("bl1", mode="fixed")
        blocks = [ClaimBlockNode(
            id="blk1",
            stratum="local",
            claims=[
                _baseline_claim("c_bl", "bl1"),
                ClaimNode(id="c_plain", kind="atomic",
                          expr=PredicateExprNode(name="P")),
            ],
        )]
        bundle = _multi_block_bundle(blocks, baselines=[baseline])

        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}
        run_step(bundle, _session(),
                 StepConfig(id="s1", claim_subset=["c_plain"]), _env(),
                 services=services)
        assert counter["calls"] == 0

        # Control: with no restriction the baseline resolves lazily at the
        # first evaluation of the referencing claim.
        counter2 = {"calls": 0}
        services2 = {"baseline_criterion_resolver": _counting_context_resolver(counter2)}
        run_step(bundle, _session(), StepConfig(id="s1"), _env(), services=services2)
        assert counter2["calls"] == 1


# ---------------------------------------------------------------------------
# shared_state (spec §16.6.3)
# ---------------------------------------------------------------------------


class TestSharedStateBaselineCaching:
    """EvaluationSession.shared_state semantics per spec §16.6.3.

    Fixed-mode baselines cache under (session_id, baseline_id) when
    shared_state=true (resolve once per session at first use) and under
    (session_id, step_id, baseline_id) when false (fresh fixed-baseline
    context per step). on_reference and tracked modes are unaffected.
    """

    def _bundle_with_baseline(self, mode="fixed", kind="point"):
        blocks = [ClaimBlockNode(
            id="blk1", stratum="local", claims=[_baseline_claim("c_bl", "bl1")],
        )]
        return _multi_block_bundle(blocks, baselines=[_baseline("bl1", mode=mode, kind=kind)])

    def test_session_config_shared_state_defaults_true(self):
        """§16.6.3 / §16.2: shared_state: true | false = true."""
        assert SessionConfig(id="s").shared_state is True

    def test_shared_state_true_reuses_fixed_value_across_steps(self):
        """shared_state=true: cache key (session_id, baseline_id) — the
        fixed baseline resolves once per session at first use; the later
        step reuses the cached value despite its step-local time change
        (§16.6.3)."""
        bundle = self._bundle_with_baseline(mode="fixed")
        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}

        result = run_session(bundle, _two_step_session(shared_state=True), _env(),
                             services=services)

        assert counter["calls"] == 1
        step0_state = result.step_results[0].machine_state.baseline_store["bl1"]
        step1_state = result.step_results[1].machine_state.baseline_store["bl1"]
        assert step0_state.status == "ready"
        assert step0_state.value == "bl1@2026-03-06T09:00:00Z"
        # Step t1 reuses the session-cached value from t0's context.
        assert step1_state.value == step0_state.value

    def test_shared_state_false_re_resolves_fixed_value_per_step(self):
        """shared_state=false: cache key (session_id, step_id, baseline_id)
        — each step behaves as a fresh fixed-baseline context, so the fixed
        baseline takes different values in different steps (§16.6.3)."""
        bundle = self._bundle_with_baseline(mode="fixed")
        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}

        result = run_session(bundle, _two_step_session(shared_state=False), _env(),
                             services=services)

        assert counter["calls"] == 2
        step0_state = result.step_results[0].machine_state.baseline_store["bl1"]
        step1_state = result.step_results[1].machine_state.baseline_store["bl1"]
        assert step0_state.value == "bl1@2026-03-06T09:00:00Z"
        assert step1_state.value == "bl1@2026-03-06T09:05:00Z"
        assert step0_state.value != step1_state.value

    @pytest.mark.parametrize("shared_state", [True, False])
    def test_on_reference_re_resolves_in_both_configurations(self, shared_state):
        """on_reference is unaffected by shared_state: it resolves each
        time a referencing claim is evaluated, under the current effective
        step context (§16.6.3)."""
        bundle = self._bundle_with_baseline(mode="on_reference")
        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}

        result = run_session(bundle, _two_step_session(shared_state=shared_state),
                             _env(), services=services)

        # One referencing claim x one evaluator x two steps = two resolutions.
        assert counter["calls"] == 2
        step0_state = result.step_results[0].machine_state.baseline_store["bl1"]
        step1_state = result.step_results[1].machine_state.baseline_store["bl1"]
        assert step0_state.value == "bl1@2026-03-06T09:00:00Z"
        assert step1_state.value == "bl1@2026-03-06T09:05:00Z"

    def test_tracked_baseline_is_not_materialized(self):
        """tracked baselines resolve as time-indexed objects and are
        unaffected by this scaffold's criterion resolver (§16.6.3)."""
        bundle = self._bundle_with_baseline(mode="tracked", kind="moving")
        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}

        result = run_session(bundle, _two_step_session(shared_state=True), _env(),
                             services=services)

        assert counter["calls"] == 0
        step0_state = result.step_results[0].machine_state.baseline_store["bl1"]
        assert step0_state.value is None

    def test_fixed_cache_is_scoped_per_session(self):
        """The fixed cache key includes session_id: a second session in the
        same bundle run resolves its own value (§16.6.3: once per
        *session*)."""
        bundle = self._bundle_with_baseline(mode="fixed")
        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}
        s1 = SessionConfig(id="sess_a", steps=[StepConfig(id="t0")])
        s2 = SessionConfig(id="sess_b", steps=[StepConfig(id="t0")])

        run_bundle(bundle, [s1, s2], _env(), services=services)

        assert counter["calls"] == 2

    def test_fixed_cache_does_not_survive_across_run_bundle_calls(self):
        """m7 red-team HIGH-2 regression: a services dict reused across two
        run_bundle invocations must NOT carry the fixed-baseline cache from
        run A into run B — §16.6.3 scopes the cache to the sessions of one
        evaluation run, and the cache key (session_id, baseline_id) carries
        no run identity, so a stale entry silently returned run A's value
        for run B's same-named session. run_bundle now installs a fresh
        cache per call, so run B re-resolves under its own step context and
        the claim truth flips with it."""
        bundle = self._bundle_with_baseline(mode="fixed")
        counter = {"calls": 0}
        services = {"baseline_criterion_resolver": _counting_context_resolver(counter)}
        t1 = TimeCtxNode(kind="point", t="2026-03-06T09:00:00Z")
        t2 = TimeCtxNode(kind="point", t="2026-03-06T09:05:00Z")

        run_a = run_bundle(
            bundle,
            [SessionConfig(id="s_shared", steps=[StepConfig(id="s1", time=t1)])],
            _env(), services=services,
        )
        value_a = (
            run_a.session_results[0].step_results[0]
            .machine_state.baseline_store["bl1"].value
        )
        assert value_a == "bl1@2026-03-06T09:00:00Z"
        assert counter["calls"] == 1

        # Run B: SAME services dict, SAME session id, different step context.
        run_b = run_bundle(
            bundle,
            [SessionConfig(id="s_shared", steps=[StepConfig(id="s1", time=t2)])],
            _env(), services=services,
        )
        value_b = (
            run_b.session_results[0].step_results[0]
            .machine_state.baseline_store["bl1"].value
        )
        assert counter["calls"] == 2, "run B must re-resolve, not reuse run A's cache"
        assert value_b == "bl1@2026-03-06T09:05:00Z"
        assert value_b != value_a

    def test_shared_baseline_cache_opt_in_survives_runs(self):
        """The documented opt-in: a dict passed under
        services["__shared_baseline_cache__"] is installed as the run cache
        and survives across run_bundle calls (mutated in place), restoring
        the old cross-run reuse for callers that explicitly want it."""
        bundle = self._bundle_with_baseline(mode="fixed")
        counter = {"calls": 0}
        shared: dict = {}
        services = {
            "baseline_criterion_resolver": _counting_context_resolver(counter),
            "__shared_baseline_cache__": shared,
        }
        t1 = TimeCtxNode(kind="point", t="2026-03-06T09:00:00Z")
        t2 = TimeCtxNode(kind="point", t="2026-03-06T09:05:00Z")

        run_bundle(
            bundle,
            [SessionConfig(id="s_shared", steps=[StepConfig(id="s1", time=t1)])],
            _env(), services=services,
        )
        run_b = run_bundle(
            bundle,
            [SessionConfig(id="s_shared", steps=[StepConfig(id="s1", time=t2)])],
            _env(), services=services,
        )

        assert counter["calls"] == 1, "opt-in shared cache must be reused across runs"
        value_b = (
            run_b.session_results[0].step_results[0]
            .machine_state.baseline_store["bl1"].value
        )
        assert value_b == "bl1@2026-03-06T09:00:00Z"
        assert ("s_shared", "bl1") in shared

    def test_resolver_error_yields_baseline_diagnostic(self):
        """A failing criterion resolver localizes to an unresolved
        BaselineState plus a baseline-phase diagnostic."""
        bundle = self._bundle_with_baseline(mode="fixed")

        def failing_resolver(baseline_node, step_ctx, services):
            raise RuntimeError("resolver exploded")

        services = {"baseline_criterion_resolver": failing_resolver}
        result = run_step(bundle, _session(), _step(), _env(), services=services)

        state = result.machine_state.baseline_store["bl1"]
        assert state.status == "unresolved"
        errors = [
            d for d in result.diagnostics
            if d.get("code") == "baseline_resolution_error"
        ]
        assert errors and errors[0]["subject"] == "bl1"
        assert errors[0]["phase"] == "baseline"

    def test_no_resolver_service_is_a_noop(self):
        """Without services["baseline_criterion_resolver"] materialization
        is a no-op — status-only baseline handling is preserved."""
        claim = _baseline_claim("c_bl", "bl1")
        machine = MachineState()

        diags = materialize_referenced_baselines(
            claim, None, machine, {},
            session_id="s", step_id="t", shared_state=True,
        )

        assert diags == []
        assert machine.baseline_store == {}

    def test_collect_baseline_refs_walks_nested_expressions(self):
        """The reference walker finds BaselineRefTerms in nested logical,
        judged, and list-term positions, deduplicated in source order."""
        expr = LogicalExprNode(
            op="and",
            args=[
                PredicateExprNode(name="P", args=[BaselineRefTermNode(id="b1")]),
                JudgedExprNode(
                    expr=PredicateExprNode(
                        name="Q",
                        args=[ListTermNode(items=[
                            BaselineRefTermNode(id="b2"),
                            BaselineRefTermNode(id="b1"),
                        ])],
                    ),
                    criterionRef="test://criterion/x",
                ),
            ],
        )

        assert _collect_baseline_refs(expr) == ["b1", "b2"]
