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
    summary      -- Summary policy framework (M6B)
    evidence     -- Evidence inference layer (M6B)
    adequacy     -- Adequacy execution with basis resolution (M6B)
    transport    -- Transport chain extensions (M6B)
"""

from __future__ import annotations

from . import (
    adequacy,
    conformance,
    context,
    evaluator,
    evidence,
    models,
    normalizer,
    parser,
    plugins,
    results,
    services,
    summary,
    transport,
)

__all__ = [
    "adequacy",
    "conformance",
    "context",
    "evaluator",
    "evidence",
    "models",
    "normalizer",
    "parser",
    "plugins",
    "results",
    "services",
    "summary",
    "transport",
]
