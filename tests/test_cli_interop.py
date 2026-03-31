"""CLI tests for interop commands: export, package, project-linkml, and --version."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from limnalis.cli import main

ROOT = Path(__file__).resolve().parents[1]
MINIMAL_LMN = ROOT / "examples" / "minimal_bundle.lmn"


# ---------------------------------------------------------------------------
# export-ast
# ---------------------------------------------------------------------------


def test_export_ast_json(capsys) -> None:
    code = main(["export-ast", str(MINIMAL_LMN)])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert "spec_version" in payload
    assert "schema_version" in payload
    assert "artifact_kind" in payload
    assert payload["artifact_kind"] == "ast"
    assert "normalized_ast" in payload


def test_export_ast_yaml(capsys) -> None:
    code = main(["export-ast", str(MINIMAL_LMN), "--format", "yaml"])

    captured = capsys.readouterr()
    assert code == 0
    payload = yaml.safe_load(captured.out)
    assert payload["artifact_kind"] == "ast"
    assert "normalized_ast" in payload


def test_export_ast_nonexistent_file(capsys) -> None:
    code = main(["export-ast", "/nonexistent/path/to/file.lmn"])

    captured = capsys.readouterr()
    assert code == 1
    assert "error:" in captured.err


def test_export_ast_invalid_source_returns_error(tmp_path: Path, capsys) -> None:
    invalid = tmp_path / "invalid.lmn"
    invalid.write_text("this is not valid limnalis syntax", encoding="utf-8")

    code = main(["export-ast", str(invalid)])
    captured = capsys.readouterr()

    assert code == 1
    assert "export-ast failed" in captured.err


# ---------------------------------------------------------------------------
# export-result
# ---------------------------------------------------------------------------


def test_export_result(tmp_path: Path, capsys) -> None:
    result_file = tmp_path / "result.json"
    result_file.write_text(
        json.dumps({"bundle_id": "test", "outcome": "pass"}),
        encoding="utf-8",
    )

    code = main(["export-result", str(result_file)])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert "spec_version" in payload
    assert "schema_version" in payload
    assert payload["artifact_kind"] == "evaluation_result"
    assert "evaluation_result" in payload


def test_export_result_invalid_yaml_returns_error(tmp_path: Path, capsys) -> None:
    result_file = tmp_path / "bad_result.yaml"
    result_file.write_text("foo: [bar", encoding="utf-8")

    code = main(["export-result", str(result_file)])
    captured = capsys.readouterr()

    assert code == 1
    assert "export-result failed" in captured.err


# ---------------------------------------------------------------------------
# export-conformance
# ---------------------------------------------------------------------------


def test_export_conformance(tmp_path: Path, capsys) -> None:
    report_file = tmp_path / "report.json"
    report_file.write_text(
        json.dumps({"summary": "all pass", "total": 5}),
        encoding="utf-8",
    )

    code = main(["export-conformance", str(report_file)])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert "spec_version" in payload
    assert payload["artifact_kind"] == "conformance_report"
    assert "report" in payload


def test_export_conformance_invalid_yaml_returns_error(tmp_path: Path, capsys) -> None:
    report_file = tmp_path / "bad_report.yaml"
    report_file.write_text("report: [", encoding="utf-8")

    code = main(["export-conformance", str(report_file)])
    captured = capsys.readouterr()

    assert code == 1
    assert "export-conformance failed" in captured.err


# ---------------------------------------------------------------------------
# package-create / inspect / validate / extract
# ---------------------------------------------------------------------------


def test_package_create(tmp_path: Path, capsys) -> None:
    pkg_dir = tmp_path / "pkg"
    code = main([
        "package-create",
        str(pkg_dir),
        "--source", str(MINIMAL_LMN),
    ])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert "root_path" in payload


def test_package_inspect(tmp_path: Path, capsys) -> None:
    pkg_dir = tmp_path / "pkg"
    main(["package-create", str(pkg_dir), "--source", str(MINIMAL_LMN)])

    capsys.readouterr()  # clear create output
    code = main(["package-inspect", str(pkg_dir)])

    captured = capsys.readouterr()
    assert code == 0
    manifest = json.loads(captured.out)
    assert "format_version" in manifest
    assert "artifact_types" in manifest


def test_package_validate(tmp_path: Path, capsys) -> None:
    pkg_dir = tmp_path / "pkg"
    main(["package-create", str(pkg_dir), "--source", str(MINIMAL_LMN)])

    capsys.readouterr()  # clear create output
    code = main(["package-validate", str(pkg_dir)])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"


def test_package_extract(tmp_path: Path, capsys) -> None:
    pkg_dir = tmp_path / "pkg"
    main(["package-create", str(pkg_dir), "--source", str(MINIMAL_LMN)])

    capsys.readouterr()  # clear create output
    extract_dir = tmp_path / "extracted"
    code = main(["package-extract", str(pkg_dir), str(extract_dir)])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert Path(payload["output_dir"]).exists()


# ---------------------------------------------------------------------------
# project-linkml
# ---------------------------------------------------------------------------


def test_project_linkml_default(capsys) -> None:
    code = main(["project-linkml"])

    captured = capsys.readouterr()
    assert code == 0
    payload = yaml.safe_load(captured.out)
    assert payload["id"] == "https://limnalis.dev/schema/ast"
    assert "classes" in payload


def test_project_linkml_evaluation_result(capsys) -> None:
    code = main(["project-linkml", "--target", "evaluation_result"])

    captured = capsys.readouterr()
    assert code == 0
    payload = yaml.safe_load(captured.out)
    assert payload["id"] == "https://limnalis.dev/schema/results"


# ---------------------------------------------------------------------------
# version subcommand
# ---------------------------------------------------------------------------


def test_version_flag(capsys) -> None:
    code = main(["version"])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    # The 'version' subcommand outputs get_version_info() which includes
    # package, spec, schema, and corpus keys.
    assert "package" in payload or "spec_version" in payload
