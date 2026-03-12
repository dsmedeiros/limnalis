from __future__ import annotations

from pathlib import Path

import pytest

from limnalis.loader import load_fixture_corpus
from limnalis.schema import (
    SchemaValidationError,
    collect_validation_errors,
    load_schema,
    make_validator,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_corpus_validates() -> None:
    corpus = load_fixture_corpus(ROOT / "fixtures" / "limnalis_fixture_corpus_v0.2.2.json")
    assert corpus["version"] == "v0.2.2-draft"


def test_ast_schema_repairs_upstream_time_ref_typo() -> None:
    schema = load_schema("ast")
    validator = make_validator("ast")
    assert schema["properties"]["time"]["$ref"] == "#/$defs/TimeCtxNode"
    assert validator is not None


def test_validate_payload_raises_structured_error_for_invalid_ast() -> None:
    with pytest.raises(SchemaValidationError) as excinfo:
        validate_payload({"node": "Bundle"}, "ast")

    error = excinfo.value

    assert error.schema_name == "ast"
    assert error.violations
    assert error.violations[0].path == "$"
    assert "required property" in error.violations[0].message


def test_collect_validation_errors_reports_json_paths() -> None:
    violations = collect_validation_errors({"node": "Bundle"}, "ast")

    assert violations
    assert violations[0].path == "$"
    assert violations[0].schema_path.startswith("$")
