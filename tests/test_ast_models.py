from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from limnalis.models.ast import (
    AnchorNode,
    AnchorTermSymbolNode,
    BaselineNode,
    BundleNode,
    ClaimBlockNode,
    ClaimNode,
    CriterionRefNode,
    DynamicExprNode,
    EvaluatorNode,
    FrameNode,
    JointAdequacyNode,
    PredicateExprNode,
    ResolutionPolicyNode,
    SymbolTermNode,
    TransportNode,
)
from limnalis.schema import validate_payload

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "examples"


def test_minimal_bundle_model_validates_against_schema() -> None:
    payload = json.loads((FIXTURE_ROOT / "minimal_bundle_ast.json").read_text(encoding="utf-8"))
    bundle = BundleNode.model_validate(payload)
    dumped = bundle.to_schema_data()
    validate_payload(dumped, "ast")


def test_direct_model_defaults_round_trip_through_schema() -> None:
    bundle = BundleNode(
        node="Bundle",
        id="direct_bundle",
        frame=FrameNode(
            node="Frame",
            system="Test",
            namespace="Direct",
            scale="unit",
            task="check",
            regime="nominal",
        ),
        evaluators=[
            EvaluatorNode(node="Evaluator", id="ev0", kind="model", binding="test://eval/direct")
        ],
        resolutionPolicy=ResolutionPolicyNode(
            node="ResolutionPolicy", id="rp0", kind="single", members=["ev0"]
        ),
        anchors=[
            AnchorNode(
                node="Anchor",
                id="a1",
                term=AnchorTermSymbolNode(kind="symbol", value="reactive_margin"),
                subtype="proxy",
                status="active",
            )
        ],
        claimBlocks=[
            ClaimBlockNode(
                node="ClaimBlock",
                id="local#1",
                stratum="local",
                claims=[
                    ClaimNode(
                        node="Claim",
                        id="c1",
                        kind="atomic",
                        expr=PredicateExprNode(node="PredicateExpr", name="p"),
                    )
                ],
            )
        ],
    )

    dumped = bundle.to_schema_data()

    assert dumped["anchors"][0]["adequacy"] == []
    assert dumped["claimBlocks"][0]["claims"][0]["expr"]["args"] == []
    validate_payload(dumped, "ast")


def test_resolution_policy_single_requires_exactly_one_member() -> None:
    with pytest.raises(ValidationError):
        ResolutionPolicyNode(node="ResolutionPolicy", id="rp", kind="single", members=["a", "b"])


def test_transport_remap_requires_claim_map() -> None:
    with pytest.raises(ValidationError):
        TransportNode(node="Transport", mode="remap_recompute")


def test_transport_metadata_only_rejects_empty_dst_evaluators() -> None:
    with pytest.raises(ValidationError):
        TransportNode(node="Transport", mode="metadata_only", dstEvaluators=[])


def test_moving_baseline_invalid_mode_accepted_at_model_layer() -> None:
    """Invalid moving+fixed combo normalizes OK; caught at runtime instead."""
    node = BaselineNode(
        node="Baseline",
        id="b1",
        kind="moving",
        criterion=CriterionRefNode(kind="ref", ref="test://baseline/series"),
        frame=FrameNode(
            node="Frame", system="T", namespace="N", scale="s", task="t", regime="r"
        ),
        evaluationMode="fixed",
    )
    assert node.kind == "moving"
    assert node.evaluationMode == "fixed"


def test_dynamic_expr_accepts_term_subject() -> None:
    expr = DynamicExprNode(
        node="DynamicExpr",
        op="approaches",
        subject=SymbolTermNode(node="SymbolTerm", value="reactive_margin"),
        target=PredicateExprNode(node="PredicateExpr", name="p", args=[]),
    )
    assert expr.op == "approaches"


def test_joint_adequacy_requires_non_empty_assessments() -> None:
    with pytest.raises(ValidationError):
        JointAdequacyNode(node="JointAdequacy", id="ja1", anchors=["a1", "a2"], assessments=[])
