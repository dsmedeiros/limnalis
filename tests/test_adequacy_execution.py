"""Tests for the stronger adequacy execution (T4 Part B)."""

from __future__ import annotations

import pytest

from limnalis.models.ast import AdequacyAssessmentNode
from limnalis.models.conformance import AdequacyExecutionTrace, BasisResolutionEntry
from limnalis.runtime.builtins import (
    aggregate_contested_adequacy,
    detect_basis_circularity,
    execute_adequacy_with_basis,
)
from limnalis.runtime.models import EvalNode


# ===================================================================
# Helpers
# ===================================================================


def _assessment(
    id: str = "aa1",
    task: str = "task1",
    producer: str = "ev1",
    score: float | None = 0.8,
    threshold: float = 0.5,
    method: str = "standard",
    basis: list[str] | None = None,
) -> AdequacyAssessmentNode:
    return AdequacyAssessmentNode(
        id=id,
        task=task,
        producer=producer,
        score=score,
        threshold=threshold,
        method=method,
        basis=basis or [],
    )


# ===================================================================
# execute_adequacy_with_basis
# ===================================================================


class TestExecuteAdequacyWithBasis:
    def test_execute_adequacy_with_basis_adequate(self):
        """Score >= threshold -> adequate=True."""
        aa = _assessment(score=0.8, threshold=0.5, basis=["c1"])
        basis_results = {"c1": EvalNode(truth="T")}

        trace, diags = execute_adequacy_with_basis(aa, ["c1"], basis_results, {})

        assert isinstance(trace, AdequacyExecutionTrace)
        assert trace.adequate is True
        assert trace.failure_kind is None or trace.failure_kind == "threshold"

    def test_execute_adequacy_with_basis_inadequate(self):
        """Score < threshold -> adequate=False."""
        aa = _assessment(score=0.3, threshold=0.5, basis=["c1"])
        basis_results = {"c1": EvalNode(truth="T")}

        trace, diags = execute_adequacy_with_basis(aa, ["c1"], basis_results, {})

        assert trace.adequate is False
        assert trace.failure_kind == "threshold"

    def test_execute_adequacy_basis_resolution(self):
        """Verify BasisResolutionEntry for each basis item."""
        aa = _assessment(basis=["c1", "c2"])
        basis_results = {
            "c1": EvalNode(truth="T"),
            "c2": EvalNode(truth="F"),
        }

        trace, diags = execute_adequacy_with_basis(
            aa, ["c1", "c2"], basis_results, {}
        )

        assert len(trace.basis_resolution) == 2
        for entry in trace.basis_resolution:
            assert isinstance(entry, BasisResolutionEntry)
            assert entry.resolved is True

    def test_execute_adequacy_method_binding(self):
        """Custom method binding in services."""
        aa = _assessment(
            score=0.8, threshold=0.5, method="custom_method", basis=["c1"]
        )
        basis_results = {"c1": EvalNode(truth="T")}

        def custom_handler(assessment):
            return 0.9

        services = {"adequacy_handlers": {"custom_method": custom_handler}}

        trace, diags = execute_adequacy_with_basis(
            aa, ["c1"], basis_results, services
        )

        assert trace.computed_score == 0.9
        assert trace.adequate is True

    def test_execute_adequacy_circular_basis(self):
        """Self-referencing basis -> failure_kind='circular_basis'."""
        aa = _assessment(id="aa_circ", basis=["aa_circ"])
        basis_results = {}

        trace, diags = execute_adequacy_with_basis(
            aa, ["aa_circ"], basis_results, {}
        )

        assert trace.adequate is False
        assert trace.failure_kind == "circular_basis"

    def test_execute_adequacy_unresolved_basis(self):
        """Missing basis claim -> failure_kind='basis_failure'."""
        aa = _assessment(basis=["c_missing"])
        basis_results = {}  # c_missing not present

        trace, diags = execute_adequacy_with_basis(
            aa, ["c_missing"], basis_results, {}
        )

        assert trace.adequate is False
        assert trace.failure_kind == "basis_failure"


# ===================================================================
# aggregate_contested_adequacy
# ===================================================================


class TestContestedAdequacy:
    def test_contested_adequacy_single(self):
        """Resolution 'single' uses first assessment."""
        aa1 = _assessment(id="aa1", score=0.8, threshold=0.5)
        aa2 = _assessment(id="aa2", score=0.3, threshold=0.5)
        basis_results = {}

        trace, diags = aggregate_contested_adequacy(
            [aa1, aa2], basis_results, "single", {}
        )

        # Single uses first assessment
        assert trace.assessment_id == "aa1"
        assert trace.adequate is True

    def test_contested_adequacy_paraconsistent_agree(self):
        """All agree -> consolidated result."""
        aa1 = _assessment(id="aa1", score=0.8, threshold=0.5)
        aa2 = _assessment(id="aa2", score=0.7, threshold=0.5)
        basis_results = {}

        trace, diags = aggregate_contested_adequacy(
            [aa1, aa2], basis_results, "paraconsistent_union", {}
        )

        assert trace.adequate is True
        assert trace.failure_kind is None

    def test_contested_adequacy_paraconsistent_disagree(self):
        """Disagree -> failure_kind='method_conflict'."""
        aa1 = _assessment(id="aa1", score=0.8, threshold=0.5)
        aa2 = _assessment(id="aa2", score=0.3, threshold=0.5)
        basis_results = {}

        trace, diags = aggregate_contested_adequacy(
            [aa1, aa2], basis_results, "paraconsistent_union", {}
        )

        assert trace.adequate is False
        assert trace.failure_kind == "method_conflict"

    def test_contested_adequacy_priority_order(self):
        """Priority order: first adequate wins."""
        aa1 = _assessment(id="aa1", score=0.3, threshold=0.5)  # inadequate
        aa2 = _assessment(id="aa2", score=0.8, threshold=0.5)  # adequate
        basis_results = {}

        trace, diags = aggregate_contested_adequacy(
            [aa1, aa2], basis_results, "priority_order", {}
        )

        assert trace.adequate is True
        assert trace.assessment_id == "aa2"

    def test_contested_adequacy_adjudicated_fallback(self):
        """No adjudicator -> falls back to paraconsistent."""
        aa1 = _assessment(id="aa1", score=0.8, threshold=0.5)
        aa2 = _assessment(id="aa2", score=0.3, threshold=0.5)
        basis_results = {}
        services: dict = {}  # no adjudicator

        trace, diags = aggregate_contested_adequacy(
            [aa1, aa2], basis_results, "adjudicated", services
        )

        # Falls back to paraconsistent, which disagrees
        assert trace.adequate is False
        assert trace.failure_kind == "method_conflict"


# ===================================================================
# detect_basis_circularity
# ===================================================================


class TestDetectBasisCircularity:
    def test_detect_basis_circularity_positive(self):
        """Circular -> True."""
        aa = _assessment(id="aa_circ", basis=["aa_circ"])

        is_circular, diags = detect_basis_circularity(aa)

        assert is_circular is True
        assert len(diags) >= 1
        assert diags[0]["code"] == "circular_basis"

    def test_detect_basis_circularity_negative(self):
        """Non-circular -> False."""
        aa = _assessment(id="aa1", basis=["c1", "c2"])

        is_circular, diags = detect_basis_circularity(aa)

        assert is_circular is False
        assert len(diags) == 0
