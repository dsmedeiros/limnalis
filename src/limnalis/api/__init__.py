"""Stable public API surface for the Limnalis reference implementation.

All imports from submodules of ``limnalis.api`` are considered stable and
supported across patch releases within the same minor version.  Internal
module paths (e.g. ``limnalis.normalizer``, ``limnalis.runtime.runner``)
are implementation details and may change without notice.

Submodules:
    parser       -- Surface-language parsing
    normalizer   -- AST normalization pipeline
    evaluator    -- Step runner / evaluation engine
    conformance  -- Fixture-based conformance harness
    plugins      -- Extension protocols and types for plugin authors
    context      -- Context and state types for plugin implementations
    results      -- Result types for plugin implementations
    models       -- AST model types for plugin authors
"""

from __future__ import annotations

from . import conformance, context, evaluator, models, normalizer, parser, plugins, results, services

__all__ = [
    "conformance",
    "context",
    "evaluator",
    "models",
    "normalizer",
    "parser",
    "plugins",
    "results",
    "services",
]
