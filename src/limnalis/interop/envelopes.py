from __future__ import annotations

from typing import Any, Literal

from limnalis.models.base import LimnalisModel


class SourceInfo(LimnalisModel):
    """Provenance metadata for the source artifact."""

    path: str | None = None
    sha256: str | None = None
    timestamp: str | None = None  # ISO 8601


class ASTEnvelope(LimnalisModel):
    """Envelope wrapping a normalized AST with version and provenance metadata."""

    spec_version: str  # e.g. "0.2.2"
    schema_version: str  # e.g. "0.2.2"
    package_version: str  # implementation version e.g. "0.1.0"
    artifact_kind: Literal["ast"] = "ast"
    source_info: SourceInfo | None = None
    normalized_ast: dict[str, Any]  # the canonical AST payload


class ResultEnvelope(LimnalisModel):
    """Envelope wrapping an evaluation result with version and provenance metadata."""

    spec_version: str
    schema_version: str
    package_version: str
    artifact_kind: Literal["evaluation_result"] = "evaluation_result"
    source_info: SourceInfo | None = None
    evaluation_result: dict[str, Any]


class ConformanceEnvelope(LimnalisModel):
    """Envelope wrapping a conformance report with version and provenance metadata."""

    spec_version: str
    schema_version: str
    package_version: str
    artifact_kind: Literal["conformance_report"] = "conformance_report"
    corpus_version: str | None = None
    report: dict[str, Any]
