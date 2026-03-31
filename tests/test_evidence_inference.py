"""Tests for the evidence inference layer (T4 Part A)."""

from __future__ import annotations

import pytest

from limnalis.models.ast import (
    EvidenceNode,
    EvidenceRelationNode,
    InferredEvidenceRelation,
)
from limnalis.runtime.builtins import (
    TransitivityInferencePolicy,
    build_evidence_view_with_inference,
    get_builtin_inference_policies,
    get_evidence_view_combined,
)
from limnalis.runtime.models import ClaimEvidenceView


# ===================================================================
# Helpers
# ===================================================================


def _evidence(id: str, kind: str = "measurement") -> EvidenceNode:
    return EvidenceNode(id=id, kind=kind, binding=f"binding_{id}")


def _relation(
    id: str, lhs: str, rhs: str, kind: str = "corroborates", score: float | None = None
) -> EvidenceRelationNode:
    return EvidenceRelationNode(id=id, lhs=lhs, rhs=rhs, kind=kind, score=score)


# ===================================================================
# TransitivityInferencePolicy
# ===================================================================


class TestTransitivityInference:
    def test_transitivity_conflicts_infers_corroborates(self):
        """A conflicts B, B conflicts C -> infers A corroborates C."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "conflicts", score=0.8),
            _relation("r2", "B", "C", "conflicts", score=0.9),
        ]
        policy = TransitivityInferencePolicy()

        inferred = policy.infer(evidence, relations, {})

        assert len(inferred) >= 1
        corr = [r for r in inferred if r.kind == "corroborates"]
        assert len(corr) >= 1
        # Should connect A and C
        pair = {corr[0].lhs, corr[0].rhs}
        assert pair == {"A", "C"}

    def test_transitivity_corroborates_chain(self):
        """A corroborates B, B corroborates C -> infers A corroborates C."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "corroborates", score=0.7),
            _relation("r2", "B", "C", "corroborates", score=0.8),
        ]
        policy = TransitivityInferencePolicy()

        inferred = policy.infer(evidence, relations, {})

        assert len(inferred) >= 1
        pair = {inferred[0].lhs, inferred[0].rhs}
        assert pair == {"A", "C"}
        assert inferred[0].kind == "corroborates"

    def test_transitivity_confidence_product(self):
        """Verify confidence is product of scores."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "corroborates", score=0.6),
            _relation("r2", "B", "C", "corroborates", score=0.5),
        ]
        policy = TransitivityInferencePolicy()

        inferred = policy.infer(evidence, relations, {})

        assert len(inferred) >= 1
        assert inferred[0].confidence == pytest.approx(0.3, abs=1e-6)

    def test_transitivity_no_self_inference(self):
        """No inference from a relation to itself."""
        evidence = [_evidence("A"), _evidence("B")]
        relations = [
            _relation("r1", "A", "B", "corroborates", score=0.8),
        ]
        policy = TransitivityInferencePolicy()

        inferred = policy.infer(evidence, relations, {})

        # Only one relation, no transitive chain possible
        assert len(inferred) == 0


# ===================================================================
# Inference policy integration
# ===================================================================


class TestInferencePolicyNone:
    def test_inference_policy_none_returns_declared_only(self):
        """None policy means no inferred relations."""
        evidence = [_evidence("E1"), _evidence("E2")]
        relations = [_relation("r1", "E1", "E2", "corroborates")]

        view, inferred, diags = build_evidence_view_with_inference(
            "c1", evidence, relations, None, {}
        )

        assert len(inferred) == 0
        assert isinstance(view, ClaimEvidenceView)


# ===================================================================
# build_evidence_view_with_inference
# ===================================================================


class TestBuildEvidenceViewWithInference:
    def test_build_evidence_view_with_inference(self):
        """Full pipeline test."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "conflicts", score=0.8),
            _relation("r2", "B", "C", "conflicts", score=0.9),
        ]
        policy = TransitivityInferencePolicy()

        view, inferred, diags = build_evidence_view_with_inference(
            "c1", evidence, relations, policy, {}
        )

        assert isinstance(view, ClaimEvidenceView)
        assert view.claim_id == "c1"
        assert len(inferred) >= 1

    def test_inferred_relations_not_in_evidence_view(self):
        """Verify inferred NOT in ClaimEvidenceView.relations."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "corroborates", score=0.7),
            _relation("r2", "B", "C", "corroborates", score=0.8),
        ]
        policy = TransitivityInferencePolicy()

        view, inferred, diags = build_evidence_view_with_inference(
            "c1", evidence, relations, policy, {}
        )

        # view.relations should only contain declared relations
        view_rel_ids = {r.id for r in view.relations}
        inferred_ids = {r.id for r in inferred}
        assert view_rel_ids.isdisjoint(inferred_ids)

    def test_get_evidence_view_combined(self):
        """Verify combined dict structure."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "conflicts", score=0.8),
            _relation("r2", "B", "C", "conflicts", score=0.9),
        ]
        policy = TransitivityInferencePolicy()

        view, inferred, _ = build_evidence_view_with_inference(
            "c1", evidence, relations, policy, {}
        )
        combined = get_evidence_view_combined(view, inferred)

        assert "declared_only" in combined
        assert "inferred" in combined
        assert "combined_relations" in combined
        assert isinstance(combined["declared_only"], ClaimEvidenceView)
        assert len(combined["combined_relations"]) == len(view.relations) + len(inferred)

    def test_inferred_relation_has_declared_false(self):
        """All inferred have declared=False."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "corroborates", score=0.7),
            _relation("r2", "B", "C", "corroborates", score=0.8),
        ]
        policy = TransitivityInferencePolicy()

        _, inferred, _ = build_evidence_view_with_inference(
            "c1", evidence, relations, policy, {}
        )

        for rel in inferred:
            assert rel.declared is False

    def test_inference_provenance(self):
        """Verify provenance traces source relations."""
        evidence = [_evidence("A"), _evidence("B"), _evidence("C")]
        relations = [
            _relation("r1", "A", "B", "conflicts", score=0.8),
            _relation("r2", "B", "C", "conflicts", score=0.9),
        ]
        policy = TransitivityInferencePolicy()

        _, inferred, _ = build_evidence_view_with_inference(
            "c1", evidence, relations, policy, {}
        )

        assert len(inferred) >= 1
        for rel in inferred:
            assert len(rel.provenance) > 0
            # Provenance should reference the source relation ids
            prov_text = " ".join(rel.provenance)
            assert "r1" in prov_text or "r2" in prov_text
