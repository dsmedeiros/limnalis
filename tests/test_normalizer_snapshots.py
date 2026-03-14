from __future__ import annotations

import json
from pathlib import Path

import pytest

from limnalis.loader import normalize_surface_file, normalize_surface_text

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CASES = {
    case["id"]: case
    for case in json.loads(
        (ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json").read_text(encoding="utf-8")
    )["cases"]
}
SNAPSHOT_CASE_IDS = ("A1", "A3", "A10", "A11", "A13", "A14", "B1", "B2")
SNAPSHOT_PATH = ROOT / "tests" / "snapshots" / "normalized_ast_acceptance_cases.json"
NORMALIZED_AST_SNAPSHOTS = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
FICTIONAL_ANCHOR_EXAMPLES = (
    "fictional_anchor_default_subtype",
    "fictional_anchor_proxy_subtype",
)


@pytest.mark.parametrize("case_id", SNAPSHOT_CASE_IDS)
def test_acceptance_cases_match_normalized_ast_snapshots(case_id: str) -> None:
    result = normalize_surface_text(FIXTURE_CASES[case_id]["source"], validate_schema=True)

    assert result.canonical_ast is not None
    assert result.canonical_ast.to_schema_data() == NORMALIZED_AST_SNAPSHOTS[case_id]


def test_normalizer_defaults_bridge_transport_and_preserves_diagnostic_spans() -> None:
    source = """\
bundle span_bridge {
  frame @Test:Scope::nominal;

  evaluator ev0 {
    kind audit;
    binding test://eval/atoms_v1;
  }

  bridge b0 {
    from @{system=Test, namespace=Scope, scale=micro, task=ops};
    to @{system=Test, namespace=Scope, scale=macro, task=planning, regime=nominal};
    via test://bridge/pass_through;
    preserve [mass_balance];
    lose [phase_detail];
  }

  local {
    c1: p;
  }
}
"""

    result = normalize_surface_text(source, validate_schema=True)

    assert result.canonical_ast is not None
    assert result.canonical_ast.bridges[0].transport.mode == "metadata_only"
    assert [diagnostic["code"] for diagnostic in result.diagnostics] == [
        "evaluator_kind_canonicalized",
        "bridge_transport_defaulted",
        "resolution_policy_defaulted",
    ]

    spans = {diagnostic["code"]: diagnostic["span"] for diagnostic in result.diagnostics}
    assert spans["evaluator_kind_canonicalized"]["start"]["line"] == 4
    assert spans["bridge_transport_defaulted"]["start"]["line"] == 9
    assert spans["resolution_policy_defaulted"]["start"]["line"] == 1


@pytest.mark.parametrize("example_name", FICTIONAL_ANCHOR_EXAMPLES)
def test_fictional_anchor_examples_match_normalized_ast_snapshots(example_name: str) -> None:
    result = normalize_surface_file(ROOT / "examples" / f"{example_name}.lmn", validate_schema=True)
    snapshot = json.loads(
        (ROOT / "examples" / f"{example_name}_normalized_ast.json").read_text(encoding="utf-8")
    )

    assert result.canonical_ast is not None
    assert result.canonical_ast.to_schema_data() == snapshot
    expected_diagnostic_codes = (
        ["fictional_anchor_subtype_defaulted"]
        if example_name == "fictional_anchor_default_subtype"
        else []
    )
    assert [diagnostic["code"] for diagnostic in result.diagnostics] == expected_diagnostic_codes, (
        f"Unexpected diagnostics for {example_name}: {result.diagnostics}"
    )
