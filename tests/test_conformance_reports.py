"""Tests for conformance report generation (JSON and Markdown formats).

T9: Conformance report tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from limnalis.cli import main

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# T9.1 – JSON report produces valid JSON with expected structure
# ---------------------------------------------------------------------------


class TestConformanceReportJson:
    """Test conformance report --format json output."""

    def test_json_report_is_valid_json(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        # Must be valid JSON
        report = json.loads(captured.out)
        assert isinstance(report, dict)

    def test_json_report_has_expected_structure(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        report = json.loads(captured.out)
        # Expected top-level keys
        assert "version" in report
        assert "total" in report
        assert "passed" in report
        assert "failed" in report
        assert "errors" in report
        assert "summary" in report
        assert "cases" in report

        # Summary should have counts
        summary = report["summary"]
        assert "total" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "errors" in summary

        # Cases should be a list
        assert isinstance(report["cases"], list)
        assert len(report["cases"]) > 0

    def test_json_report_case_entries_have_required_fields(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        report = json.loads(captured.out)
        for case_entry in report["cases"]:
            assert "case_id" in case_entry
            assert "name" in case_entry
            assert "status" in case_entry
            assert case_entry["status"] in ("pass", "fail", "error", "known_deviation")
            assert "mismatches" in case_entry
            assert isinstance(case_entry["mismatches"], list)

    def test_json_report_totals_are_consistent(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        report = json.loads(captured.out)
        summary = report["summary"]
        total = summary["total"]
        passed = summary["passed"]
        failed = summary["failed"]
        errors = summary["errors"]
        skipped = summary.get("skipped", 0)

        assert total == passed + failed + errors + skipped
        assert total == len(report["cases"])
        assert report["failed"] == failed + skipped
        assert report["total"] == report["passed"] + report["failed"] + report["errors"]


# ---------------------------------------------------------------------------
# T9.2 – Markdown report produces readable markdown
# ---------------------------------------------------------------------------


class TestConformanceReportMarkdown:
    """Test conformance report --format markdown output."""

    def test_markdown_report_has_header(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "markdown"])
        captured = capsys.readouterr()
        assert code == 0

        lines = captured.out.strip().split("\n")
        assert len(lines) > 0
        # Should start with a markdown header
        assert lines[0].startswith("# Conformance Report")

    def test_markdown_report_has_summary(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "markdown"])
        captured = capsys.readouterr()
        assert code == 0

        # Should contain summary statistics
        assert "Summary" in captured.out
        assert "Total" in captured.out
        assert "Passed" in captured.out

    def test_markdown_report_has_results_table(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "markdown"])
        captured = capsys.readouterr()
        assert code == 0

        # Should contain a markdown table
        assert "| Case |" in captured.out
        assert "|---" in captured.out


# ---------------------------------------------------------------------------
# T9.3 – Report includes version metadata
# ---------------------------------------------------------------------------


class TestConformanceReportVersion:
    """Test that reports include version metadata."""

    def test_json_report_includes_version(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        report = json.loads(captured.out)
        assert "version" in report
        version = report["version"]
        assert isinstance(version, dict)
        assert "package" in version
        assert "spec" in version

    def test_markdown_report_includes_version(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "markdown"])
        captured = capsys.readouterr()
        assert code == 0

        # Version info should appear in the report
        assert "limnalis" in captured.out.lower()
        assert "Spec:" in captured.out


# ---------------------------------------------------------------------------
# T9.4 – Failing case produces readable diff output in the report
# ---------------------------------------------------------------------------


class TestConformanceReportFailingCases:
    """Test that failing cases produce readable output."""

    def test_failing_case_has_mismatches_in_json_report(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        report = json.loads(captured.out)

        # Check if any cases have mismatches (fail or error status)
        failing = [c for c in report["cases"] if c["status"] in ("fail", "error")]

        # If there are failing cases, verify their mismatches are readable
        for case_entry in failing:
            if case_entry["status"] == "fail":
                # Mismatches should be a list of strings
                assert isinstance(case_entry["mismatches"], list)
                for m in case_entry["mismatches"]:
                    assert isinstance(m, str)
            elif case_entry["status"] == "error":
                # Error cases should have an error field
                assert "error" in case_entry

    def test_report_diagnostics_count_is_non_negative(self, capsys) -> None:
        code = main(["conformance", "report", "--format", "json"])
        captured = capsys.readouterr()
        assert code == 0

        report = json.loads(captured.out)
        for case_entry in report["cases"]:
            assert "diagnostics_count" in case_entry
            assert case_entry["diagnostics_count"] >= 0
