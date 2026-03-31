"""Tests for the LinkML projection pipeline."""

from __future__ import annotations

from pathlib import Path

import yaml

from limnalis.interop import ProjectionResult, project_linkml_schema


def test_project_ast_returns_projection_result() -> None:
    result = project_linkml_schema("ast")

    assert isinstance(result, ProjectionResult)
    assert result.target_format == "linkml"
    assert result.source_model == "ast"


def test_project_evaluation_result() -> None:
    result = project_linkml_schema("evaluation_result")

    assert isinstance(result, ProjectionResult)
    assert result.source_model == "evaluation_result"


def test_project_conformance_report() -> None:
    result = project_linkml_schema("conformance_report")

    assert isinstance(result, ProjectionResult)
    assert result.source_model == "conformance_report"


def test_evaluation_result_projection_matches_runtime_bundle_result(tmp_path: Path) -> None:
    out = tmp_path / "eval_result.yaml"
    project_linkml_schema("evaluation_result", output_path=out)

    parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "BundleResult" in parsed["classes"]
    attrs = parsed["classes"]["BundleResult"]["attributes"]
    assert "bundle_id" in attrs
    assert "session_results" in attrs
    assert "diagnostics" in attrs


def test_conformance_report_projection_matches_report_shape(tmp_path: Path) -> None:
    out = tmp_path / "conformance_report.yaml"
    project_linkml_schema("conformance_report", output_path=out)

    parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "ConformanceReportModel" in parsed["classes"]
    attrs = parsed["classes"]["ConformanceReportModel"]["attributes"]
    assert "summary" in attrs
    assert "cases" in attrs


def test_output_file_written(tmp_path: Path) -> None:
    out = tmp_path / "schema.linkml.yaml"
    result = project_linkml_schema("ast", output_path=out)

    assert result.artifact_path == str(out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert len(content) > 0


def test_generated_yaml_is_valid(tmp_path: Path) -> None:
    out = tmp_path / "schema.linkml.yaml"
    project_linkml_schema("ast", output_path=out)

    content = out.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict)


def test_projection_has_warnings_and_lossy_fields() -> None:
    result = project_linkml_schema("ast")

    # The AST model has unions and dicts, so we expect some warnings
    assert isinstance(result.warnings, list)
    assert isinstance(result.lossy_fields, list)
    assert len(result.warnings) > 0
    assert len(result.lossy_fields) > 0


def test_regeneration_produces_stable_output(tmp_path: Path) -> None:
    out1 = tmp_path / "first.yaml"
    out2 = tmp_path / "second.yaml"

    project_linkml_schema("ast", output_path=out1)
    project_linkml_schema("ast", output_path=out2)

    content1 = out1.read_text(encoding="utf-8")
    content2 = out2.read_text(encoding="utf-8")

    # Parse both to compare structure (timestamps may differ in comments)
    parsed1 = yaml.safe_load(content1)
    parsed2 = yaml.safe_load(content2)

    assert parsed1["id"] == parsed2["id"]
    assert parsed1["name"] == parsed2["name"]
    assert parsed1["classes"].keys() == parsed2["classes"].keys()


def test_generated_yaml_has_expected_top_level_keys(tmp_path: Path) -> None:
    out = tmp_path / "schema.linkml.yaml"
    project_linkml_schema("ast", output_path=out)

    parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "id" in parsed
    assert "name" in parsed
    assert "classes" in parsed
    assert "prefixes" in parsed
    assert "default_range" in parsed


def test_projection_includes_root_entrypoint_class(tmp_path: Path) -> None:
    out = tmp_path / "schema.linkml.yaml"
    project_linkml_schema("ast", output_path=out)

    parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "classes" in parsed
    assert "BundleNode" in parsed["classes"]
