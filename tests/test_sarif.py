"""Tests for SARIF 2.1.0 export of Limnalis diagnostics."""

from __future__ import annotations

import json

from limnalis.diagnostic_fmt import format_diagnostics
from limnalis.diagnostics import Diagnostic, SourcePosition, SourceSpan
from limnalis.sarif import diagnostics_to_sarif
from limnalis.version import PACKAGE_VERSION


def _make_diag(
    *,
    severity: str = "error",
    code: str = "test_code",
    message: str = "test message",
    phase: str = "parse",
    subject: str = "anchor",
    span: SourceSpan | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        phase=phase,
        subject=subject,
        span=span,
    )


def _sample_span() -> SourceSpan:
    return SourceSpan(
        start=SourcePosition(line=1, column=5, offset=4),
        end=SourcePosition(line=3, column=10, offset=42),
    )


class TestSarifStructure:
    def test_schema_and_version(self) -> None:
        result = diagnostics_to_sarif([])
        assert result["$schema"].endswith("sarif-schema-2.1.0.json")
        assert result["version"] == "2.1.0"

    def test_empty_diagnostics(self) -> None:
        result = diagnostics_to_sarif([])
        assert len(result["runs"]) == 1
        run = result["runs"][0]
        assert run["results"] == []
        assert run["tool"]["driver"]["rules"] == []

    def test_tool_metadata(self) -> None:
        result = diagnostics_to_sarif([], tool_name="custom", tool_version="1.0")
        driver = result["runs"][0]["tool"]["driver"]
        assert driver["name"] == "custom"
        assert driver["version"] == "1.0"

    def test_default_version(self) -> None:
        result = diagnostics_to_sarif([])
        driver = result["runs"][0]["tool"]["driver"]
        assert driver["version"] == PACKAGE_VERSION


class TestSeverityMapping:
    def test_error_maps_to_error(self) -> None:
        result = diagnostics_to_sarif([_make_diag(severity="error")])
        assert result["runs"][0]["results"][0]["level"] == "error"

    def test_warning_maps_to_warning(self) -> None:
        result = diagnostics_to_sarif([_make_diag(severity="warning")])
        assert result["runs"][0]["results"][0]["level"] == "warning"

    def test_info_maps_to_note(self) -> None:
        result = diagnostics_to_sarif([_make_diag(severity="info")])
        assert result["runs"][0]["results"][0]["level"] == "note"


class TestSpanMapping:
    def test_with_span(self) -> None:
        diag = _make_diag(span=_sample_span())
        result = diagnostics_to_sarif([diag])
        loc = result["runs"][0]["results"][0]["locations"][0]
        region = loc["physicalLocation"]["region"]
        assert region["startLine"] == 1
        assert region["startColumn"] == 5
        assert region["endLine"] == 3
        assert region["endColumn"] == 10

    def test_without_span(self) -> None:
        diag = _make_diag(span=None)
        result = diagnostics_to_sarif([diag])
        assert "locations" not in result["runs"][0]["results"][0]


class TestRuleDeduplication:
    def test_same_code_produces_one_rule(self) -> None:
        diags = [
            _make_diag(code="dup_code", message="first"),
            _make_diag(code="dup_code", message="second"),
        ]
        result = diagnostics_to_sarif(diags)
        rules = result["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 1
        assert rules[0]["id"] == "dup_code"

    def test_different_codes_produce_multiple_rules(self) -> None:
        diags = [
            _make_diag(code="alpha"),
            _make_diag(code="beta"),
        ]
        result = diagnostics_to_sarif(diags)
        rules = result["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 2
        assert [r["id"] for r in rules] == ["alpha", "beta"]


class TestDeterminism:
    def test_output_is_deterministic(self) -> None:
        diags = [
            _make_diag(code="z_code", message="zzz"),
            _make_diag(code="a_code", message="aaa"),
            _make_diag(code="m_code", message="mmm"),
        ]
        result1 = diagnostics_to_sarif(diags)
        result2 = diagnostics_to_sarif(list(reversed(diags)))
        assert json.dumps(result1, sort_keys=True) == json.dumps(result2, sort_keys=True)


class TestProperties:
    def test_phase_and_subject_in_properties(self) -> None:
        diag = _make_diag(phase="normalize", subject="frame.evaluator")
        result = diagnostics_to_sarif([diag])
        props = result["runs"][0]["results"][0]["properties"]
        assert props["phase"] == "normalize"
        assert props["subject"] == "frame.evaluator"


class TestRawDictInput:
    def test_accepts_raw_dicts(self) -> None:
        raw = {"severity": "warning", "code": "w1", "message": "warn", "phase": "p", "subject": "s"}
        result = diagnostics_to_sarif([raw])
        assert len(result["runs"][0]["results"]) == 1


class TestFormatDiagnosticsSarifMode:
    def test_returns_valid_json(self) -> None:
        diags = [_make_diag()]
        output = format_diagnostics(diags, mode="sarif")
        parsed = json.loads(output)
        assert parsed["version"] == "2.1.0"
        assert len(parsed["runs"][0]["results"]) == 1
