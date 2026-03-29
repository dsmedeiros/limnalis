"""Tests for the JWT/auth domain example plugin pack."""

from __future__ import annotations

import pytest

from limnalis.plugins import (
    ADEQUACY_METHOD,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    PluginRegistry,
)
from limnalis.plugins.jwt_example import (
    jwt_adequacy_check,
    jwt_judged_handler,
    jwt_predicate_handler,
    register_jwt_plugins,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> PluginRegistry:
    reg = PluginRegistry()
    register_jwt_plugins(reg)
    return reg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterJwtPlugins:
    """Registration succeeds and all expected plugins are present."""

    def test_evaluator_bindings_registered(self, registry: PluginRegistry) -> None:
        assert registry.has(EVALUATOR_BINDING, "ev_gateway::predicate")
        assert registry.has(EVALUATOR_BINDING, "ev_gateway::judged")

    def test_support_policy_registered(self, registry: PluginRegistry) -> None:
        assert registry.has(EVIDENCE_POLICY, "test://policy/jwt_support_v1")

    def test_adequacy_methods_registered(self, registry: PluginRegistry) -> None:
        for uri in [
            "test://method/stateless_access",
            "test://method/stateless_revocation",
            "test://method/clock_access",
            "test://method/jwt_joint_access",
        ]:
            assert registry.has(ADEQUACY_METHOD, uri), f"Missing adequacy method: {uri}"

    def test_total_plugin_count(self, registry: PluginRegistry) -> None:
        all_plugins = registry.list_plugins()
        # 2 evaluator bindings + 1 support policy + 4 adequacy methods = 7
        assert len(all_plugins) == 7


class TestJwtPredicateHandler:
    """jwt_predicate_handler returns TruthCore with truth=T."""

    def test_returns_truth_t(self) -> None:
        result = jwt_predicate_handler(None, None, None, None)
        assert result.truth == "T"

    def test_has_reason(self) -> None:
        result = jwt_predicate_handler(None, None, None, None)
        assert result.reason == "jwt_check_passed"

    def test_has_provenance(self) -> None:
        result = jwt_predicate_handler(None, None, None, None)
        assert "jwt_gateway_v1" in result.provenance

    def test_confidence_is_one(self) -> None:
        result = jwt_predicate_handler(None, None, None, None)
        assert result.confidence == 1.0


class TestJwtJudgedHandler:
    """jwt_judged_handler returns TruthCore with truth=T and mentions policy."""

    def test_returns_truth_t(self) -> None:
        result = jwt_judged_handler(None, None, None, None)
        assert result.truth == "T"

    def test_mentions_policy_in_provenance(self) -> None:
        result = jwt_judged_handler(None, None, None, None)
        assert "auth_access_v3" in result.provenance

    def test_has_policy_satisfied_reason(self) -> None:
        result = jwt_judged_handler(None, None, None, None)
        assert result.reason == "policy_satisfied"


class TestJwtAdequacyHandler:
    """jwt_adequacy_check returns correct score float."""

    def test_returns_score_as_float(self) -> None:

        class FakeAssessment:
            score = 0.96

        result = jwt_adequacy_check(FakeAssessment())
        assert result == pytest.approx(0.96)

    def test_returns_zero_for_none_score(self) -> None:

        class FakeAssessment:
            score = None

        result = jwt_adequacy_check(FakeAssessment())
        assert result == 0.0

    def test_returns_zero_for_n_score(self) -> None:

        class FakeAssessment:
            score = "N"

        result = jwt_adequacy_check(FakeAssessment())
        assert result == 0.0

    def test_returns_zero_for_missing_score(self) -> None:

        class FakeAssessment:
            pass

        result = jwt_adequacy_check(FakeAssessment())
        assert result == 0.0


class TestJwtPluginPackImportable:
    """Module is importable from limnalis.plugins.jwt_example."""

    def test_importable(self) -> None:
        from limnalis.plugins.jwt_example import register_jwt_plugins  # noqa: F811

        assert callable(register_jwt_plugins)

    def test_all_handlers_importable(self) -> None:
        from limnalis.plugins.jwt_example import (  # noqa: F811
            jwt_adequacy_check,
            jwt_judged_handler,
            jwt_predicate_handler,
            jwt_support_policy,
        )

        assert callable(jwt_predicate_handler)
        assert callable(jwt_judged_handler)
        assert callable(jwt_support_policy)
        assert callable(jwt_adequacy_check)
