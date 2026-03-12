from __future__ import annotations

import json
from pathlib import Path

import pytest

from limnalis.normalizer import NormalizationError, Normalizer
from limnalis.parser import LimnalisParser
from limnalis.schema import validate_payload

ROOT = Path(__file__).resolve().parents[1]


def _normalize_source(source: str):
    tree = LimnalisParser().parse_text(source)
    result = Normalizer().normalize(tree)
    assert result.canonical_ast is not None
    validate_payload(result.canonical_ast.to_schema_data(), "ast")
    return result


def test_normalizer_converts_minimal_bundle_into_canonical_ast() -> None:
    source = (ROOT / "examples" / "minimal_bundle.lmn").read_text(encoding="utf-8")
    expected = json.loads(
        (ROOT / "examples" / "minimal_bundle_normalized_ast.json").read_text(encoding="utf-8")
    )

    result = _normalize_source(source)

    assert result.canonical_ast.to_schema_data() == expected
    assert [diagnostic["code"] for diagnostic in result.diagnostics] == [
        "resolution_policy_defaulted"
    ]


def test_normalizer_handles_frame_blocks_and_logical_claims() -> None:
    source = """
    bundle A3_logic_block {
      frame {
        system Test;
        namespace Logic;
        scale unit;
        task check;
        regime nominal;
      }

      evaluator ev0 {
        kind model;
        binding test://eval/atoms_v1;
      }

      resolution_policy rp0 {
        kind single;
        members [ev0];
      }

      local {
        c1: b;
        c2: n;
      }

      systemic {
        c3: p;
      }

      meta {
        c5: (p AND b);
      }
    }
    """

    bundle = _normalize_source(source).canonical_ast

    assert bundle.frame.node == "Frame"
    assert bundle.frame.system == "Test"
    assert [block.id for block in bundle.claimBlocks] == ["local#1", "systemic#1", "meta#1"]
    meta_claim = bundle.claimBlocks[2].claims[0]
    assert meta_claim.kind == "logical"
    assert meta_claim.expr.node == "LogicalExpr"
    assert meta_claim.expr.op == "and"
    assert [arg.name for arg in meta_claim.expr.args] == ["p", "b"]


def test_normalizer_wraps_judged_claims() -> None:
    source = """
    bundle A13_core_judged_expr {
      frame {
        system Test;
        namespace Judgment;
        scale service;
        task review;
        regime nominal;
      }

      evaluator ev0 {
        kind institution;
        binding test://eval/auth_truth_v1;
      }

      local {
        c1: safe(grid_state) judged_by test://eval/judged_inner_v1;
      }
    }
    """

    bundle = _normalize_source(source).canonical_ast
    claim = bundle.claimBlocks[0].claims[0]

    assert claim.kind == "judgment"
    assert claim.expr.node == "JudgedExpr"
    assert claim.expr.criterionRef == "test://eval/judged_inner_v1"
    assert claim.expr.expr.node == "PredicateExpr"
    assert claim.expr.expr.name == "safe"
    assert claim.expr.expr.args[0].node == "SymbolTerm"
    assert claim.expr.expr.args[0].value == "grid_state"


def test_normalizer_keeps_explicit_adjudicated_resolution_policy() -> None:
    source = """
    bundle A14_adjudicated_resolution {
      frame {
        system Test;
        namespace Governance;
        scale service;
        task review;
        regime nominal;
      }

      evaluator ev_primary {
        kind model;
        role primary;
        binding test://eval/atoms_v1;
      }

      evaluator ev_adversarial {
        kind model;
        role adversarial;
        binding test://eval/adversarial_v1;
      }

      resolution_policy rp_adj {
        kind adjudicated;
        members [ev_primary, ev_adversarial];
        binding test://resolution/adjudicated_v1;
      }

      local {
        c1: p;
        c2: (b AND n);
      }
    }
    """

    bundle = _normalize_source(source).canonical_ast

    assert [evaluator.id for evaluator in bundle.evaluators] == ["ev_primary", "ev_adversarial"]
    assert [evaluator.role for evaluator in bundle.evaluators] == ["primary", "adversarial"]
    assert bundle.resolutionPolicy.kind == "adjudicated"
    assert bundle.resolutionPolicy.members == ["ev_primary", "ev_adversarial"]
    assert bundle.resolutionPolicy.binding == "test://resolution/adjudicated_v1"


def test_normalizer_rejects_unsupported_claim_metadata() -> None:
    source = """
    bundle unsupported_claim_metadata {
      frame {
        system Test;
        namespace Unsupported;
        scale unit;
        task check;
        regime nominal;
      }

      evaluator ev0 {
        kind model;
        binding test://eval/atoms_v1;
      }

      local {
        c1: p refs [e1];
      }
    }
    """

    tree = LimnalisParser().parse_text(source)

    with pytest.raises(NormalizationError, match="claim metadata modifiers"):
        Normalizer().normalize(tree)
