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


def test_normalize_cli_smoke(capsys) -> None:
    code = main(["normalize", str(ROOT / "examples" / "minimal_bundle.lmn")])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["id"] == "minimal_bundle"
    assert payload["frame"]["node"] == "FramePattern"
    assert payload["resolutionPolicy"]["members"] == ["ev0"]


def test_validate_source_cli_smoke(capsys) -> None:
    code = main(["validate-source", str(ROOT / "examples" / "minimal_bundle.lmn")])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["bundle"] == "minimal_bundle"
    assert [diagnostic["code"] for diagnostic in payload["diagnostics"]] == [
        "resolution_policy_defaulted"
    ]


def test_validate_source_cli_reports_normalization_errors(tmp_path: Path, capsys) -> None:
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
    path = tmp_path / "unsupported.lmn"
    path.write_text(source, encoding="utf-8")

    code = main(["validate-source", str(path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["phase"] == "normalize"
    assert "claim metadata modifiers" in payload["message"]


def test_print_schema_cli_smoke(capsys) -> None:
    code = main(["print-schema", "ast"])

    captured = capsys.readouterr()

    assert code == 0
    assert json.loads(captured.out)["title"] == "Limnalis v0.2.2 canonical AST schema"
