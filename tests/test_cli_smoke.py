from __future__ import annotations

from pathlib import Path

from limnalis.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_validate_fixtures_cli_smoke() -> None:
    code = main(
        ["validate-fixtures", str(ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json")]
    )
    assert code == 0
