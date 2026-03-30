from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from limnalis.interop import (
    ASTEnvelope,
    ConformanceEnvelope,
    ResultEnvelope,
    SCHEMA_VERSION,
    SPEC_VERSION,
    SourceInfo,
    export_ast,
    export_ast_from_dict,
    export_conformance,
    export_result,
    get_package_version,
    import_ast_envelope,
    import_conformance_envelope,
    import_result_envelope,
)

ROOT = Path(__file__).resolve().parents[1]
MINIMAL_BUNDLE = ROOT / "examples" / "minimal_bundle.lmn"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_ast_dict() -> dict:
    return {"node": "Bundle", "id": "fixture_bundle", "version": "1.0"}


@pytest.fixture()
def sample_result_data() -> dict:
    return {"status": "pass", "score": 1.0, "details": ["ok"]}


@pytest.fixture()
def sample_conformance_report() -> dict:
    return {"total": 5, "passed": 5, "failed": 0}


# ---------------------------------------------------------------------------
# export_ast (from real .lmn source)
# ---------------------------------------------------------------------------


class TestExportAST:
    def test_export_ast_json_from_source_file(self) -> None:
        result = export_ast(MINIMAL_BUNDLE, format="json")
        data = json.loads(result)
        assert data["artifact_kind"] == "ast"
        assert data["spec_version"] == SPEC_VERSION
        assert data["schema_version"] == SCHEMA_VERSION
        assert isinstance(data["normalized_ast"], dict)

    def test_export_ast_yaml_from_source_file(self) -> None:
        result = export_ast(MINIMAL_BUNDLE, format="yaml")
        data = yaml.safe_load(result)
        assert data["artifact_kind"] == "ast"
        assert isinstance(data["normalized_ast"], dict)

    def test_export_ast_includes_source_info(self) -> None:
        result = export_ast(MINIMAL_BUNDLE, format="json")
        data = json.loads(result)
        assert data["source_info"]["path"] == str(MINIMAL_BUNDLE)


# ---------------------------------------------------------------------------
# export_ast_from_dict
# ---------------------------------------------------------------------------


class TestExportASTFromDict:
    def test_json_format(self, sample_ast_dict: dict) -> None:
        result = export_ast_from_dict(sample_ast_dict, format="json")
        data = json.loads(result)
        assert data["artifact_kind"] == "ast"
        assert data["normalized_ast"] == sample_ast_dict

    def test_yaml_format(self, sample_ast_dict: dict) -> None:
        result = export_ast_from_dict(sample_ast_dict, format="yaml")
        data = yaml.safe_load(result)
        assert data["artifact_kind"] == "ast"
        assert data["normalized_ast"] == sample_ast_dict

    def test_with_source_info(self, sample_ast_dict: dict) -> None:
        si = SourceInfo(path="/custom.lmn", sha256="aaa")
        result = export_ast_from_dict(sample_ast_dict, source_info=si, format="json")
        data = json.loads(result)
        assert data["source_info"]["path"] == "/custom.lmn"
        assert data["source_info"]["sha256"] == "aaa"


# ---------------------------------------------------------------------------
# export_result
# ---------------------------------------------------------------------------


class TestExportResult:
    def test_json_format(self, sample_result_data: dict) -> None:
        result = export_result(sample_result_data, format="json")
        data = json.loads(result)
        assert data["artifact_kind"] == "evaluation_result"
        assert data["evaluation_result"] == sample_result_data

    def test_yaml_format(self, sample_result_data: dict) -> None:
        result = export_result(sample_result_data, format="yaml")
        data = yaml.safe_load(result)
        assert data["artifact_kind"] == "evaluation_result"
        assert data["evaluation_result"] == sample_result_data


# ---------------------------------------------------------------------------
# export_conformance
# ---------------------------------------------------------------------------


class TestExportConformance:
    def test_json_format(self, sample_conformance_report: dict) -> None:
        result = export_conformance(sample_conformance_report, format="json")
        data = json.loads(result)
        assert data["artifact_kind"] == "conformance_report"
        assert data["report"] == sample_conformance_report

    def test_yaml_format(self, sample_conformance_report: dict) -> None:
        result = export_conformance(sample_conformance_report, format="yaml")
        data = yaml.safe_load(result)
        assert data["artifact_kind"] == "conformance_report"

    def test_with_corpus_version(self, sample_conformance_report: dict) -> None:
        result = export_conformance(
            sample_conformance_report, corpus_version="2.0", format="json"
        )
        data = json.loads(result)
        assert data["corpus_version"] == "2.0"


# ---------------------------------------------------------------------------
# import_ast_envelope
# ---------------------------------------------------------------------------


class TestImportASTEnvelope:
    def test_from_json_string(self, sample_ast_dict: dict) -> None:
        exported = export_ast_from_dict(sample_ast_dict, format="json")
        env = import_ast_envelope(exported, format="json")
        assert isinstance(env, ASTEnvelope)
        assert env.normalized_ast == sample_ast_dict

    def test_from_yaml_string(self, sample_ast_dict: dict) -> None:
        exported = export_ast_from_dict(sample_ast_dict, format="yaml")
        env = import_ast_envelope(exported, format="yaml")
        assert isinstance(env, ASTEnvelope)
        assert env.normalized_ast == sample_ast_dict

    def test_from_dict(self, sample_ast_dict: dict) -> None:
        raw = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "ast",
            "normalized_ast": sample_ast_dict,
        }
        env = import_ast_envelope(raw)
        assert env.normalized_ast == sample_ast_dict

    def test_from_json_file(self, tmp_path: Path, sample_ast_dict: dict) -> None:
        exported = export_ast_from_dict(sample_ast_dict, format="json")
        p = tmp_path / "test_ast.json"
        p.write_text(exported, encoding="utf-8")
        env = import_ast_envelope(p)
        assert isinstance(env, ASTEnvelope)
        assert env.normalized_ast == sample_ast_dict

    def test_from_yaml_file(self, tmp_path: Path, sample_ast_dict: dict) -> None:
        exported = export_ast_from_dict(sample_ast_dict, format="yaml")
        p = tmp_path / "test_ast.yaml"
        p.write_text(exported, encoding="utf-8")
        env = import_ast_envelope(p)
        assert isinstance(env, ASTEnvelope)
        assert env.normalized_ast == sample_ast_dict

    def test_string_without_format_raises(self, sample_ast_dict: dict) -> None:
        exported = export_ast_from_dict(sample_ast_dict, format="json")
        with pytest.raises(ValueError, match="format parameter is required"):
            import_ast_envelope(exported)

    def test_file_with_bad_extension_raises(
        self, tmp_path: Path, sample_ast_dict: dict
    ) -> None:
        exported = export_ast_from_dict(sample_ast_dict, format="json")
        p = tmp_path / "test_ast.xml"
        p.write_text(exported, encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot detect format"):
            import_ast_envelope(p)


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestRoundTrips:
    def test_ast_round_trip_from_source(self) -> None:
        exported_json = export_ast(MINIMAL_BUNDLE, format="json")
        env = import_ast_envelope(exported_json, format="json")
        assert env.spec_version == SPEC_VERSION
        assert env.schema_version == SCHEMA_VERSION
        assert env.artifact_kind == "ast"
        assert isinstance(env.normalized_ast, dict)
        assert env.source_info is not None
        assert env.source_info.path == str(MINIMAL_BUNDLE)

    def test_ast_round_trip_yaml(self) -> None:
        exported_yaml = export_ast(MINIMAL_BUNDLE, format="yaml")
        env = import_ast_envelope(exported_yaml, format="yaml")
        assert env.artifact_kind == "ast"
        assert isinstance(env.normalized_ast, dict)

    def test_result_round_trip(self, sample_result_data: dict) -> None:
        exported = export_result(sample_result_data, format="json")
        env = import_result_envelope(exported, format="json")
        assert isinstance(env, ResultEnvelope)
        assert env.evaluation_result == sample_result_data
        assert env.artifact_kind == "evaluation_result"
        assert env.spec_version == SPEC_VERSION

    def test_conformance_round_trip(self, sample_conformance_report: dict) -> None:
        exported = export_conformance(
            sample_conformance_report, corpus_version="3.0", format="json"
        )
        env = import_conformance_envelope(exported, format="json")
        assert isinstance(env, ConformanceEnvelope)
        assert env.report == sample_conformance_report
        assert env.corpus_version == "3.0"
        assert env.artifact_kind == "conformance_report"

    def test_result_round_trip_yaml(self, sample_result_data: dict) -> None:
        exported = export_result(sample_result_data, format="yaml")
        env = import_result_envelope(exported, format="yaml")
        assert env.evaluation_result == sample_result_data

    def test_conformance_round_trip_yaml(
        self, sample_conformance_report: dict
    ) -> None:
        exported = export_conformance(sample_conformance_report, format="yaml")
        env = import_conformance_envelope(exported, format="yaml")
        assert env.report == sample_conformance_report


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_export_ast_deterministic(self) -> None:
        a = export_ast(MINIMAL_BUNDLE, format="json")
        b = export_ast(MINIMAL_BUNDLE, format="json")
        assert a == b

    def test_export_ast_from_dict_deterministic(self, sample_ast_dict: dict) -> None:
        a = export_ast_from_dict(sample_ast_dict, format="json")
        b = export_ast_from_dict(sample_ast_dict, format="json")
        assert a == b

    def test_export_result_deterministic(self, sample_result_data: dict) -> None:
        a = export_result(sample_result_data, format="json")
        b = export_result(sample_result_data, format="json")
        assert a == b

    def test_export_conformance_deterministic(
        self, sample_conformance_report: dict
    ) -> None:
        a = export_conformance(sample_conformance_report, format="json")
        b = export_conformance(sample_conformance_report, format="json")
        assert a == b
