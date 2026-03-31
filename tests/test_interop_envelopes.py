from __future__ import annotations

import pytest
from pydantic import ValidationError

from limnalis.interop import (
    ASTEnvelope,
    ConformanceEnvelope,
    ResultEnvelope,
    SourceInfo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def source_info() -> SourceInfo:
    return SourceInfo(path="/tmp/test.lmn", sha256="abc123", timestamp="2025-01-01T00:00:00Z")


@pytest.fixture()
def minimal_ast_data() -> dict:
    return {"node": "Bundle", "id": "test_bundle"}


# ---------------------------------------------------------------------------
# SourceInfo
# ---------------------------------------------------------------------------


class TestSourceInfo:
    def test_creation_with_all_fields(self) -> None:
        si = SourceInfo(path="/a/b.lmn", sha256="deadbeef", timestamp="2025-06-01T12:00:00Z")
        assert si.path == "/a/b.lmn"
        assert si.sha256 == "deadbeef"
        assert si.timestamp == "2025-06-01T12:00:00Z"

    def test_creation_with_defaults(self) -> None:
        si = SourceInfo()
        assert si.path is None
        assert si.sha256 is None
        assert si.timestamp is None

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SourceInfo(path="/a.lmn", bogus="nope")  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        si = SourceInfo(path="/x.lmn")
        d = si.model_dump(mode="json")
        assert d["path"] == "/x.lmn"
        assert "sha256" in d


# ---------------------------------------------------------------------------
# ASTEnvelope
# ---------------------------------------------------------------------------


class TestASTEnvelope:
    def test_creation_with_all_fields(
        self, source_info: SourceInfo, minimal_ast_data: dict
    ) -> None:
        env = ASTEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            source_info=source_info,
            normalized_ast=minimal_ast_data,
        )
        assert env.spec_version == "0.2.2"
        assert env.artifact_kind == "ast"
        assert env.normalized_ast == minimal_ast_data
        assert env.source_info is not None
        assert env.source_info.path == "/tmp/test.lmn"

    def test_default_artifact_kind(self, minimal_ast_data: dict) -> None:
        env = ASTEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            normalized_ast=minimal_ast_data,
        )
        assert env.artifact_kind == "ast"

    def test_rejects_extra_fields(self, minimal_ast_data: dict) -> None:
        with pytest.raises(ValidationError):
            ASTEnvelope(
                spec_version="0.2.2",
                schema_version="0.2.2",
                package_version="0.1.0",
                normalized_ast=minimal_ast_data,
                unexpected_field="bad",  # type: ignore[call-arg]
            )

    def test_model_dump_serialization(self, minimal_ast_data: dict) -> None:
        env = ASTEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            normalized_ast=minimal_ast_data,
        )
        d = env.model_dump(mode="json")
        assert d["spec_version"] == "0.2.2"
        assert d["artifact_kind"] == "ast"
        assert d["normalized_ast"] == minimal_ast_data


# ---------------------------------------------------------------------------
# ResultEnvelope
# ---------------------------------------------------------------------------


class TestResultEnvelope:
    def test_creation_with_all_fields(self, source_info: SourceInfo) -> None:
        result_data = {"status": "pass", "score": 1.0}
        env = ResultEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            source_info=source_info,
            evaluation_result=result_data,
        )
        assert env.artifact_kind == "evaluation_result"
        assert env.evaluation_result == result_data

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ResultEnvelope(
                spec_version="0.2.2",
                schema_version="0.2.2",
                package_version="0.1.0",
                evaluation_result={"ok": True},
                extra_stuff=True,  # type: ignore[call-arg]
            )

    def test_model_dump_serialization(self) -> None:
        env = ResultEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            evaluation_result={"passed": True},
        )
        d = env.model_dump(mode="json")
        assert d["artifact_kind"] == "evaluation_result"
        assert d["evaluation_result"] == {"passed": True}


# ---------------------------------------------------------------------------
# ConformanceEnvelope
# ---------------------------------------------------------------------------


class TestConformanceEnvelope:
    def test_creation_with_all_fields(self) -> None:
        env = ConformanceEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            corpus_version="1.0",
            report={"total": 10, "passed": 10},
        )
        assert env.artifact_kind == "conformance_report"
        assert env.corpus_version == "1.0"
        assert env.report == {"total": 10, "passed": 10}

    def test_corpus_version_optional(self) -> None:
        env = ConformanceEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            report={"total": 5},
        )
        assert env.corpus_version is None

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ConformanceEnvelope(
                spec_version="0.2.2",
                schema_version="0.2.2",
                package_version="0.1.0",
                report={},
                rogue="field",  # type: ignore[call-arg]
            )

    def test_model_dump_serialization(self) -> None:
        env = ConformanceEnvelope(
            spec_version="0.2.2",
            schema_version="0.2.2",
            package_version="0.1.0",
            report={"summary": "all pass"},
        )
        d = env.model_dump(mode="json")
        assert d["artifact_kind"] == "conformance_report"
        assert d["report"] == {"summary": "all pass"}
