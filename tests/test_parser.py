from __future__ import annotations

import json
from pathlib import Path

import pytest
from lark import Token, UnexpectedInput

from limnalis.parser import LimnalisParser

ROOT = Path(__file__).resolve().parents[1]


def test_parser_accepts_minimal_bundle_example() -> None:
    source = (ROOT / "examples" / "minimal_bundle.lmn").read_text(encoding="utf-8")

    tree = LimnalisParser().parse_text(source)

    assert tree.data == "start"
    assert tree.children[0].data == "bundle"


def test_parser_handles_nested_blocks_comments_and_strings() -> None:
    source = """
    // bundle-level comment
    bundle smoke {
      evaluator ev0 {
        kind model;
        binding \"test://eval/atoms_v1\";
      }

      # local assertions
      local {
        c1: p;
      }
    }
    """

    tree = LimnalisParser().parse_text(source)
    bundle = tree.children[0]
    block = bundle.children[1]

    assert [child.data for child in block.children] == ["nested_block", "nested_block"]
    assert list(
        tree.scan_values(lambda value: isinstance(value, Token) and value.type == "STRING")
    ) == ['"test://eval/atoms_v1"']


def test_parse_file_matches_parse_text(tmp_path: Path) -> None:
    source = 'bundle smoke { frame @Test:Minimal::nominal; binding "test://eval/atoms_v1"; }'
    path = tmp_path / "smoke.lmn"
    path.write_text(source, encoding="utf-8")

    parser = LimnalisParser()

    assert parser.parse_file(path).pretty() == parser.parse_text(source).pretty()


def test_parser_rejects_unbalanced_block() -> None:
    parser = LimnalisParser()

    with pytest.raises(UnexpectedInput):
        parser.parse_text("bundle broken { frame x;")

def test_parser_accepts_all_fixture_corpus_sources() -> None:
    parser = LimnalisParser()
    corpus = json.loads(
        (ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json").read_text(
            encoding="utf-8"
        )
    )
    failures: list[str] = []

    for case in corpus["cases"]:
        try:
            parser.parse_text(case["source"])
        except UnexpectedInput as exc:
            failures.append(f"{case['id']}: {exc}")

    assert failures == []


def test_parser_accepts_fictional_anchor_examples() -> None:
    parser = LimnalisParser()

    default_tree = parser.parse_file(ROOT / "examples" / "fictional_anchor_default_subtype.lmn")
    proxy_tree = parser.parse_file(ROOT / "examples" / "fictional_anchor_proxy_subtype.lmn")

    default_bundle = default_tree.children[0].children[1]
    proxy_bundle = proxy_tree.children[0].children[1]

    assert any(
        child.data == "nested_block" and child.children[0] == "fictional_anchor"
        for child in default_bundle.children
    )
    assert any(
        child.data == "nested_block" and child.children[0] == "fictional_anchor"
        for child in proxy_bundle.children
    )
