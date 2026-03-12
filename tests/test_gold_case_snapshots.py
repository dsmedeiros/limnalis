from __future__ import annotations

import json
from pathlib import Path

from limnalis.normalizer import Normalizer
from limnalis.parser import LimnalisParser

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CORPUS_PATH = ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json"
SNAPSHOT_DIR = ROOT / "tests" / "snapshots" / "gold_cases"
GOLD_CASE_IDS = ["A1", "A3", "A11", "A14", "B1", "B2"]



def _fixture_cases() -> dict[str, dict[str, object]]:
    corpus = json.loads(FIXTURE_CORPUS_PATH.read_text(encoding="utf-8"))
    return {case["id"]: case for case in corpus["cases"]}



def _actual_snapshot(case_source: str, case_id: str) -> dict[str, object]:
    tree = LimnalisParser().parse_text(case_source)
    result = Normalizer().normalize(tree)
    assert result.canonical_ast is not None
    return {
        "case_id": case_id,
        "bundle_id": result.canonical_ast.id,
        "diagnostics": result.diagnostics,
        "canonical_ast": result.canonical_ast.to_schema_data(),
    }



def test_gold_fixture_cases_match_snapshots() -> None:
    fixture_cases = _fixture_cases()

    for case_id in GOLD_CASE_IDS:
        case = fixture_cases[case_id]
        expected = json.loads((SNAPSHOT_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
        actual = _actual_snapshot(case["source"], case_id)

        assert actual == expected
