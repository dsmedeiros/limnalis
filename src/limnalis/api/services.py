"""Stable public API for the Limnalis plugin registry and services.

Plugin registration, lookup, and service construction for extension authors.
"""

from __future__ import annotations

from ..plugins import (
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
