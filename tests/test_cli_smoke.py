from __future__ import annotations

import json
from pathlib import Path

from limnalis.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_validate_fixtures_cli_smoke() -> None:
    code = main(
        ["validate-fixtures", str(ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json")]
    )
    assert code == 0


def test_parse_cli_smoke(capsys) -> None:
    code = main(["parse", str(ROOT / "examples" / "minimal_bundle.lmn")])

    captured = capsys.readouterr()

    assert code == 0
    assert "bundle" in captured.out
    assert "nested_block" in captured.out


def test_print_schema_cli_smoke(capsys) -> None:
    code = main(["print-schema", "ast"])

    captured = capsys.readouterr()

    assert code == 0
    assert json.loads(captured.out)["title"] == "Limnalis v0.2.2 canonical AST schema"
