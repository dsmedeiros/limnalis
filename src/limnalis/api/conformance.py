"""Stable public API for the Limnalis conformance harness.

Imports from this module are supported across patch releases.
"""

from __future__ import annotations

from ..conformance import (
    FixtureCase,
    compare_case,
    load_corpus,
    load_corpus_from_default,
    run_case,
)

__all__ = [
    "FixtureCase",
    "compare_case",
    "load_corpus",
    "load_corpus_from_default",
    "run_case",
]
