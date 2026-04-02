"""Tests for diagnostic formatting and pretty-printing."""

from __future__ import annotations

import json

import pytest

from limnalis.diagnostic_fmt import (
    REMEDIATION_HINTS,
    format_diagnostics,
)
from limnalis.diagnostics import Diagnostic


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

SAMPLE_DIAGNOSTICS: list[dict] = [
    {
        "severity": "warning",
        "phase": "normalize",
        "subject": "evaluator.kind",
        "code": "evaluator_kind_canonicalized",
        "message": "Canonicalized evaluator kind 'Manual' -> 'manual'",
    },
    {
        "severity": "error",
        "phase": "validate",
        "subject": "ast.root",
        "code": "schema_validation_error",
        "message": "Required field 'anchor' missing in frame",
    },
    {
        "severity": "info",
        "phase": "runtime",
        "subject": "primitive.noop",
        "code": "stubbed_primitive",
        "message": "Using stub implementation for noop primitive",
    },
    {
        "severity": "warning",
        "phase": "normalize",
        "subject": "frame.baseline",
        "code": "baseline_mode_invalid",
        "message": "Baseline mode 'aggressive' is not recognised; falling back to 'default'",
    },
    {
        "severity": "error",
        "phase": "normalize",
        "subject": "frame.f1",
        "code": "frame_incomplete",
        "message": "Frame f1 missing required evaluator field",
    },
]


# ---------------------------------------------------------------------------
# Diagnostic.from_dict tests
# ---------------------------------------------------------------------------

class TestFromDict:
    def test_complete_dict(self) -> None:
        raw = {
            "severity": "error",
            "phase": "validate",
            "subject": "ast.root",
            "code": "schema_validation_error",
            "message": "bad field",
        }
        diag = Diagnostic.from_dict(raw)
        assert diag.severity == "error"
        assert diag.phase == "validate"
        assert diag.subject == "ast.root"
        assert diag.code == "schema_validation_error"
        assert diag.message == "bad field"
        assert diag.span is None

    def test_partial_dict_uses_defaults(self) -> None:
        diag = Diagnostic.from_dict({"message": "something happened"})
        assert diag.severity == "info"
        assert diag.phase == "unknown"
        assert diag.subject == ""
        assert diag.code == "unknown"
        assert diag.message == "something happened"

    def test_extra_keys_ignored(self) -> None:
        raw = {
            "severity": "warning",
            "phase": "parse",
            "subject": "token",
            "code": "w001",
            "message": "odd token",
            "extra_field": 42,
            "another": True,
        }
        diag = Diagnostic.from_dict(raw)
        assert diag.severity == "warning"
        assert diag.code == "w001"

    def test_with_span(self) -> None:
        raw = {
            "severity": "error",
            "phase": "parse",
            "subject": "token",
            "code": "e001",
            "message": "unexpected token",
            "span": {
                "start": {"line": 1, "column": 5, "offset": 4},
                "end": {"line": 1, "column": 10, "offset": 9},
            },
        }
        diag = Diagnostic.from_dict(raw)
        assert diag.span is not None
        assert diag.span.start.line == 1
        assert diag.span.end.column == 10


# ---------------------------------------------------------------------------
# format_diagnostics — plain mode
# ---------------------------------------------------------------------------

class TestPlainMode:
    def test_plain_output_lines(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", show_hints=False)
        lines = output.strip().split("\n")
        # 5 diagnostics -> 5 lines
        assert len(lines) == 5

    def test_plain_deterministic_order(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", show_hints=False)
        lines = output.strip().split("\n")
        # errors first, then warnings, then info
        assert lines[0].startswith("[ERROR]")
        assert lines[1].startswith("[ERROR]")
        assert lines[2].startswith("[WARNING]")
        assert lines[3].startswith("[WARNING]")
        assert lines[4].startswith("[INFO]")

    def test_plain_line_format(self) -> None:
        diags = [
            Diagnostic(
                severity="warning",
                phase="normalize",
                subject="x",
                code="c1",
                message="msg",
            )
        ]
        output = format_diagnostics(diags, mode="plain", show_hints=False)
        assert output == "[WARNING] phase:normalize code:c1 subject:x \u2014 msg"

    def test_plain_with_hints(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", show_hints=True)
        assert "hint:" in output
        assert REMEDIATION_HINTS["stubbed_primitive"] in output

    def test_plain_without_hints(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", show_hints=False)
        assert "hint:" not in output


# ---------------------------------------------------------------------------
# format_diagnostics — grouped mode
# ---------------------------------------------------------------------------

class TestGroupedMode:
    def test_grouped_has_section_headers(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="grouped", show_hints=False)
        assert "--- ERROR ---" in output
        assert "--- WARNING ---" in output
        assert "--- INFO ---" in output

    def test_grouped_sections_in_severity_order(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="grouped", show_hints=False)
        error_pos = output.index("--- ERROR ---")
        warning_pos = output.index("--- WARNING ---")
        info_pos = output.index("--- INFO ---")
        assert error_pos < warning_pos < info_pos

    def test_grouped_omits_empty_sections(self) -> None:
        diags = [{"severity": "info", "phase": "p", "subject": "s", "code": "c", "message": "m"}]
        output = format_diagnostics(diags, mode="grouped", show_hints=False)
        assert "--- ERROR ---" not in output
        assert "--- WARNING ---" not in output
        assert "--- INFO ---" in output


# ---------------------------------------------------------------------------
# format_diagnostics — json mode
# ---------------------------------------------------------------------------

class TestJsonMode:
    def test_json_parses(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="json")
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 5

    def test_json_deterministic(self) -> None:
        a = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="json")
        b = format_diagnostics(list(reversed(SAMPLE_DIAGNOSTICS)), mode="json")
        assert a == b

    def test_json_keys_sorted(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="json")
        parsed = json.loads(output)
        for entry in parsed:
            keys = list(entry.keys())
            assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Color output
# ---------------------------------------------------------------------------

class TestColor:
    def test_color_contains_ansi_escapes(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", color=True, show_hints=False)
        assert "\033[31m" in output  # red for error
        assert "\033[33m" in output  # yellow for warning
        assert "\033[34m" in output  # blue for info
        assert "\033[0m" in output   # reset

    def test_no_color_no_escapes(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", color=False, show_hints=False)
        assert "\033[" not in output

    def test_grouped_color_headers(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="grouped", color=True, show_hints=False)
        assert "\033[31m" in output


# ---------------------------------------------------------------------------
# Remediation hints
# ---------------------------------------------------------------------------

class TestRemediationHints:
    def test_known_codes_have_hints(self) -> None:
        for code in (
            "stubbed_primitive",
            "schema_validation_error",
            "evaluator_kind_canonicalized",
            "frame_incomplete",
            "baseline_mode_invalid",
        ):
            assert code in REMEDIATION_HINTS

    def test_hints_appear_in_output(self) -> None:
        diags = [
            {
                "severity": "warning",
                "phase": "normalize",
                "subject": "x",
                "code": "evaluator_kind_canonicalized",
                "message": "Canonicalized kind",
            }
        ]
        output = format_diagnostics(diags, mode="plain", show_hints=True)
        assert "hint:" in output
        assert REMEDIATION_HINTS["evaluator_kind_canonicalized"] in output

    def test_unknown_code_no_hint(self) -> None:
        diags = [
            {
                "severity": "info",
                "phase": "p",
                "subject": "s",
                "code": "totally_unknown_code",
                "message": "m",
            }
        ]
        output = format_diagnostics(diags, mode="plain", show_hints=True)
        assert "hint:" not in output


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------

class TestDeterministicOrdering:
    def test_same_output_regardless_of_input_order(self) -> None:
        a = format_diagnostics(SAMPLE_DIAGNOSTICS, mode="plain", show_hints=False)
        b = format_diagnostics(list(reversed(SAMPLE_DIAGNOSTICS)), mode="plain", show_hints=False)
        assert a == b

    def test_secondary_sort_by_phase_code_subject(self) -> None:
        diags = [
            {"severity": "error", "phase": "z", "subject": "a", "code": "c1", "message": "m1"},
            {"severity": "error", "phase": "a", "subject": "a", "code": "c1", "message": "m2"},
        ]
        output = format_diagnostics(diags, mode="plain", show_hints=False)
        lines = output.strip().split("\n")
        assert "phase:a" in lines[0]
        assert "phase:z" in lines[1]


# ---------------------------------------------------------------------------
# Mixed input types (Diagnostic objects + raw dicts)
# ---------------------------------------------------------------------------

class TestMixedInput:
    def test_accepts_diagnostic_objects(self) -> None:
        diags = [
            Diagnostic(severity="info", phase="p", subject="s", code="c", message="m"),
        ]
        output = format_diagnostics(diags, mode="plain", show_hints=False)
        assert "[INFO]" in output

    def test_accepts_raw_dicts(self) -> None:
        output = format_diagnostics(SAMPLE_DIAGNOSTICS[:1], mode="plain", show_hints=False)
        assert "[WARNING]" in output

    def test_accepts_mixed_list(self) -> None:
        mixed = [
            Diagnostic(severity="error", phase="p", subject="s", code="c", message="m1"),
            {"severity": "info", "phase": "q", "subject": "t", "code": "d", "message": "m2"},
        ]
        output = format_diagnostics(mixed, mode="plain", show_hints=False)
        lines = output.strip().split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("[ERROR]")
        assert lines[1].startswith("[INFO]")
