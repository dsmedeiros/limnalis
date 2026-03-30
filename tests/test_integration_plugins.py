"""Integration tests for the Limnalis extension SDK pipeline.

Validates plugin registry, plugin packs (fixture, grid, JWT), conformance
execution, public API consumer workflows, import hygiene, and determinism.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from limnalis.api.services import (
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
from limnalis.api.conformance import (
    compare_case,
    load_corpus_from_default,
    run_case,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture(scope="module")
def corpus():
    return load_corpus_from_default()


# ===========================================================================
# 1. Plugin Registry Integration
# ===========================================================================


class TestPluginRegistryIntegration:
    """Register multiple plugin kinds, verify deterministic listing and errors."""

    def test_plugin_registry_register_and_lookup(self, registry: PluginRegistry) -> None:
        """Register multiple plugin kinds, verify deterministic listing."""
        h1 = lambda: "eval"
        h2 = lambda: "policy"
        h3 = lambda: "adequacy"

        registry.register(EVALUATOR_BINDING, "ev1::predicate", h1)
        registry.register(EVIDENCE_POLICY, "policy_a", h2)
        registry.register(ADEQUACY_METHOD, "method_x", h3)

        assert registry.get(EVALUATOR_BINDING, "ev1::predicate") is h1
        assert registry.get(EVIDENCE_POLICY, "policy_a") is h2
        assert registry.get(ADEQUACY_METHOD, "method_x") is h3

        all_plugins = registry.list_plugins()
        assert len(all_plugins) == 3
        keys = [(m.kind, m.plugin_id) for m in all_plugins]
        assert keys == sorted(keys), "Listing must be in deterministic sorted order"

    def test_plugin_metadata_reporting(self, registry: PluginRegistry) -> None:
        """Verify metadata includes kind, id, version, description."""
        handler = lambda: None
        registry.register(
            EVALUATOR_BINDING,
            "ev_test::predicate",
            handler,
            version="2.0.1",
            description="Test evaluator binding",
        )
        meta = registry.get_metadata(EVALUATOR_BINDING, "ev_test::predicate")
        assert isinstance(meta, PluginMetadata)
        assert meta.kind == EVALUATOR_BINDING
        assert meta.plugin_id == "ev_test::predicate"
        assert meta.version == "2.0.1"
        assert meta.description == "Test evaluator binding"
        assert meta.handler is handler

    def test_plugin_missing_registration_error(self, registry: PluginRegistry) -> None:
        """Verify clean error on missing plugin lookup."""
        with pytest.raises(PluginNotFoundError) as exc_info:
            registry.get(EVALUATOR_BINDING, "nonexistent::thing")
        assert exc_info.value.kind == EVALUATOR_BINDING
        assert exc_info.value.plugin_id == "nonexistent::thing"

    def test_plugin_invalid_duplicate_error(self, registry: PluginRegistry) -> None:
        """Verify clean error on duplicate registration."""
        registry.register(EVALUATOR_BINDING, "dup::pred", lambda: None)
        with pytest.raises(PluginConflictError) as exc_info:
            registry.register(EVALUATOR_BINDING, "dup::pred", lambda: None)
        assert exc_info.value.kind == EVALUATOR_BINDING
        assert exc_info.value.plugin_id == "dup::pred"


# ===========================================================================
# 2. Fixture Plugin Pack Integration
# ===========================================================================


class TestFixturePluginPackIntegration:
    """Register fixture plugins from corpus cases and run conformance."""

    def test_fixture_plugin_pack_registration(self, corpus) -> None:
        """Register fixture plugins from a corpus case, verify they exist."""
        from limnalis.plugins.fixtures import register_fixture_plugins

        case = corpus.get_case("A1")
        assert case is not None, "Case A1 not found in corpus"

        reg = PluginRegistry()
        register_fixture_plugins(reg, case)

        # Must have registered at least one evaluator binding
        eval_plugins = reg.list_plugins(EVALUATOR_BINDING)
        assert len(eval_plugins) > 0, "Fixture plugins should register evaluator bindings"

    def test_fixture_plugin_pack_conformance(self, corpus) -> None:
        """Run conformance case A1 through the conformance runner, verify pass."""
        case = corpus.get_case("A1")
        assert case is not None
        result = run_case(case, corpus)
        assert result.error is None, f"Runner error for A1: {result.error}"
        comparison = compare_case(case, result)
        assert comparison.passed, (
            f"A1 conformance failed:\n"
            + "\n".join(str(m) for m in comparison.mismatches)
        )


# ===========================================================================
# 3. Grid Example Plugin Pack Integration
# ===========================================================================


class TestGridPluginPackIntegration:
    """Register grid plugins and run B1 conformance."""

    def test_grid_plugin_pack_registration(self) -> None:
        """Register grid plugins, verify all expected bindings present."""
        from limnalis.plugins.grid_example import register_grid_plugins

        reg = PluginRegistry()
        register_grid_plugins(reg)

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

        # Verify listing order is deterministic
        all_plugins = reg.list_plugins()
        keys = [(m.kind, m.plugin_id) for m in all_plugins]
        assert keys == sorted(keys)

    def test_grid_b1_conformance_pass(self, corpus) -> None:
        """Run B1 through conformance runner, verify case passes."""
        case = corpus.get_case("B1")
        assert case is not None, "Case B1 not found in corpus"
        result = run_case(case, corpus)
        assert result.error is None, f"Runner error for B1: {result.error}"
        comparison = compare_case(case, result)
        assert comparison.passed, (
            f"B1 conformance failed:\n"
            + "\n".join(str(m) for m in comparison.mismatches)
        )


# ===========================================================================
# 4. JWT Example Plugin Pack Integration
# ===========================================================================


class TestJwtPluginPackIntegration:
    """Register JWT plugins and run B2 conformance."""

    def test_jwt_plugin_pack_registration(self) -> None:
        """Register JWT plugins, verify all expected bindings present."""
        from limnalis.plugins.jwt_example import register_jwt_plugins

        reg = PluginRegistry()
        register_jwt_plugins(reg)

        # Evaluator bindings
        assert reg.has(EVALUATOR_BINDING, "ev_gateway::predicate")
        assert reg.has(EVALUATOR_BINDING, "ev_gateway::judged")

        # Support policy
        assert reg.has(EVIDENCE_POLICY, "test://policy/jwt_support_v1")

        # Adequacy methods
        assert reg.has(ADEQUACY_METHOD, "test://method/stateless_access")
        assert reg.has(ADEQUACY_METHOD, "test://method/stateless_revocation")
        assert reg.has(ADEQUACY_METHOD, "test://method/clock_access")
        assert reg.has(ADEQUACY_METHOD, "test://method/jwt_joint_access")

        # Verify listing order is deterministic
        all_plugins = reg.list_plugins()
        keys = [(m.kind, m.plugin_id) for m in all_plugins]
        assert keys == sorted(keys)

    def test_jwt_b2_conformance_pass(self, corpus) -> None:
        """Run B2 through conformance runner, verify case passes."""
        case = corpus.get_case("B2")
        assert case is not None, "Case B2 not found in corpus"
        result = run_case(case, corpus)
        assert result.error is None, f"Runner error for B2: {result.error}"
        comparison = compare_case(case, result)
        assert comparison.passed, (
            f"B2 conformance failed:\n"
            + "\n".join(str(m) for m in comparison.mismatches)
        )


# ===========================================================================
# 5. Installed-Package Plugin Registration
# ===========================================================================


class TestInstalledPackageRegistration:
    """Build services from registry and dispatch via RegistryEvaluatorBindings."""

    def test_build_services_from_registry(self) -> None:
        """Build services dict from registry with grid plugins, verify structure."""
        from limnalis.plugins.grid_example import register_grid_plugins

        reg = PluginRegistry()
        register_grid_plugins(reg)
        services = build_services_from_registry(reg)

        assert "evaluator_bindings" in services
        assert isinstance(services["evaluator_bindings"], RegistryEvaluatorBindings)
        assert "support_policy_handlers" in services
        assert "test://eval/grid_v1" in services["support_policy_handlers"]
        assert "adequacy_handlers" in services
        assert "sim://checks/n1_pred" in services["adequacy_handlers"]

    def test_registry_evaluator_bindings_dispatch(self) -> None:
        """Register evaluator bindings, dispatch via RegistryEvaluatorBindings."""
        from limnalis.plugins.grid_example import (
            grid_predicate_handler,
            grid_causal_handler,
        )

        reg = PluginRegistry()
        reg.register(EVALUATOR_BINDING, "ev_grid::predicate", grid_predicate_handler)
        reg.register(EVALUATOR_BINDING, "ev_grid::causal", grid_causal_handler)

        bindings = RegistryEvaluatorBindings(reg)

        # Successful dispatch
        assert bindings.get_handler("ev_grid", "predicate") is grid_predicate_handler
        assert bindings.get_handler("ev_grid", "causal") is grid_causal_handler

        # Missing dispatch returns None
        assert bindings.get_handler("ev_grid", "nonexistent") is None
        assert bindings.get_handler("no_eval", "predicate") is None


# ===========================================================================
# 6. Consumer Smoke Tests
# ===========================================================================


class TestConsumerSmokeTests:
    """Parse, normalize, and evaluate using only public API."""

    def test_consumer_parse_normalize(self) -> None:
        """Parse and normalize a surface file using only public API."""
        from limnalis.api.parser import LimnalisParser
        from limnalis.api.normalizer import normalize_surface_file

        minimal_lmn = ROOT / "examples" / "minimal_bundle.lmn"
        assert minimal_lmn.exists(), f"Missing fixture: {minimal_lmn}"

        # Parse
        parser = LimnalisParser()
        tree = parser.parse_file(minimal_lmn)
        assert tree is not None

        # Normalize
        result = normalize_surface_file(minimal_lmn, validate_schema=True)
        assert result.canonical_ast is not None
        assert result.canonical_ast.id == "minimal_bundle"

    def test_consumer_evaluate_minimal(self) -> None:
        """Parse, normalize, and run minimal evaluation using public API."""
        from limnalis.api.normalizer import normalize_surface_file
        from limnalis.api.evaluator import (
            run_bundle,
            BundleResult,
            EvaluationEnvironment,
            SessionConfig,
            StepConfig,
        )

        minimal_lmn = ROOT / "examples" / "minimal_bundle.lmn"
        result = normalize_surface_file(minimal_lmn, validate_schema=True)
        assert result.canonical_ast is not None

        sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
        env = EvaluationEnvironment()
        bundle_result = run_bundle(result.canonical_ast, sessions, env)
        assert isinstance(bundle_result, BundleResult)
        assert len(bundle_result.session_results) == 1


# ===========================================================================
# 7. Public Import Validation
# ===========================================================================


# Allowed import prefixes for example plugin packs
_ALLOWED_IMPORT_PREFIXES = (
    "limnalis.api.",
    "limnalis.plugins",
)

# Standard library modules are always allowed (we check positively)
_STDLIB_TOP_LEVEL = frozenset({
    "__future__", "abc", "ast", "asyncio", "base64", "builtins",
    "collections", "contextlib", "copy", "dataclasses", "datetime",
    "enum", "functools", "hashlib", "hmac", "importlib", "inspect",
    "io", "itertools", "json", "logging", "math", "os", "pathlib",
    "re", "secrets", "string", "struct", "sys", "textwrap", "threading",
    "time", "typing", "typing_extensions", "uuid", "warnings",
})


def _get_imports_from_source(source: str) -> list[str]:
    """Extract all import module paths from Python source code."""
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _is_allowed_import(module_path: str) -> bool:
    """Check if a module import is from the public API or stdlib."""
    top_level = module_path.split(".")[0]
    if top_level in _STDLIB_TOP_LEVEL:
        return True
    if top_level != "limnalis":
        # Third-party packages are allowed
        return True
    # Must be from limnalis.api.* or limnalis.plugins
    return any(module_path.startswith(prefix) for prefix in _ALLOWED_IMPORT_PREFIXES)


class TestPublicImportValidation:
    """Verify example plugin packs use only public imports."""

    @pytest.mark.parametrize(
        "module_name,module_path",
        [
            ("grid_example", "limnalis.plugins.grid_example"),
            ("jwt_example", "limnalis.plugins.jwt_example"),
        ],
    )
    def test_example_packs_use_only_public_imports(
        self, module_name: str, module_path: str
    ) -> None:
        """Verify grid_example.py and jwt_example.py don't import internal modules."""
        import importlib

        mod = importlib.import_module(module_path)
        source = inspect.getsource(mod)
        imports = _get_imports_from_source(source)

        violations = [imp for imp in imports if not _is_allowed_import(imp)]
        assert violations == [], (
            f"{module_name} imports non-public modules: {violations}\n"
            f"All imports must be from limnalis.api.* or limnalis.plugins.*"
        )


# ===========================================================================
# 8. Determinism Checks
# ===========================================================================


class TestDeterminismChecks:
    """Verify plugin listing and service building are deterministic."""

    def test_plugin_listing_deterministic(self) -> None:
        """Verify plugin listing order is deterministic across multiple calls."""
        from limnalis.plugins.grid_example import register_grid_plugins
        from limnalis.plugins.jwt_example import register_jwt_plugins

        reg = PluginRegistry()
        register_grid_plugins(reg)
        register_jwt_plugins(reg)

        listings = []
        for _ in range(5):
            result = reg.list_plugins()
            keys = [(m.kind, m.plugin_id) for m in result]
            listings.append(keys)

        for i in range(1, len(listings)):
            assert listings[i] == listings[0], (
                f"Listing order changed on call {i}: {listings[i]} != {listings[0]}"
            )

    def test_plugin_services_deterministic(self) -> None:
        """Verify build_services_from_registry produces identical results."""
        from limnalis.plugins.grid_example import register_grid_plugins

        reg = PluginRegistry()
        register_grid_plugins(reg)

        results = []
        for _ in range(5):
            services = build_services_from_registry(reg)
            # Check structure is consistent
            result_keys = sorted(services.keys())
            policy_keys = sorted(services.get("support_policy_handlers", {}).keys())
            adequacy_keys = sorted(services.get("adequacy_handlers", {}).keys())
            results.append((result_keys, policy_keys, adequacy_keys))

        for i in range(1, len(results)):
            assert results[i] == results[0], (
                f"Service structure changed on call {i}: {results[i]} != {results[0]}"
            )
