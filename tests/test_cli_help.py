"""Help text snapshot and consistency tests for all CLI commands.

Verifies that:
- Main help includes all registered subcommands.
- Each command group lists its subcommands.
- Every new top-level command has help text.
- The ``--no-color`` global flag is present.
"""
from __future__ import annotations

import re
import subprocess
import sys
from typing import List

import pytest


def _run_help(*args: str) -> str:
    """Run ``python -m limnalis <args> --help`` and return stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "limnalis", *args, "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"help failed: {result.stderr}"
    return result.stdout


# ---------------------------------------------------------------------------
# Main help includes all new commands
# ---------------------------------------------------------------------------


class TestMainHelp:
    """Tests for the top-level ``limnalis --help`` output."""

    @pytest.fixture(scope="class")
    def help_text(self) -> str:
        return _run_help()

    def test_includes_inspect(self, help_text: str) -> None:
        assert "inspect" in help_text

    def test_includes_lint(self, help_text: str) -> None:
        assert "lint" in help_text

    def test_includes_analyze(self, help_text: str) -> None:
        assert "analyze" in help_text

    def test_includes_symbols(self, help_text: str) -> None:
        assert "symbols" in help_text

    def test_includes_explain(self, help_text: str) -> None:
        assert "explain" in help_text

    def test_includes_visualize(self, help_text: str) -> None:
        assert "visualize" in help_text

    def test_includes_doctor(self, help_text: str) -> None:
        assert "doctor" in help_text

    def test_includes_init(self, help_text: str) -> None:
        assert "init" in help_text

    def test_no_color_flag(self, help_text: str) -> None:
        assert "--no-color" in help_text


# ---------------------------------------------------------------------------
# Inspect subcommands
# ---------------------------------------------------------------------------


class TestInspectHelp:
    @pytest.fixture(scope="class")
    def help_text(self) -> str:
        return _run_help("inspect")

    def test_lists_ast(self, help_text: str) -> None:
        assert "ast" in help_text

    def test_lists_normalized(self, help_text: str) -> None:
        assert "normalized" in help_text

    def test_lists_trace(self, help_text: str) -> None:
        assert "trace" in help_text

    def test_lists_machine_state(self, help_text: str) -> None:
        assert "machine-state" in help_text

    def test_lists_license(self, help_text: str) -> None:
        assert "license" in help_text


# ---------------------------------------------------------------------------
# Visualize subcommands
# ---------------------------------------------------------------------------


class TestVisualizeHelp:
    @pytest.fixture(scope="class")
    def help_text(self) -> str:
        return _run_help("visualize")

    def test_lists_frame_graph(self, help_text: str) -> None:
        assert "frame-graph" in help_text

    def test_lists_evaluator_graph(self, help_text: str) -> None:
        assert "evaluator-graph" in help_text

    def test_lists_evidence_graph(self, help_text: str) -> None:
        assert "evidence-graph" in help_text


# ---------------------------------------------------------------------------
# Init subcommands
# ---------------------------------------------------------------------------


class TestInitHelp:
    @pytest.fixture(scope="class")
    def help_text(self) -> str:
        return _run_help("init")

    def test_lists_bundle(self, help_text: str) -> None:
        assert "bundle" in help_text

    def test_lists_plugin_pack(self, help_text: str) -> None:
        assert "plugin-pack" in help_text

    def test_lists_conformance_case(self, help_text: str) -> None:
        assert "conformance-case" in help_text or "conformance" in help_text


# ---------------------------------------------------------------------------
# Individual top-level commands have help text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    ["lint", "analyze", "symbols", "explain", "doctor"],
)
def test_toplevel_command_has_help(command: str) -> None:
    text = _run_help(command)
    # Help text should be non-trivial (more than just usage line)
    assert len(text) > 40, f"{command} --help is too short"


# ---------------------------------------------------------------------------
# Snapshot: main help text for regression detection
# ---------------------------------------------------------------------------


_MAIN_HELP_EXPECTED_COMMANDS = [
    "inspect",
    "lint",
    "analyze",
    "symbols",
    "explain",
    "visualize",
    "init",
    "doctor",
]


def test_main_help_snapshot() -> None:
    """Snapshot-style regression test: all expected commands appear in help."""
    text = _run_help()
    for cmd in _MAIN_HELP_EXPECTED_COMMANDS:
        assert cmd in text, f"main help missing expected command: {cmd}"
    # Global flags
    assert "--no-color" in text
    assert "--version" in text
