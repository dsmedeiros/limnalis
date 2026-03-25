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
"""

from __future__ import annotations

from . import conformance, evaluator, normalizer, parser

__all__ = [
    "conformance",
    "evaluator",
    "normalizer",
    "parser",
]
