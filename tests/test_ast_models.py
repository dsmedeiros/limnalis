from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from limnalis.models.ast import (
    BaselineNode,
    BundleNode,
    CriterionRefNode,
    DynamicExprNode,
    FrameNode,
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


def test_resolution_policy_single_requires_exactly_one_member() -> None:
    with pytest.raises(ValidationError):
        ResolutionPolicyNode(node="ResolutionPolicy", id="rp", kind="single", members=["a", "b"])


def test_transport_remap_requires_claim_map() -> None:
    with pytest.raises(ValidationError):
        TransportNode(node="Transport", mode="remap_recompute")


def test_moving_baseline_requires_tracked_mode() -> None:
    with pytest.raises(ValidationError):
        BaselineNode(
            node="Baseline",
            id="b1",
            kind="moving",
            criterion=CriterionRefNode(kind="ref", ref="test://baseline/series"),
            frame=FrameNode(node="Frame", system="T", namespace="N", scale="s", task="t", regime="r"),
            evaluationMode="fixed",
        )


def test_dynamic_expr_accepts_term_subject() -> None:
    expr = DynamicExprNode(
        node="DynamicExpr",
        op="approaches",
        subject=SymbolTermNode(node="SymbolTerm", value="reactive_margin"),
        target=PredicateExprNode(node="PredicateExpr", name="p", args=[]),
    )
    assert expr.op == "approaches"
