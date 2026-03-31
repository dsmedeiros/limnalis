"""Tests for M6B CLI commands: summarize and list-summary-policies."""

from __future__ import annotations

import json
from pathlib import Path

from limnalis.cli import main

ROOT = Path(__file__).resolve().parents[1]
MINIMAL_BUNDLE = str(ROOT / "examples" / "minimal_bundle.lmn")


class TestSummarizeCommand:
    def test_summarize_command_runs(self, capsys) -> None:
        """Run summarize on minimal_bundle.lmn with default policy, verify exit code 0."""
        code = main(["summarize", MINIMAL_BUNDLE])
        assert code == 0

    def test_summarize_command_json_output(self, capsys) -> None:
        """Run with --json, verify output is valid JSON containing expected keys."""
        code = main(["summarize", "--json", MINIMAL_BUNDLE])
        captured = capsys.readouterr()

        assert code == 0
        payload = json.loads(captured.out)
        assert "policy_id" in payload
        assert "scope" in payload
        assert "normative" in payload

    def test_summarize_command_severity_max(self, capsys) -> None:
        """Run with --policy severity_max, verify exit code 0."""
        code = main(["summarize", "--policy", "severity_max", MINIMAL_BUNDLE])
        assert code == 0

    def test_summarize_command_invalid_file(self, tmp_path: Path, capsys) -> None:
        """Run with nonexistent file, verify non-zero exit code."""
        nonexistent = str(tmp_path / "nonexistent.lmn")
        code = main(["summarize", nonexistent])
        assert code != 0

    def test_summarize_command_invalid_policy(self, capsys) -> None:
        """Run with --policy nonexistent, verify non-zero exit code."""
        code = main(["summarize", "--policy", "nonexistent", MINIMAL_BUNDLE])
        assert code != 0


class TestListSummaryPoliciesCommand:
    def test_list_summary_policies_runs(self, capsys) -> None:
        """Run list-summary-policies, verify exit code 0 and output mentions built-in policies."""
        code = main(["list-summary-policies"])
        captured = capsys.readouterr()

        assert code == 0
        output = captured.out
        assert "passthrough_normative" in output
        assert "severity_max" in output
        assert "majority_vote" in output
