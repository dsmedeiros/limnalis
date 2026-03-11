from __future__ import annotations

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
