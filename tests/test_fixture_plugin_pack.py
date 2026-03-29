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


class TestFixtureEvalHandler:
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


class TestImportable:
    """Test that the module is importable from the expected path."""

    def test_register_fixture_plugins_importable(self) -> None:
        from limnalis.plugins.fixtures import register_fixture_plugins

        assert callable(register_fixture_plugins)

    def test_handler_classes_importable(self) -> None:
        from limnalis.plugins.fixtures import (
            FixtureAdequacyHandler,
            FixtureAdjudicator,
            FixtureEvalHandler,
            FixtureEvalHandlerForEvaluator,
            FixtureSupportHandler,
        )

        assert all(
            callable(cls)
            for cls in [
                FixtureAdequacyHandler,
                FixtureAdjudicator,
                FixtureEvalHandler,
                FixtureEvalHandlerForEvaluator,
                FixtureSupportHandler,
            ]
        )
