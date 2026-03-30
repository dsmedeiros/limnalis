from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml

from limnalis.interop.envelopes import (
    ASTEnvelope,
    ConformanceEnvelope,
    ResultEnvelope,
)


def import_ast_envelope(
    data: str | Path | dict[str, Any],
    *,
    input_format: Literal["json", "yaml"] | None = None,
) -> ASTEnvelope:
    """Load and validate an ASTEnvelope from string, file, or dict."""
    parsed = _load_input(data, input_format=input_format)
    return ASTEnvelope.model_validate(parsed)


def import_result_envelope(
    data: str | Path | dict[str, Any],
    *,
    input_format: Literal["json", "yaml"] | None = None,
) -> ResultEnvelope:
    """Load and validate a ResultEnvelope."""
    parsed = _load_input(data, input_format=input_format)
    return ResultEnvelope.model_validate(parsed)


def import_conformance_envelope(
    data: str | Path | dict[str, Any],
    *,
    input_format: Literal["json", "yaml"] | None = None,
) -> ConformanceEnvelope:
    """Load and validate a ConformanceEnvelope."""
    parsed = _load_input(data, input_format=input_format)
    return ConformanceEnvelope.model_validate(parsed)


def _load_input(
    data: str | Path | dict[str, Any],
    *,
    input_format: Literal["json", "yaml"] | None,
) -> dict[str, Any]:
    """Resolve input to a dict, handling string content, file paths, and dicts."""
    if isinstance(data, dict):
        return data

    if isinstance(data, Path):
        text = data.read_text(encoding="utf-8")
        resolved_format = input_format or _detect_format(data)
        return _parse_text(text, input_format=resolved_format)

    # str input: require explicit format
    if input_format is None:
        raise ValueError(
            "input_format parameter is required when importing from a string; "
            "pass input_format='json' or input_format='yaml'"
        )
    return _parse_text(data, input_format=input_format)


def _detect_format(path: Path) -> Literal["json", "yaml"]:
    """Auto-detect format from file extension."""
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    raise ValueError(
        f"Cannot detect format from file extension '{suffix}'; "
        "pass input_format='json' or input_format='yaml' explicitly"
    )


def _parse_text(text: str, *, input_format: Literal["json", "yaml"]) -> dict[str, Any]:
    """Parse text as JSON or YAML and return a dict."""
    if input_format == "json":
        result = json.loads(text)
    else:
        result = yaml.safe_load(text)
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON/YAML object (dict), got {type(result).__name__}")
    return result
