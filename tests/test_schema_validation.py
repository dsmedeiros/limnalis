from __future__ import annotations

from pathlib import Path

from limnalis.loader import load_fixture_corpus
from limnalis.schema import load_schema, make_validator

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_corpus_validates() -> None:
    corpus = load_fixture_corpus(ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json")
    assert corpus["version"] == "v0.2.2-draft"


def test_ast_schema_repairs_upstream_time_ref_typo() -> None:
    schema = load_schema("ast")
    validator = make_validator("ast")
    assert schema["properties"]["time"]["$ref"] == "#/$defs/TimeCtxNode"
    assert validator is not None
