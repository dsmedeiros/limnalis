"""Tests for lint, analyze, symbols, and explain CLI commands and analysis functions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from limnalis.analysis import analyze_structure, extract_symbols
from limnalis.cli import main
from limnalis.loader import normalize_surface_file

MINIMAL_BUNDLE = Path(__file__).resolve().parent.parent / "examples" / "minimal_bundle.lmn"


# ---------------------------------------------------------------------------
# extract_symbols tests
# ---------------------------------------------------------------------------


class TestExtractSymbols:
    """Tests for the extract_symbols function."""

    def test_minimal_bundle_symbols(self) -> None:
        result = normalize_surface_file(MINIMAL_BUNDLE, validate_schema=True)
        assert result.canonical_ast is not None
        symbols = extract_symbols(result.canonical_ast)

        assert symbols["bundle"] == ["minimal_bundle"]
        assert symbols["evaluators"] == ["ev0"]
        assert symbols["claim_blocks"] == ["local#1"]
        assert symbols["claims"] == ["c1"]
        assert symbols["bridges"] == []
        assert symbols["anchors"] == []
        assert symbols["evidence"] == []
        assert symbols["baselines"] == []

    def test_all_lists_sorted(self) -> None:
        result = normalize_surface_file(MINIMAL_BUNDLE, validate_schema=True)
        assert result.canonical_ast is not None
        symbols = extract_symbols(result.canonical_ast)

        for key, ids in symbols.items():
            assert ids == sorted(ids), f"{key} list is not sorted"


# ---------------------------------------------------------------------------
# analyze_structure tests
# ---------------------------------------------------------------------------


class TestAnalyzeStructure:
    """Tests for the analyze_structure function."""

    def test_minimal_bundle_no_errors(self) -> None:
        result = normalize_surface_file(MINIMAL_BUNDLE, validate_schema=True)
        assert result.canonical_ast is not None
        diagnostics = analyze_structure(result.canonical_ast)

        # No error-severity diagnostics expected
        errors = [d for d in diagnostics if d["severity"] == "error"]
        assert errors == []

    def test_diagnostics_are_dicts(self) -> None:
        result = normalize_surface_file(MINIMAL_BUNDLE, validate_schema=True)
        assert result.canonical_ast is not None
        diagnostics = analyze_structure(result.canonical_ast)

        for d in diagnostics:
            assert isinstance(d, dict)
            assert "severity" in d
            assert "phase" in d
            assert "code" in d
            assert "subject" in d
            assert "message" in d

    def test_diagnostics_have_analysis_phase(self) -> None:
        result = normalize_surface_file(MINIMAL_BUNDLE, validate_schema=True)
        assert result.canonical_ast is not None
        diagnostics = analyze_structure(result.canonical_ast)

        for d in diagnostics:
            assert d["phase"] == "analysis"


# ---------------------------------------------------------------------------
# CLI: lint command
# ---------------------------------------------------------------------------


class TestLintCommand:
    """Tests for ``limnalis lint``."""

    def test_lint_valid_file_exit_zero(self) -> None:
        exit_code = main(["lint", str(MINIMAL_BUNDLE)])
        assert exit_code == 0

    def test_lint_json_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        main(["lint", str(MINIMAL_BUNDLE), "--format", "json"])
        captured = capsys.readouterr()
        # JSON output should be valid JSON (may be empty array)
        if captured.out.strip():
            parsed = json.loads(captured.out)
            assert isinstance(parsed, list)

    def test_lint_plain_format(self) -> None:
        exit_code = main(["lint", str(MINIMAL_BUNDLE), "--format", "plain"])
        assert exit_code == 0


# ---------------------------------------------------------------------------
# CLI: symbols command
# ---------------------------------------------------------------------------


class TestSymbolsCommand:
    """Tests for ``limnalis symbols``."""

    def test_symbols_contains_expected_ids(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(["symbols", str(MINIMAL_BUNDLE)])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "minimal_bundle" in captured.out
        assert "ev0" in captured.out
        assert "c1" in captured.out

    def test_symbols_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["symbols", str(MINIMAL_BUNDLE), "--json"])
        assert exit_code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["bundle"] == ["minimal_bundle"]
        assert "ev0" in data["evaluators"]


# ---------------------------------------------------------------------------
# CLI: explain command
# ---------------------------------------------------------------------------


class TestExplainCommand:
    """Tests for ``limnalis explain``."""

    def test_explain_known_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["explain", "stubbed_primitive"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "stubbed_primitive" in captured.out
        assert "plugin registry" in captured.out.lower()

    def test_explain_unknown_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["explain", "nonexistent_code_xyz"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "No hint available for code: nonexistent_code_xyz" in captured.out
