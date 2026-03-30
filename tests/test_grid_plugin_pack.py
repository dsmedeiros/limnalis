"""Tests for the grid example plugin pack."""

from __future__ import annotations

import pytest

from limnalis.plugins import (
    ADEQUACY_METHOD,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    PluginRegistry,
)
from limnalis.plugins.grid_example import (
    grid_adequacy_check,
    grid_causal_handler,
    grid_emergence_handler,
    grid_predicate_handler,
    register_grid_plugins,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry() -> PluginRegistry:
    reg = PluginRegistry()
    register_grid_plugins(reg)
    return reg


class _FakeExpr:
    """Minimal stand-in for an expression node."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeClaim:
    """Minimal stand-in for a ClaimNode."""

    def __init__(self, refs=None):
        self.refs = refs or []


class _FakeAssessment:
    """Minimal stand-in for an AdequacyAssessmentNode."""

    def __init__(self, score=None):
        self.score = score


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterGridPlugins:
    """Registration succeeds and all expected plugins are present."""

    def test_register_grid_plugins(self):
        reg = _make_registry()

        # Evaluator bindings
        assert reg.has(EVALUATOR_BINDING, "ev_grid::predicate")
        assert reg.has(EVALUATOR_BINDING, "ev_grid::causal")
        assert reg.has(EVALUATOR_BINDING, "ev_grid::emergence")

        # Support policy
        assert reg.has(EVIDENCE_POLICY, "test://eval/grid_v1")

        # Adequacy methods
        assert reg.has(ADEQUACY_METHOD, "sim://checks/n1_pred")
        assert reg.has(ADEQUACY_METHOD, "sim://checks/n1_ctrl")
        assert reg.has(ADEQUACY_METHOD, "audit://postmortem/n1_expl")

    def test_total_plugin_count(self):
        reg = _make_registry()
        all_plugins = reg.list_plugins()
        # 3 evaluator bindings + 1 evidence policy + 3 adequacy methods = 7
        assert len(all_plugins) == 7


class TestGridPredicateHandler:
    """grid_predicate_handler returns TruthCore with truth=T."""

    def test_returns_truth_t(self):
        expr = _FakeExpr(name="overload", args=[])
        claim = _FakeClaim()
        result = grid_predicate_handler(expr, claim, None, None)
        assert result.truth == "T"
        assert result.reason == "grid_predicate_match"
        assert result.confidence == 1.0
        assert "grid_v1" in result.provenance


class TestGridCausalHandler:
    """grid_causal_handler returns TruthCore with truth=B."""

    def test_returns_truth_b(self):
        expr = _FakeExpr(mode="obs")
        claim = _FakeClaim()
        result = grid_causal_handler(expr, claim, None, None)
        assert result.truth == "B"
        assert result.reason == "source_conflict"
        assert result.confidence == pytest.approx(0.72)
        assert "scada_pmu_conflict" in result.provenance


class TestGridEmergenceHandler:
    """grid_emergence_handler returns TruthCore with truth=T."""

    def test_returns_truth_t(self):
        expr = _FakeExpr(property="voltage_instability")
        claim = _FakeClaim()
        result = grid_emergence_handler(expr, claim, None, None)
        assert result.truth == "T"
        assert result.reason == "emergence_detected"
        assert result.confidence == pytest.approx(0.85)


class TestGridAdequacyHandler:
    """grid_adequacy_check returns correct score float."""

    def test_returns_score(self):
        assessment = _FakeAssessment(score=0.98)
        assert grid_adequacy_check(assessment) == pytest.approx(0.98)

    def test_returns_zero_when_no_score(self):
        assessment = _FakeAssessment(score=None)
        assert grid_adequacy_check(assessment) == 0.0

    def test_returns_zero_when_no_attr(self):
        assessment = object()
        assert grid_adequacy_check(assessment) == 0.0


class TestGridPluginPackImportable:
    """The plugin pack is importable from limnalis.plugins.grid_example."""

    def test_importable(self):
        from limnalis.plugins.grid_example import register_grid_plugins as fn

        assert callable(fn)

    def test_all_handlers_importable(self):
        from limnalis.plugins.grid_example import (
            grid_adequacy_check,
            grid_causal_handler,
            grid_emergence_handler,
            grid_predicate_handler,
            grid_support_policy,
        )

        for fn in [
            grid_predicate_handler,
            grid_causal_handler,
            grid_emergence_handler,
            grid_support_policy,
            grid_adequacy_check,
        ]:
            assert callable(fn)
