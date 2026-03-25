"""Property-based tests for four-valued logic, block fold, and exact-set matching.

T7: Determinism + property tests (property-based portion).
Uses Hypothesis for property testing.
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import given, settings
from hypothesis import strategies as st

from limnalis.runtime.builtins import (
    _TRUTH_JOIN,
    _aggregate_truth,
    _fold_block_truth,
)

# Strategy: sample from the four truth values
truth_values = st.sampled_from(["met", "unmet", "not_applicable", "unresolved"])

# The runtime uses single-letter abbreviations internally
truth_values_abbrev = st.sampled_from(["T", "F", "N", "B"])


# ---------------------------------------------------------------------------
# Four-valued logic connectives via the paraconsistent join lattice
# ---------------------------------------------------------------------------


class TestFourValuedLogicProperties:
    """Property tests for the four-valued truth join lattice."""

    @given(a=truth_values_abbrev, b=truth_values_abbrev)
    def test_join_is_commutative(self, a: str, b: str) -> None:
        """AND (join) is commutative: a JOIN b == b JOIN a."""
        assert _TRUTH_JOIN[(a, b)] == _TRUTH_JOIN[(b, a)]

    @given(a=truth_values_abbrev, b=truth_values_abbrev, c=truth_values_abbrev)
    def test_join_is_associative(self, a: str, b: str, c: str) -> None:
        """JOIN is associative: (a JOIN b) JOIN c == a JOIN (b JOIN c)."""
        left = _TRUTH_JOIN[(_TRUTH_JOIN[(a, b)], c)]
        right = _TRUTH_JOIN[(a, _TRUTH_JOIN[(b, c)])]
        assert left == right

    @given(a=truth_values_abbrev)
    def test_join_identity_element_N(self, a: str) -> None:
        """N is the identity element for JOIN: a JOIN N == a."""
        assert _TRUTH_JOIN[(a, "N")] == a

    @given(a=truth_values_abbrev)
    def test_join_annihilator_B(self, a: str) -> None:
        """B is the annihilator for JOIN: a JOIN B == B for all a."""
        # B absorbs everything in the join lattice (including N JOIN B = B)
        assert _TRUTH_JOIN[(a, "B")] == "B"

    @given(a=truth_values_abbrev)
    def test_join_is_idempotent(self, a: str) -> None:
        """JOIN is idempotent: a JOIN a == a."""
        assert _TRUTH_JOIN[(a, a)] == a

    @given(
        values=st.lists(truth_values_abbrev, min_size=1, max_size=10),
        rng=st.randoms(use_true_random=False),
    )
    def test_aggregate_truth_commutative(self, values: list[str], rng) -> None:
        """_aggregate_truth is order-independent (commutative fold)."""
        result1 = _aggregate_truth(values)
        shuffled = values.copy()
        rng.shuffle(shuffled)
        result2 = _aggregate_truth(shuffled)
        assert result1 == result2

    def test_aggregate_truth_empty(self) -> None:
        """Empty list yields N."""
        assert _aggregate_truth([]) == "N"


# ---------------------------------------------------------------------------
# Block fold operations
# ---------------------------------------------------------------------------


class TestBlockFoldProperties:
    """Property tests for block fold truth aggregation."""

    @given(
        values=st.lists(truth_values_abbrev, min_size=1, max_size=10),
        rng=st.randoms(use_true_random=False),
    )
    def test_fold_block_truth_order_independent(self, values: list[str], rng) -> None:
        """Block fold truth is order-independent for the same set of values."""
        result1 = _fold_block_truth(values)
        shuffled = values.copy()
        rng.shuffle(shuffled)
        result2 = _fold_block_truth(shuffled)
        assert result1 == result2

    def test_fold_block_truth_empty(self) -> None:
        """Empty list yields N."""
        assert _fold_block_truth([]) == "N"

    @given(values=st.lists(st.just("T"), min_size=1, max_size=5))
    def test_fold_all_T_yields_T(self, values: list[str]) -> None:
        """If all truths are T, block truth is T."""
        assert _fold_block_truth(values) == "T"

    @given(
        values=st.lists(truth_values_abbrev, min_size=1, max_size=5).filter(
            lambda vs: "F" in vs
        )
    )
    def test_fold_with_F_yields_F(self, values: list[str]) -> None:
        """If any truth is F, block truth is F."""
        assert _fold_block_truth(values) == "F"

    @given(
        values=st.lists(
            st.sampled_from(["T", "B", "N"]), min_size=2, max_size=5
        ).filter(lambda vs: "B" in vs and "N" in vs)
    )
    def test_fold_B_and_N_yields_F(self, values: list[str]) -> None:
        """If both B and N are present (no F), block truth is F."""
        assert _fold_block_truth(values) == "F"


