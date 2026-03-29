"""Limnalis plugin registry -- register and discover extension bindings.

Plugin authors register handlers by kind and ID. The registry provides
deterministic lookup and clean error diagnostics for missing plugins.
"""

from __future__ import annotations

import dataclasses
import warnings
from typing import Any


# ---------------------------------------------------------------------------
# Plugin kind constants
# ---------------------------------------------------------------------------

EVALUATOR_BINDING = "evaluator_binding"
CRITERION_BINDING = "criterion_binding"
EVIDENCE_POLICY = "evidence_policy"
ADEQUACY_METHOD = "adequacy_method"
ADJUDICATOR = "adjudicator"
TRANSPORT_HANDLER = "transport_handler"
BASELINE_HANDLER = "baseline_handler"
BINDING_RESOLVER = "binding_resolver"


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class PluginError(Exception):
    """Base error for plugin operations."""


class PluginNotFoundError(PluginError):
    """Raised when a plugin lookup fails."""

    def __init__(self, kind: str, plugin_id: str):
        self.kind = kind
        self.plugin_id = plugin_id
        super().__init__(f"No plugin registered: kind={kind!r}, id={plugin_id!r}")


class PluginConflictError(PluginError):
    """Raised when a duplicate plugin is registered."""

    def __init__(self, kind: str, plugin_id: str):
        self.kind = kind
        self.plugin_id = plugin_id
        super().__init__(f"Plugin already registered: kind={kind!r}, id={plugin_id!r}")


# ---------------------------------------------------------------------------
# PluginMetadata
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PluginMetadata:
    """Metadata for a registered plugin."""

    kind: str
    plugin_id: str
    handler: Any
    version: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------


class PluginRegistry:
    """Registry for Limnalis extension plugins.

    Supports registering and looking up handlers by kind and ID.
    Not thread-safe for concurrent registration; intended for
    single-threaded plugin setup before evaluation begins.
    """

    def __init__(self) -> None:
        self._plugins: dict[tuple[str, str], PluginMetadata] = {}

    # -- mutation -----------------------------------------------------------

    def register(
        self,
        kind: str,
        plugin_id: str,
        handler: Any,
        *,
        version: str = "",
        description: str = "",
    ) -> None:
        """Register a plugin. Raises PluginConflictError on duplicate (kind, plugin_id)."""
        key = (kind, plugin_id)
        if key in self._plugins:
            raise PluginConflictError(kind, plugin_id)
        self._plugins[key] = PluginMetadata(
            kind=kind,
            plugin_id=plugin_id,
            handler=handler,
            version=version,
            description=description,
        )

    def unregister(self, kind: str, plugin_id: str) -> None:
        """Remove a plugin. Raises PluginNotFoundError if missing."""
        key = (kind, plugin_id)
        if key not in self._plugins:
            raise PluginNotFoundError(kind, plugin_id)
        del self._plugins[key]

    def clear(self) -> None:
        """Remove all plugins (useful for test teardown)."""
        self._plugins.clear()

    # -- lookup -------------------------------------------------------------

    def get(self, kind: str, plugin_id: str) -> Any:
        """Get handler. Raises PluginNotFoundError if missing."""
        key = (kind, plugin_id)
        if key not in self._plugins:
            raise PluginNotFoundError(kind, plugin_id)
        return self._plugins[key].handler

    def get_metadata(self, kind: str, plugin_id: str) -> PluginMetadata:
        """Get full metadata. Raises PluginNotFoundError."""
        key = (kind, plugin_id)
        if key not in self._plugins:
            raise PluginNotFoundError(kind, plugin_id)
        return self._plugins[key]

    def has(self, kind: str, plugin_id: str) -> bool:
        """Check if registered."""
        return (kind, plugin_id) in self._plugins

    # -- enumeration --------------------------------------------------------

    def list_plugins(self, kind: str | None = None) -> list[PluginMetadata]:
        """List all plugins, optionally filtered by kind. Returns deterministic (sorted) order."""
        entries = self._plugins.values()
        if kind is not None:
            entries = [m for m in entries if m.kind == kind]
        return sorted(entries, key=lambda m: (m.kind, m.plugin_id))

    def kinds(self) -> list[str]:
        """List all registered kinds (sorted)."""
        return sorted({k for k, _ in self._plugins})


# ---------------------------------------------------------------------------
# RegistryEvaluatorBindings
# ---------------------------------------------------------------------------


class RegistryEvaluatorBindings:
    """EvaluatorBindings implementation backed by the plugin registry.

    Plugin IDs for evaluator_binding kind should use the format:
    ``"evaluator_id::expr_type"`` (e.g., ``"grid_eval_v1::predicate"``).
    """

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    @staticmethod
    def _normalize_expr_type(expr_type: str) -> str:
        """Normalize AST/node expression names to evaluator binding plugin IDs."""
        normalized = (expr_type or "").strip()
        mapping = {
            "PredicateExpr": "predicate",
            "CausalExpr": "causal",
            "EmergenceExpr": "emergence",
            "JudgedExpr": "judged",
        }
        return mapping.get(normalized, normalized.lower())

    def get_handler(self, evaluator_id: str, expr_type: str) -> Any | None:
        """Return a handler for the given evaluator and expression type, or None."""
        plugin_id = f"{evaluator_id}::{self._normalize_expr_type(expr_type)}"
        if self._registry.has(EVALUATOR_BINDING, plugin_id):
            return self._registry.get(EVALUATOR_BINDING, plugin_id)
        return None


# ---------------------------------------------------------------------------
# build_services_from_registry
# ---------------------------------------------------------------------------


def build_services_from_registry(registry: PluginRegistry) -> dict[str, Any]:
    """Build a services dict from registered plugins.

    Collects plugin handlers from the registry into the format expected
    by ``run_bundle`` / ``run_session`` / ``run_step``.

    **Wired plugin kinds** (automatically included in the returned dict):

    - ``EVALUATOR_BINDING`` -- wrapped in a :class:`RegistryEvaluatorBindings`
      and set as ``services["evaluator_bindings"]``.
    - ``EVIDENCE_POLICY`` -- collected into
      ``services["support_policy_handlers"]``.
    - ``ADEQUACY_METHOD`` -- collected into ``services["adequacy_handlers"]``.
    - ``ADJUDICATOR`` -- if exactly one adjudicator is registered, set as
      ``services["adjudicator"]``.  If multiple are registered the consumer
      must select one explicitly (a warning is emitted).

    **Registry-only plugin kinds** (available via ``registry.get()`` but *not*
    automatically wired here -- consumers must retrieve them directly):

    - ``CRITERION_BINDING``
    - ``TRANSPORT_HANDLER``
    - ``BASELINE_HANDLER``
    - ``BINDING_RESOLVER``

    Returns:
        A services dict ready to pass to the evaluation runner.
    """
    services: dict[str, Any] = {}

    # Evaluator bindings
    if registry.list_plugins(EVALUATOR_BINDING):
        services["evaluator_bindings"] = RegistryEvaluatorBindings(registry)

    # Support policy handlers (evidence_policy kind)
    policy_plugins = registry.list_plugins(EVIDENCE_POLICY)
    if policy_plugins:
        services["support_policy_handlers"] = {
            m.plugin_id: m.handler for m in policy_plugins
        }

    # Adequacy handlers
    adequacy_plugins = registry.list_plugins(ADEQUACY_METHOD)
    if adequacy_plugins:
        services["adequacy_handlers"] = {
            m.plugin_id: m.handler for m in adequacy_plugins
        }

    # Adjudicator -- wire automatically when exactly one is registered.
    adjudicator_plugins = registry.list_plugins(ADJUDICATOR)
    if len(adjudicator_plugins) == 1:
        services["adjudicator"] = adjudicator_plugins[0].handler
    elif len(adjudicator_plugins) > 1:
        warnings.warn(
            (
                "Multiple adjudicator plugins are registered; skipping auto-wiring "
                "for services['adjudicator']. Select an adjudicator explicitly."
            ),
            stacklevel=2,
        )

    return services


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Kind constants
    "EVALUATOR_BINDING",
    "CRITERION_BINDING",
    "EVIDENCE_POLICY",
    "ADEQUACY_METHOD",
    "ADJUDICATOR",
    "TRANSPORT_HANDLER",
    "BASELINE_HANDLER",
    "BINDING_RESOLVER",
    # Errors
    "PluginError",
    "PluginNotFoundError",
    "PluginConflictError",
    # Core types
    "PluginMetadata",
    "PluginRegistry",
    "RegistryEvaluatorBindings",
    # Helpers
    "build_services_from_registry",
]
