"""Tests for the Limnalis plugin registry system."""

from __future__ import annotations

import pytest

from limnalis.plugins import (
    ADEQUACY_METHOD,
    EVALUATOR_BINDING,
    EVIDENCE_POLICY,
    PluginConflictError,
    PluginMetadata,
    PluginNotFoundError,
    PluginRegistry,
    RegistryEvaluatorBindings,
    build_services_from_registry,
)


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


# -- basic register / get --------------------------------------------------


def test_register_and_get(registry: PluginRegistry) -> None:
    handler = lambda: "hello"
    registry.register("test_kind", "p1", handler)
    assert registry.get("test_kind", "p1") is handler


def test_register_duplicate_raises(registry: PluginRegistry) -> None:
    registry.register("k", "id1", lambda: None)
    with pytest.raises(PluginConflictError) as exc_info:
        registry.register("k", "id1", lambda: None)
    assert exc_info.value.kind == "k"
    assert exc_info.value.plugin_id == "id1"


def test_get_missing_raises(registry: PluginRegistry) -> None:
    with pytest.raises(PluginNotFoundError) as exc_info:
        registry.get("no_kind", "no_id")
    assert exc_info.value.kind == "no_kind"
    assert exc_info.value.plugin_id == "no_id"


# -- metadata --------------------------------------------------------------


def test_get_metadata(registry: PluginRegistry) -> None:
    handler = lambda: None
    registry.register("k", "p", handler, version="1.0", description="A plugin")
    meta = registry.get_metadata("k", "p")
    assert isinstance(meta, PluginMetadata)
    assert meta.kind == "k"
    assert meta.plugin_id == "p"
    assert meta.handler is handler
    assert meta.version == "1.0"
    assert meta.description == "A plugin"


# -- list ------------------------------------------------------------------


def test_list_plugins_all(registry: PluginRegistry) -> None:
    registry.register("b_kind", "z_id", 1)
    registry.register("a_kind", "y_id", 2)
    registry.register("a_kind", "x_id", 3)
    result = registry.list_plugins()
    assert len(result) == 3


def test_list_plugins_by_kind(registry: PluginRegistry) -> None:
    registry.register("alpha", "p1", 1)
    registry.register("beta", "p2", 2)
    registry.register("alpha", "p3", 3)
    result = registry.list_plugins("alpha")
    assert len(result) == 2
    assert all(m.kind == "alpha" for m in result)


def test_list_plugins_deterministic_order(registry: PluginRegistry) -> None:
    registry.register("b", "z", 1)
    registry.register("a", "y", 2)
    registry.register("a", "x", 3)
    registry.register("b", "w", 4)
    result = registry.list_plugins()
    keys = [(m.kind, m.plugin_id) for m in result]
    assert keys == sorted(keys)


# -- has -------------------------------------------------------------------


def test_has(registry: PluginRegistry) -> None:
    assert registry.has("k", "p") is False
    registry.register("k", "p", 1)
    assert registry.has("k", "p") is True


# -- unregister / clear ----------------------------------------------------


def test_unregister(registry: PluginRegistry) -> None:
    registry.register("k", "p", 1)
    assert registry.has("k", "p")
    registry.unregister("k", "p")
    assert not registry.has("k", "p")


def test_unregister_missing_raises(registry: PluginRegistry) -> None:
    with pytest.raises(PluginNotFoundError):
        registry.unregister("k", "nope")


def test_clear(registry: PluginRegistry) -> None:
    registry.register("a", "1", 1)
    registry.register("b", "2", 2)
    registry.clear()
    assert registry.list_plugins() == []


# -- kinds -----------------------------------------------------------------


def test_kinds(registry: PluginRegistry) -> None:
    registry.register("beta", "p1", 1)
    registry.register("alpha", "p2", 2)
    registry.register("beta", "p3", 3)
    assert registry.kinds() == ["alpha", "beta"]


# -- build_services --------------------------------------------------------


def test_build_services_evaluator_bindings(registry: PluginRegistry) -> None:
    handler = lambda expr, claim, ctx, state: None
    registry.register(EVALUATOR_BINDING, "eval1::predicate", handler)
    services = build_services_from_registry(registry)
    assert "evaluator_bindings" in services
    assert isinstance(services["evaluator_bindings"], RegistryEvaluatorBindings)


def test_build_services_adequacy_handlers(registry: PluginRegistry) -> None:
    handler = lambda: None
    registry.register(ADEQUACY_METHOD, "method_a", handler)
    services = build_services_from_registry(registry)
    assert "adequacy_handlers" in services
    assert services["adequacy_handlers"]["method_a"] is handler


def test_build_services_evidence_policy(registry: PluginRegistry) -> None:
    handler = lambda: None
    registry.register(EVIDENCE_POLICY, "policy_x", handler)
    services = build_services_from_registry(registry)
    assert "support_policy_handlers" in services
    assert services["support_policy_handlers"]["policy_x"] is handler


# -- RegistryEvaluatorBindings ---------------------------------------------


def test_registry_evaluator_bindings_lookup(registry: PluginRegistry) -> None:
    handler = lambda expr, claim, ctx, state: None
    registry.register(EVALUATOR_BINDING, "eval1::predicate", handler)
    bindings = RegistryEvaluatorBindings(registry)
    assert bindings.get_handler("eval1", "predicate") is handler


def test_registry_evaluator_bindings_miss(registry: PluginRegistry) -> None:
    bindings = RegistryEvaluatorBindings(registry)
    assert bindings.get_handler("no_eval", "no_type") is None


# -- public API importability ----------------------------------------------


def test_public_api_importable() -> None:
    from limnalis.api.services import (  # noqa: F401
        ADEQUACY_METHOD,
        ADJUDICATOR,
        BASELINE_HANDLER,
        BINDING_RESOLVER,
        CRITERION_BINDING,
        EVALUATOR_BINDING,
        EVIDENCE_POLICY,
        TRANSPORT_HANDLER,
        PluginConflictError,
        PluginError,
        PluginMetadata,
        PluginNotFoundError,
        PluginRegistry,
        RegistryEvaluatorBindings,
        build_services_from_registry,
    )
