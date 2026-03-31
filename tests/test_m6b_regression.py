"""Regression coverage for M6B changes."""

from __future__ import annotations

import pytest

from limnalis.conformance.fixtures import load_corpus_from_default
from limnalis.conformance.runner import run_case
from limnalis.conformance.compare import compare_case
from limnalis.models.ast import (
    ClaimBlockNode,
    ClaimNode,
    PredicateExprNode,
    ResolutionPolicyNode,
)
from limnalis.runtime.builtins import (
    compose_license,
    fold_block,
)
from limnalis.runtime.models import (
    ClaimClassification,
    EvalNode,
)


# ===================================================================
# Existing corpus stability
# ===================================================================


@pytest.fixture(scope="module")
def corpus():
    return load_corpus_from_default()


class TestExistingCorpusStable:
    def test_existing_corpus_stable(self, corpus):
        """Load and run all existing conformance cases, verify they still pass."""
        failures = []
        for case_id in corpus.case_ids():
            case = corpus.get_case(case_id)
            if case is None:
                continue
            result = run_case(case, corpus)
            if result.error is not None:
                failures.append(f"{case_id}: runner error: {result.error}")
                continue
            comparison = compare_case(case, result)
            if not comparison.passed:
                details = "; ".join(str(m) for m in comparison.mismatches[:3])
                failures.append(f"{case_id}: {details}")

        assert len(failures) == 0, (
            f"{len(failures)} conformance case(s) failed:\n"
            + "\n".join(failures)
        )


# ===================================================================
# fold_block unchanged
# ===================================================================


class TestFoldBlockUnchanged:
    def test_fold_block_unchanged(self):
        """Verify fold_block produces same results as before with known inputs."""
        claim1 = ClaimNode(
            id="c1", kind="atomic", expr=PredicateExprNode(name="P")
        )
        claim2 = ClaimNode(
            id="c2", kind="atomic", expr=PredicateExprNode(name="Q")
        )
        block = ClaimBlockNode(id="blk1", stratum="local", claims=[claim1, claim2])

        per_claim_agg = {
            "c1": EvalNode(truth="T", provenance=["c1"]),
            "c2": EvalNode(truth="F", provenance=["c2"]),
        }
        per_claim_per_ev = {
            "c1": {"ev1": EvalNode(truth="T", provenance=["ev1", "c1"])},
            "c2": {"ev1": EvalNode(truth="F", provenance=["ev1", "c2"])},
        }
        classifications = {
            "c1": ClaimClassification(claim_id="c1", evaluable=True, expr_kind="PredicateExpr"),
            "c2": ClaimClassification(claim_id="c2", evaluable=True, expr_kind="PredicateExpr"),
        }
        policy = ResolutionPolicyNode(id="pol", kind="single", members=["ev1"])

        per_ev_block, aggregate = fold_block(
            block, per_claim_agg, per_claim_per_ev, classifications, policy
        )

        # With T and F claims, fold should yield F for ev1 (worst truth)
        assert per_ev_block["ev1"].truth == "F"
        assert aggregate.truth == "F"


# ===================================================================
# Severity order not shadowed
# ===================================================================


class TestSeverityOrderNotShadowed:
    def test_severity_order_not_shadowed(self):
        """Verify compose_license _SEVERITY_ORDER is correct (F=3 highest)."""
        from limnalis.runtime.builtins import _SEVERITY_ORDER

        # F should have the highest severity rank
        assert _SEVERITY_ORDER["F"] == 3
        assert _SEVERITY_ORDER["B"] == 2
        assert _SEVERITY_ORDER["N"] == 1
        assert _SEVERITY_ORDER["T"] == 0

        # Verify ordering is strictly increasing in severity
        assert _SEVERITY_ORDER["T"] < _SEVERITY_ORDER["N"]
        assert _SEVERITY_ORDER["N"] < _SEVERITY_ORDER["B"]
        assert _SEVERITY_ORDER["B"] < _SEVERITY_ORDER["F"]
