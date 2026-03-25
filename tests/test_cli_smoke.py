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
    source = "bundle empty_bundle { }"
    path = tmp_path / "empty.lmn"
    path.write_text(source, encoding="utf-8")

    code = main(["validate-source", str(path)])

    captured = capsys.readouterr()

    assert code == 1
    assert "error:" in captured.err
    assert "normalization" in captured.err.lower() or "normalize" in captured.err.lower()


def test_print_schema_cli_smoke(capsys) -> None:
    code = main(["print-schema", "ast"])

    captured = capsys.readouterr()

    assert code == 0
    assert json.loads(captured.out)["title"] == "Limnalis v0.2.2 canonical AST schema"


# ---------------------------------------------------------------------------
# T8.3 – Additional CLI smoke tests
# ---------------------------------------------------------------------------


def test_version_command(capsys) -> None:
    """Test 'limnalis version' prints version info as JSON."""
    code = main(["version"])
    captured = capsys.readouterr()

    assert code == 0
    info = json.loads(captured.out)
    assert "package" in info
    assert "spec" in info


def test_version_flag() -> None:
    """Test 'limnalis --version' flag."""
    import pytest as _pytest
    with _pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


def test_parse_invalid_file(tmp_path: Path, capsys) -> None:
    """Test 'limnalis parse' with a non-existent file returns exit code 1."""
    nonexistent = tmp_path / "nonexistent.lmn"
    code = main(["parse", str(nonexistent)])
    assert code == 1, f"Expected exit code 1 for missing file, got {code}"
    captured = capsys.readouterr()
    assert "error:" in captured.err


def test_normalize_invalid_file(tmp_path: Path, capsys) -> None:
    """Test 'limnalis normalize' with a non-existent file returns exit code 1."""
    nonexistent = tmp_path / "nonexistent.lmn"
    code = main(["normalize", str(nonexistent)])
    assert code == 1, f"Expected exit code 1 for missing file, got {code}"
    captured = capsys.readouterr()
    assert "error:" in captured.err


def test_evaluate_with_valid_fixture(capsys) -> None:
    """Test 'limnalis evaluate' with a valid fixture file."""
    code = main(["evaluate", str(ROOT / "examples" / "minimal_bundle.lmn")])
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert "bundle_id" in payload or "session_results" in payload


def test_conformance_list(capsys) -> None:
    """Test 'limnalis conformance list' exits cleanly."""
    code = main(["conformance", "list"])

    assert code == 0
    captured = capsys.readouterr()
    # Should list at least one case
    assert len(captured.out.strip()) > 0


def test_conformance_run_all(capsys) -> None:
    """Test 'limnalis conformance run --all' exits cleanly."""
    code = main(["conformance", "run", "--all"])

    captured = capsys.readouterr()
    # Should print results summary
    assert "Results:" in captured.out
    assert code == 0


def test_conformance_run_all_strict(capsys) -> None:
    """Test 'limnalis conformance run --all --strict' exits 0 when all cases pass."""
    code = main(["conformance", "run", "--all", "--strict"])

    captured = capsys.readouterr()
    assert "Results:" in captured.out
    assert code == 0


def test_conformance_report_json(capsys) -> None:
    """Test 'limnalis conformance report --format json' produces valid JSON."""
    code = main(["conformance", "report", "--format", "json"])

    captured = capsys.readouterr()
    assert code == 0
    report = json.loads(captured.out)
    assert "summary" in report
    assert "cases" in report
    assert report["summary"]["total"] > 0


def test_conformance_report_markdown(capsys) -> None:
    """Test 'limnalis conformance report --format markdown' produces output."""
    code = main(["conformance", "report", "--format", "markdown"])

    captured = capsys.readouterr()
    assert code == 0
    assert "# Conformance Report" in captured.out
    assert "## Summary" in captured.out
    assert "## Results" in captured.out


def test_conformance_allowlist_missing_returns_error_code(capsys, tmp_path) -> None:
    """Test allowlist load errors return code 1 (no SystemExit from main)."""
    missing_path = tmp_path / "missing_allowlist.json"
    code = main(["conformance", "run", "--allowlist", str(missing_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert "allowlist file not found" in captured.err
