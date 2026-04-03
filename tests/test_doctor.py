"""Tests for ``limnalis doctor`` command."""
from __future__ import annotations

import json

import pytest

from limnalis.cli import main
from limnalis.cli.doctor_cmd import _run_checks


class TestDoctorCommand:
    """Integration tests for the doctor CLI subcommand."""

    def test_doctor_exit_zero(self) -> None:
        """Doctor returns exit 0 in a healthy test environment."""
        rc = main(["doctor"])
        assert rc == 0

    def test_doctor_json_valid(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--json flag produces valid JSON output."""
        rc = main(["doctor", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) > 0
        for item in data:
            assert "name" in item
            assert "status" in item
            assert "detail" in item

    def test_doctor_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Default text output contains expected check names."""
        rc = main(["doctor"])
        assert rc == 0
        output = capsys.readouterr().out
        expected_checks = [
            "Python version",
            "Pydantic version",
            "Lark parser",
            "JSON schemas",
            "Fixture corpus",
            "Plugin registry",
            "Example files",
        ]
        for name in expected_checks:
            assert name in output, f"Expected check '{name}' not found in output"

    def test_doctor_all_checks_present(self) -> None:
        """All expected checks run and produce results."""
        results = _run_checks()
        assert len(results) == 7
        names = [r.name for r in results]
        assert "Python version" in names
        assert "Pydantic version" in names
        assert "Lark parser" in names
        assert "JSON schemas" in names
        assert "Fixture corpus" in names
        assert "Plugin registry" in names
        assert "Example files" in names

    def test_doctor_pass_status_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Each line uses [PASS], [FAIL], or [SKIP] prefix."""
        main(["doctor"])
        output = capsys.readouterr().out
        for line in output.strip().splitlines():
            assert line.startswith("[PASS]") or line.startswith("[FAIL]") or line.startswith("[SKIP]"), (
                f"Unexpected line format: {line}"
            )
