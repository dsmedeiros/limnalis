"""Conformance harness: fixture loading, execution, and result comparison."""

from __future__ import annotations

from .compare import compare_case
from .fixtures import FixtureCase, load_corpus, load_corpus_from_default
from .runner import run_case

__all__ = [
    "FixtureCase",
    "compare_case",
    "load_corpus",
    "load_corpus_from_default",
    "run_case",
]
