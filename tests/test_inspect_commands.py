"""Tests for ``limnalis inspect`` CLI subcommands."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from limnalis.cli import main

MINIMAL_BUNDLE = Path("examples/minimal_bundle.lmn")


def _run_cli(*argv: str) -> tuple[int, str, str]:
    """Run the CLI, capturing stdout and stderr.  Returns (exit_code, stdout, stderr)."""
    import io
    import sys

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        rc = main(list(argv))
    except SystemExit as exc:
        rc = exc.code if exc.code is not None else 0
    finally:
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        sys.stdout, sys.stderr = old_out, old_err
    return rc, out, err


# ---------------------------------------------------------------------------
# inspect ast
# ---------------------------------------------------------------------------


class TestInspectAst:
    def test_human_output(self) -> None:
        rc, out, err = _run_cli("inspect", "ast", str(MINIMAL_BUNDLE))
        assert rc == 0
        assert "Bundle:" in out
        assert "Evaluators (1)" in out
        assert "Claim Blocks (1)" in out

    def test_json_output(self) -> None:
        rc, out, err = _run_cli("inspect", "ast", "--json", str(MINIMAL_BUNDLE))
        assert rc == 0
        data = json.loads(out)
        assert "bundle_id" in data
        assert data["evaluator_count"] == 1
        assert data["claim_block_count"] == 1
        assert data["total_claims"] >= 1

    def test_missing_file(self) -> None:
        rc, out, err = _run_cli("inspect", "ast", "nonexistent.lmn")
        assert rc == 1
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# inspect normalized
# ---------------------------------------------------------------------------


class TestInspectNormalized:
    def test_valid_json(self) -> None:
        rc, out, err = _run_cli("inspect", "normalized", str(MINIMAL_BUNDLE))
        assert rc == 0
        data = json.loads(out)
        assert data["node"] == "Bundle"
        assert "evaluators" in data

    def test_missing_file(self) -> None:
        rc, out, err = _run_cli("inspect", "normalized", "nonexistent.lmn")
        assert rc == 1


# ---------------------------------------------------------------------------
# inspect trace
# ---------------------------------------------------------------------------


class TestInspectTrace:
    def test_human_output(self) -> None:
        rc, out, err = _run_cli("inspect", "trace", str(MINIMAL_BUNDLE))
        assert rc == 0
        # Should contain phase numbers
        assert "Phase " in out

    def test_json_output(self) -> None:
        rc, out, err = _run_cli("inspect", "trace", "--json", str(MINIMAL_BUNDLE))
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)
        if data:
            assert "phase" in data[0]
            assert "primitive" in data[0]

    def test_phase_numbers_present(self) -> None:
        rc, out, err = _run_cli("inspect", "trace", str(MINIMAL_BUNDLE))
        assert rc == 0
        lines = [l for l in out.strip().splitlines() if l.startswith("Phase ")]
        assert len(lines) > 0
        # Verify phase numbers are integers
        for line in lines:
            phase_str = line.split(":")[0].replace("Phase ", "")
            int(phase_str)  # Should not raise

    def test_missing_file(self) -> None:
        rc, out, err = _run_cli("inspect", "trace", "nonexistent.lmn")
        assert rc == 1


# ---------------------------------------------------------------------------
# inspect machine-state
# ---------------------------------------------------------------------------


class TestInspectMachineState:
    def test_human_output(self) -> None:
        rc, out, err = _run_cli("inspect", "machine-state", str(MINIMAL_BUNDLE))
        assert rc == 0
        assert "Resolution Store:" in out
        assert "Baseline Store:" in out
        assert "Adequacy Store:" in out
        assert "Evidence Views:" in out
        assert "Transport Store:" in out

    def test_json_output(self) -> None:
        rc, out, err = _run_cli("inspect", "machine-state", "--json", str(MINIMAL_BUNDLE))
        assert rc == 0
        data = json.loads(out)
        assert "resolution_store" in data

    def test_missing_file(self) -> None:
        rc, out, err = _run_cli("inspect", "machine-state", "nonexistent.lmn")
        assert rc == 1


# ---------------------------------------------------------------------------
# inspect license
# ---------------------------------------------------------------------------


class TestInspectLicense:
    def test_human_output(self) -> None:
        rc, out, err = _run_cli("inspect", "license", str(MINIMAL_BUNDLE))
        assert rc == 0
        # May or may not have license results depending on the bundle
        # but should not crash

    def test_json_output(self) -> None:
        rc, out, err = _run_cli("inspect", "license", "--json", str(MINIMAL_BUNDLE))
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, dict)

    def test_missing_file(self) -> None:
        rc, out, err = _run_cli("inspect", "license", "nonexistent.lmn")
        assert rc == 1


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_ast_deterministic(self) -> None:
        """Two runs of inspect ast --json produce identical output."""
        _, out1, _ = _run_cli("inspect", "ast", "--json", str(MINIMAL_BUNDLE))
        _, out2, _ = _run_cli("inspect", "ast", "--json", str(MINIMAL_BUNDLE))
        assert out1 == out2

    def test_trace_deterministic(self) -> None:
        """Two runs of inspect trace --json produce identical output."""
        _, out1, _ = _run_cli("inspect", "trace", "--json", str(MINIMAL_BUNDLE))
        _, out2, _ = _run_cli("inspect", "trace", "--json", str(MINIMAL_BUNDLE))
        assert out1 == out2
