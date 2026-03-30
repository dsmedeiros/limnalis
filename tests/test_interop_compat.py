"""Tests for envelope compatibility checking."""

from __future__ import annotations

from limnalis.interop import (
    ASTEnvelope,
    SCHEMA_VERSION,
    SPEC_VERSION,
    check_envelope_compatibility,
)


def _make_envelope(
    spec_version: str = SPEC_VERSION,
    schema_version: str = SCHEMA_VERSION,
) -> ASTEnvelope:
    return ASTEnvelope(
        spec_version=spec_version,
        schema_version=schema_version,
        package_version="0.0.0-test",
        normalized_ast={"id": "test"},
    )


def test_matching_versions_returns_empty_list() -> None:
    envelope = _make_envelope()
    issues = check_envelope_compatibility(envelope)
    assert issues == []


def test_mismatched_spec_version_returns_issue() -> None:
    envelope = _make_envelope(spec_version="0.0.0")
    issues = check_envelope_compatibility(envelope)
    assert len(issues) == 1
    assert "spec_version" in issues[0]


def test_mismatched_schema_version_returns_issue() -> None:
    envelope = _make_envelope(schema_version="0.0.0")
    issues = check_envelope_compatibility(envelope)
    assert len(issues) == 1
    assert "schema_version" in issues[0]


def test_both_mismatched_returns_two_issues() -> None:
    envelope = _make_envelope(spec_version="0.0.0", schema_version="0.0.0")
    issues = check_envelope_compatibility(envelope)
    assert len(issues) == 2
    assert any("spec_version" in i for i in issues)
    assert any("schema_version" in i for i in issues)
