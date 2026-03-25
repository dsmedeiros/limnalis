from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from limnalis.normalizer import NormalizationError, Normalizer
from limnalis.parser import LimnalisParser
from limnalis.schema import validate_payload

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CASES = {
    case["id"]: case
    for case in json.loads(
        (ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json").read_text(encoding="utf-8")
    )["cases"]
}


def _normalize_source(source: str):
    tree = LimnalisParser().parse_text(source)
    result = Normalizer().normalize(tree)
    assert result.canonical_ast is not None
    validate_payload(result.canonical_ast.to_schema_data(), "ast")
    return result


def _normalize_fixture(case_id: str):
    return _normalize_source(FIXTURE_CASES[case_id]["source"])


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


@pytest.mark.parametrize(
    "case_id",
    sorted(case_id for case_id in FIXTURE_CASES if case_id != "A4"),
)
def test_fixture_corpus_cases_normalize_to_schema_valid_ast(case_id: str) -> None:
    result = _normalize_fixture(case_id)

    assert result.canonical_ast.id == FIXTURE_CASES[case_id]["source"].split()[1]


def test_normalizer_accepts_invalid_moving_baseline_fixture() -> None:
    """A4 moving+fixed baseline normalizes OK; validation is at runtime."""
    tree = LimnalisParser().parse_text(FIXTURE_CASES["A4"]["source"])
    result = Normalizer().normalize(tree)
    baselines = {bl.id: bl for bl in result.canonical_ast.baselines}
    assert baselines["b_invalid"].kind == "moving"
    assert baselines["b_invalid"].evaluationMode == "fixed"


def test_normalizer_synthesizes_ids_for_authored_adequacy_blocks() -> None:
    result = _normalize_fixture("A6")
    bundle = result.canonical_ast
    codes = Counter(diagnostic["code"] for diagnostic in result.diagnostics)

    assert [assessment.id for assessment in bundle.anchors[0].adequacy] == [
        "a_stateless#adequacy1",
        "a_stateless#adequacy2",
    ]
    assert [assessment.id for assessment in bundle.anchors[1].adequacy] == ["a_clock#adequacy1"]
    assert [assessment.id for assessment in bundle.anchors[2].adequacy] == ["a_cache#adequacy1"]
    assert bundle.jointAdequacies[0].assessments[0].id == "ja_access#assessment1"
    assert codes["adequacy_id_synthesized"] == 4
    assert codes["assessment_id_synthesized"] == 1


def test_normalizer_supports_causal_emergence_and_declaration_forms() -> None:
    bundle = _normalize_fixture("B1").canonical_ast

    local_claim = bundle.claimBlocks[0].claims[1]
    systemic_claim = bundle.claimBlocks[1].claims[0]
    declaration_claim = bundle.claimBlocks[2].claims[0]
    note_claim = bundle.claimBlocks[2].claims[1]

    assert local_claim.kind == "causal"
    assert local_claim.expr.node == "CausalExpr"
    assert local_claim.expr.mode == "obs"
    assert local_claim.refs == ["scada_bus7", "pmu_bus7"]

    assert systemic_claim.kind == "emergence"
    assert systemic_claim.usesAnchors == ["a_nminus1"]
    assert systemic_claim.refs == ["scada_bus7"]
    assert systemic_claim.annotations == {"license_task": "control"}
    assert systemic_claim.expr.node == "EmergenceExpr"
    assert systemic_claim.expr.onset.node == "DynamicExpr"
    assert systemic_claim.expr.onset.op == "approaches"
    assert systemic_claim.expr.onset.target.node == "BaselineRefTerm"
    assert systemic_claim.expr.onset.target.id == "margin"

    assert declaration_claim.kind == "declaration"
    assert declaration_claim.expr.node == "DeclarationExpr"
    assert declaration_claim.expr.within.node == "FramePattern"
    assert note_claim.kind == "note"
    assert note_claim.expr.text.startswith("N-1 is acceptable")


def test_normalizer_preserves_metadata_on_judged_claims() -> None:
    bundle = _normalize_fixture("B2").canonical_ast
    claim = bundle.claimBlocks[0].claims[2]

    assert claim.kind == "judgment"
    assert claim.expr.node == "JudgedExpr"
    assert claim.expr.criterionRef == "test://policy/auth_access_v3"
    assert claim.usesAnchors == ["a_stateless", "a_clock"]
    assert claim.refs == ["e_sig", "e_clock", "e_rev"]
    assert claim.annotations == {"license_task": "access_decision"}


def test_normalizer_emits_compatibility_diagnostics_for_surface_only_forms() -> None:
    a9 = _normalize_fixture("A9")
    a12 = _normalize_fixture("A12")

    assert a9.canonical_ast.evaluators[0].id == "ev_audit"
    assert a9.canonical_ast.evaluators[0].kind == "process"
    assert a9.canonical_ast.evaluators[0].role == "audit"
    assert [diagnostic["code"] for diagnostic in a9.diagnostics] == ["evaluator_kind_canonicalized"]

    assert a12.canonical_ast.resolutionPolicy.id == "rp0"
    assert a12.canonical_ast.anchors[0].adequacyPolicy == "rp_adequacy"
    assert [diagnostic["code"] for diagnostic in a12.diagnostics] == [
        "extra_resolution_policy_omitted"
    ]
