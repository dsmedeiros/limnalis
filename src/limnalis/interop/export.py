from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml

from limnalis.interop.envelopes import (
    ASTEnvelope,
    ConformanceEnvelope,
    ResultEnvelope,
    SourceInfo,
)
from limnalis.interop.types import SCHEMA_VERSION, SPEC_VERSION, get_package_version
from limnalis.loader import normalize_surface_file


def export_ast(
    source_path: str | Path,
    *,
    output_format: Literal["json", "yaml"] = "json",
    validate: bool = True,
    source_info: SourceInfo | None = None,
) -> str:
    """Parse, normalize source file, wrap in ASTEnvelope, serialize."""
    result = normalize_surface_file(source_path, validate_schema=validate)
    if result.canonical_ast is None:
        raise ValueError("Normalization did not produce a canonical AST")
    ast_data = result.canonical_ast.to_schema_data()

    if source_info is None:
        source_info = SourceInfo(path=str(source_path))

    envelope = ASTEnvelope(
        spec_version=SPEC_VERSION,
        schema_version=SCHEMA_VERSION,
        package_version=get_package_version(),
        source_info=source_info,
        normalized_ast=ast_data,
    )
    return _serialize(envelope_to_dict(envelope), output_format=output_format)


def export_ast_from_dict(
    ast_data: dict[str, Any],
    *,
    output_format: Literal["json", "yaml"] = "json",
    source_info: SourceInfo | None = None,
) -> str:
    """Wrap pre-normalized AST dict in ASTEnvelope and serialize."""
    envelope = ASTEnvelope(
        spec_version=SPEC_VERSION,
        schema_version=SCHEMA_VERSION,
        package_version=get_package_version(),
        source_info=source_info,
        normalized_ast=ast_data,
    )
    return _serialize(envelope_to_dict(envelope), output_format=output_format)


def export_result(
    result_data: dict[str, Any],
    *,
    output_format: Literal["json", "yaml"] = "json",
    source_info: SourceInfo | None = None,
) -> str:
    """Wrap evaluation result dict in ResultEnvelope and serialize."""
    envelope = ResultEnvelope(
        spec_version=SPEC_VERSION,
        schema_version=SCHEMA_VERSION,
        package_version=get_package_version(),
        source_info=source_info,
        evaluation_result=result_data,
    )
    return _serialize(envelope_to_dict(envelope), output_format=output_format)


def export_conformance(
    report_data: dict[str, Any],
    *,
    output_format: Literal["json", "yaml"] = "json",
    corpus_version: str | None = None,
) -> str:
    """Wrap conformance report dict in ConformanceEnvelope and serialize."""
    envelope = ConformanceEnvelope(
        spec_version=SPEC_VERSION,
        schema_version=SCHEMA_VERSION,
        package_version=get_package_version(),
        corpus_version=corpus_version,
        report=report_data,
    )
    return _serialize(envelope_to_dict(envelope), output_format=output_format)


def envelope_to_dict(
    envelope: ASTEnvelope | ResultEnvelope | ConformanceEnvelope,
) -> dict[str, Any]:
    """Convert envelope to a deterministically ordered dict."""
    return envelope.model_dump(mode="json")


def _serialize(data: dict[str, Any], *, output_format: Literal["json", "yaml"]) -> str:
    """Serialize a dict to JSON or YAML with deterministic key ordering."""
    if output_format == "json":
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return yaml.dump(data, default_flow_style=False, sort_keys=True, allow_unicode=True)
