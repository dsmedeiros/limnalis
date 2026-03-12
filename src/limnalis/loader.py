from __future__ import annotations

from pathlib import Path
from typing import Any

from .models.ast import BundleNode
from .normalizer import NormalizationResult, Normalizer
from .parser import LimnalisParser
from .schema import load_json_or_yaml, validate_payload


def load_data(path: str | Path) -> Any:
    return load_json_or_yaml(path)


def load_fixture_corpus(path: str | Path) -> dict[str, Any]:
    payload = load_json_or_yaml(path)
    validate_payload(payload, "fixture_corpus")
    return payload


def load_ast_bundle(path: str | Path) -> BundleNode:
    payload = load_json_or_yaml(path)
    validate_payload(payload, "ast")
    return BundleNode.model_validate(payload)


def normalize_surface_text(source: str, *, validate_schema: bool = True) -> NormalizationResult:
    result = Normalizer().normalize(LimnalisParser().parse_text(source))
    _validate_normalization_result(result, validate_schema=validate_schema)
    return result


def normalize_surface_file(
    path: str | Path, *, validate_schema: bool = True
) -> NormalizationResult:
    result = Normalizer().normalize(LimnalisParser().parse_file(path))
    _validate_normalization_result(result, validate_schema=validate_schema)
    return result


def load_surface_bundle(path: str | Path) -> BundleNode:
    result = normalize_surface_file(path, validate_schema=True)
    if result.canonical_ast is None:
        raise ValueError("surface normalization completed without producing a canonical AST")
    return result.canonical_ast


def _validate_normalization_result(result: NormalizationResult, *, validate_schema: bool) -> None:
    if validate_schema and result.canonical_ast is not None:
        validate_payload(result.canonical_ast.to_schema_data(), "ast")
