"""Tests for the fixture plugin pack (limnalis.plugins.fixtures)."""

from __future__ import annotations

import pytest

from limnalis.conformance.fixtures import FixtureCase
from limnalis.plugins import (
    ADEQUACY_METHOD,
    ADJUDICATOR,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    PluginRegistry,
)
from limnalis.plugins.fixtures import (
    FixtureAdequacyHandler,
    FixtureAdjudicator,
    FixtureEvalHandlerForEvaluator,
    FixtureSupportHandler,
    _has_adjudicated_policy,
    _collect_evaluator_expr_types,
    register_fixture_plugins,
)
from limnalis.runtime.models import (
    EvalNode,
    MachineState,
    SupportResult,
    TruthCore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(
    *,
    case_id: str = "test_case",
    evaluator_ids: list[str] | None = None,
    claims: dict | None = None,
    environment: dict | None = None,
) -> FixtureCase:
    """Build a minimal FixtureCase for testing."""
    if evaluator_ids is None:
        evaluator_ids = ["ev1"]
    if claims is None:
        claims = {
            "c1": {
                "per_evaluator": {
                    "ev1": {"truth": "T", "support": "supported"},
                },
            },
        }
    if environment is None:
        environment = {
            "bindings": [
                {"id": ev_id, "type": "evaluator", "expr_type": "predicate"}
                for ev_id in evaluator_ids
            ],
        }

    return FixtureCase(
        id=case_id,
        track="test",
        name="Test case",
        focus=["unit"],
        source="",
        environment=environment,
        expected={
            "sessions": [
                {
                    "id": "default",
                    "steps": [
                        {
                            "id": "step0",
                            "claims": claims,
                        }
                    ],
                }
            ],
        },
    )


class _FakeClaim:
    """Minimal claim stub with an id attribute."""

    def __init__(self, claim_id: str) -> None:
        self.id = claim_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterFixturePluginsCreatesEntries:
    """Test that register_fixture_plugins populates the registry."""

    def test_evaluator_bindings_registered(self) -> None:
        registry = PluginRegistry()
        case = _make_case(evaluator_ids=["ev1"])
        register_fixture_plugins(registry, case)

        assert registry.has(EVALUATOR_BINDING, "ev1::predicate")

    def test_multiple_evaluators(self) -> None:
        registry = PluginRegistry()
        case = _make_case(
            evaluator_ids=["ev1", "ev2"],
            claims={
                "c1": {
                    "per_evaluator": {
                        "ev1": {"truth": "T"},
                        "ev2": {"truth": "F"},
                    },
                },
            },
        )
        register_fixture_plugins(registry, case)

        assert registry.has(EVALUATOR_BINDING, "ev1::predicate")
        assert registry.has(EVALUATOR_BINDING, "ev2::predicate")

    def test_evidence_policy_registered(self) -> None:
        registry = PluginRegistry()
        case = _make_case(
            environment={
                "bindings": [
                    {"id": "ev1", "type": "evaluator", "expr_type": "predicate"},
                    {"id": "test://policy/v1", "type": "evidence_policy"},
                ],
            },
        )
        register_fixture_plugins(registry, case)

        assert registry.has(EVIDENCE_POLICY, "test://policy/v1")

    def test_adequacy_method_registered(self) -> None:
        registry = PluginRegistry()
        case = _make_case(
            environment={
                "bindings": [
                    {"id": "ev1", "type": "evaluator", "expr_type": "predicate"},
                ],
                "adequacy_methods": {
                    "test://adequacy/v1": {"score": 0.85},
                },
            },
        )
        register_fixture_plugins(registry, case)

        assert registry.has(ADEQUACY_METHOD, "test://adequacy/v1")

    def test_adjudicator_registered_for_conflict(self) -> None:
        registry = PluginRegistry()
        case = _make_case(
            evaluator_ids=["ev1", "ev2"],
            claims={
                "c1": {
                    "per_evaluator": {
                        "ev1": {"truth": "T"},
                        "ev2": {"truth": "F"},
                    },
                    "aggregate": {"truth": "B", "reason": "evaluator_conflict"},
                },
            },
        )
        register_fixture_plugins(registry, case)

        assert registry.has(ADJUDICATOR, f"fixture_adjudicator::{case.id}")

    def test_returns_extras_dict(self) -> None:
        registry = PluginRegistry()
        case = _make_case()
        extras = register_fixture_plugins(registry, case)

        assert isinstance(extras, dict)
        assert "__fixture_step_index__" in extras


class TestFixtureEvalHandlerForEvaluator:
    """Test that FixtureEvalHandlerForEvaluator returns expected TruthCore."""

    def test_returns_expected_truth(self) -> None:
        truth_map = {
            "c1": {
                "ev1": TruthCore(truth="T", reason="test_reason"),
            },
        }
        handler = FixtureEvalHandlerForEvaluator("ev1", truth_map)
        claim = _FakeClaim("c1")

        result = handler(expr=None, claim=claim, step_ctx=None, machine_state=MachineState())

        assert result.truth == "T"
        assert result.reason == "test_reason"

    def test_returns_default_for_unknown_claim(self) -> None:
        truth_map = {"c1": {"ev1": TruthCore(truth="T")}}
        handler = FixtureEvalHandlerForEvaluator("ev1", truth_map)
        claim = _FakeClaim("unknown_claim")

        result = handler(expr=None, claim=claim, step_ctx=None, machine_state=MachineState())

        assert result.truth == "N"
        assert result.reason == "fixture_not_specified"

    def test_returns_default_for_wrong_evaluator(self) -> None:
        truth_map = {"c1": {"ev1": TruthCore(truth="T")}}
        handler = FixtureEvalHandlerForEvaluator("ev_other", truth_map)
        claim = _FakeClaim("c1")

        result = handler(expr=None, claim=claim, step_ctx=None, machine_state=MachineState())

        assert result.truth == "N"

    def test_uses_per_step_truth_map_when_step_index_is_present(self) -> None:
        per_step_truth_maps = [
            {"c1": {"ev1": TruthCore(truth="T", reason="step0")}},
            {"c1": {"ev1": TruthCore(truth="F", reason="step1")}},
        ]
        merged_truth_map = {"c1": {"ev1": TruthCore(truth="F", reason="merged")}}
        handler = FixtureEvalHandlerForEvaluator(
            "ev1",
            merged_truth_map,
            per_step_truth_maps=per_step_truth_maps,
        )
        claim = _FakeClaim("c1")

        machine0 = MachineState()
        machine0.adequacy_store["__fixture_step_index__"] = 0
        result0 = handler(expr=None, claim=claim, step_ctx=None, machine_state=machine0)
        assert result0.truth == "T"
        assert result0.reason == "step0"

        machine1 = MachineState()
        machine1.adequacy_store["__fixture_step_index__"] = 1
        result1 = handler(expr=None, claim=claim, step_ctx=None, machine_state=machine1)
        assert result1.truth == "F"
        assert result1.reason == "step1"


class TestFixtureSupportHandler:
    """Test that FixtureSupportHandler returns expected SupportResult."""

    def test_returns_expected_support(self) -> None:
        support_map = {"c1": {"ev1": "supported"}}
        handler = FixtureSupportHandler(support_map)
        claim = _FakeClaim("c1")

        result = handler(
            claim=claim,
            truth_core=TruthCore(truth="T"),
            evidence_view=None,
            evaluator_id="ev1",
            step_ctx=None,
            machine_state=MachineState(),
        )

        assert isinstance(result, SupportResult)
        assert result.support == "supported"
        assert "ev1" in result.provenance
        assert "c1" in result.provenance

    def test_returns_absent_for_unknown(self) -> None:
        support_map: dict = {}
        handler = FixtureSupportHandler(support_map)
        claim = _FakeClaim("unknown")

        result = handler(
            claim=claim,
            truth_core=TruthCore(truth="T"),
            evidence_view=None,
            evaluator_id="ev1",
            step_ctx=None,
            machine_state=MachineState(),
        )

        assert result.support == "absent"


class TestFixtureAdequacyHandler:
    """Test that FixtureAdequacyHandler returns the configured score."""

    def test_returns_score(self) -> None:
        handler = FixtureAdequacyHandler(0.95)
        result = handler(assessment={"some": "data"})
        assert result == 0.95

    def test_returns_zero(self) -> None:
        handler = FixtureAdequacyHandler(0.0)
        assert handler(assessment=None) == 0.0

    def test_returns_one(self) -> None:
        handler = FixtureAdequacyHandler(1.0)
        assert handler(assessment="anything") == 1.0


class TestFixtureAdjudicator:
    """Test FixtureAdjudicator conflict detection."""

    def test_conflict_returns_B(self) -> None:
        adj = FixtureAdjudicator()
        result = adj({
            "ev1": EvalNode(truth="T", provenance=["ev1"]),
            "ev2": EvalNode(truth="F", provenance=["ev2"]),
        })
        assert result.truth == "B"
        assert result.reason == "evaluator_conflict"

    def test_agreement_returns_agreed(self) -> None:
        adj = FixtureAdjudicator()
        result = adj({
            "ev1": EvalNode(truth="T", support="supported", provenance=["ev1"]),
            "ev2": EvalNode(truth="T", support="supported", provenance=["ev2"]),
        })
        assert result.truth == "T"

    def test_empty_returns_N(self) -> None:
        adj = FixtureAdjudicator()
        result = adj({})
        assert result.truth == "N"
        assert result.reason == "no_evaluators"

    def test_mixed_t_and_n_aggregates(self) -> None:
        """T and N are not a conflict; join(T, N) = T via paraconsistent lattice."""
        adj = FixtureAdjudicator()
        result = adj({
            "ev1": EvalNode(truth="T", support="supported", provenance=["ev1"]),
            "ev2": EvalNode(truth="N", support="absent", provenance=["ev2"]),
        })
        assert result.truth == "T"
        assert result.reason is None  # no conflict
        assert sorted(result.provenance) == ["ev1", "ev2"]

    def test_mixed_f_and_n_aggregates(self) -> None:
        """F and N are not a conflict; join(F, N) = F via paraconsistent lattice."""
        adj = FixtureAdjudicator()
        result = adj({
            "ev1": EvalNode(truth="F", support="supported", provenance=["ev1"]),
            "ev2": EvalNode(truth="N", support="absent", provenance=["ev2"]),
        })
        assert result.truth == "F"
        assert result.reason is None  # no conflict
        assert sorted(result.provenance) == ["ev1", "ev2"]

    def test_mixed_truths_without_support_default_to_absent(self) -> None:
        """Mixed non-conflicting truths with no support values should return absent support."""
        adj = FixtureAdjudicator()
        result = adj({
            "ev1": EvalNode(truth="B", provenance=["ev1"]),
            "ev2": EvalNode(truth="N", provenance=["ev2"]),
        })
        assert result.truth == "B"
        assert result.reason == "evaluator_conflict"
        assert result.support == "absent"


class TestFixtureSupportHandlerDefaultSynth:
    """Test FixtureSupportHandler default_synth fallback path."""

    def test_default_synth_fallback_non_tuple(self) -> None:
        """When claim is not in the support map, default_synth is called.

        Non-tuple return is used directly.
        """
        sentinel = SupportResult(support="partial", provenance=["fallback"])

        def synth(claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state):
            return sentinel

        handler = FixtureSupportHandler({}, default_synth=synth)
        claim = _FakeClaim("unknown")
        result = handler(
            claim=claim,
            truth_core=TruthCore(truth="T"),
            evidence_view=None,
            evaluator_id="ev1",
            step_ctx=None,
            machine_state=MachineState(),
        )
        assert result is sentinel

    def test_default_synth_fallback_tuple(self) -> None:
        """When default_synth returns a tuple, the first element is extracted."""
        inner = SupportResult(support="supported", provenance=["tuple_fallback"])

        def synth(claim, truth_core, evidence_view, evaluator_id, step_ctx, machine_state):
            return (inner, "extra_metadata")

        handler = FixtureSupportHandler({}, default_synth=synth)
        claim = _FakeClaim("unknown")
        result = handler(
            claim=claim,
            truth_core=TruthCore(truth="T"),
            evidence_view=None,
            evaluator_id="ev1",
            step_ctx=None,
            machine_state=MachineState(),
        )
        assert result is inner


class TestHasAdjudicatedPolicy:
    """Test _has_adjudicated_policy with edge cases."""

    def test_non_dict_aggregate_returns_false(self) -> None:
        """A non-dict aggregate value should not cause an error."""
        case = _make_case(
            claims={
                "c1": {
                    "per_evaluator": {
                        "ev1": {"truth": "T"},
                    },
                    "aggregate": "not_a_dict",
                },
            },
        )
        assert _has_adjudicated_policy(case) is False

    def test_detects_adjudicated_policy_from_source(self, monkeypatch) -> None:
        class _Policy:
            kind = "adjudicated"

        class _Ast:
            resolutionPolicy = _Policy()

        class _Norm:
            canonical_ast = _Ast()

        def _fake_normalize(source: str, *, validate_schema: bool = True):
            return _Norm()

        monkeypatch.setattr("limnalis.plugins.fixtures.normalize_surface_text", _fake_normalize)
        case = _make_case(claims={"c1": {"per_evaluator": {"ev1": {"truth": "T"}}}})
        case.source = "bundle with adjudicated policy"

        assert _has_adjudicated_policy(case) is True


class TestCollectEvaluatorExprTypes:
    """Test _collect_evaluator_expr_types fallback behavior."""

    def test_uses_expr_kinds_from_source_when_bindings_missing(self, monkeypatch) -> None:
        class _Expr:
            def __init__(self, node: str) -> None:
                self.node = node

        class _Claim:
            def __init__(self, cid: str, node: str) -> None:
                self.id = cid
                self.expr = _Expr(node)

        class _Block:
            def __init__(self, claims) -> None:
                self.claims = claims

        class _Ast:
            def __init__(self, blocks) -> None:
                self.claimBlocks = blocks

        class _Norm:
            def __init__(self, ast) -> None:
                self.canonical_ast = ast

        def _fake_normalize(source: str, *, validate_schema: bool = True):
            return _Norm(_Ast([_Block([_Claim("c1", "JudgedExpr")])]))

        monkeypatch.setattr("limnalis.plugins.fixtures.normalize_surface_text", _fake_normalize)

        case = _make_case(
            claims={"c1": {"per_evaluator": {"ev1": {"truth": "T"}}}},
            environment={"bindings": []},
        )
        case.source = "claim c1 ..."
        pairs = _collect_evaluator_expr_types(case)
        assert ("ev1", "judged") in pairs


class TestImportable:
    """Test that the module is importable from the expected path."""

    def test_register_fixture_plugins_importable(self) -> None:
        from limnalis.plugins.fixtures import register_fixture_plugins

        assert callable(register_fixture_plugins)

    def test_handler_classes_importable(self) -> None:
        from limnalis.plugins.fixtures import (
            FixtureAdequacyHandler,
            FixtureAdjudicator,
            FixtureEvalHandlerForEvaluator,
            FixtureSupportHandler,
        )

        assert all(
            callable(cls)
            for cls in [
                FixtureAdequacyHandler,
                FixtureAdjudicator,
                FixtureEvalHandlerForEvaluator,
                FixtureSupportHandler,
            ]
        )
