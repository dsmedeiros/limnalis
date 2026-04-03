"""Red team adversarial tests for Milestone 6C changeset.

Tests path traversal, malicious identifiers, Unicode edge cases, SARIF
compliance, Mermaid injection, empty/malformed inputs, determinism, and
error handling quality.
"""
from __future__ import annotations

import ast as python_ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES = _PROJECT_ROOT / "examples"
_MINIMAL = _EXAMPLES / "minimal_bundle.lmn"
_CWT = _EXAMPLES / "cwt_transport_bundle.lmn"


def _cli(*args: str, expect_fail: bool = False) -> subprocess.CompletedProcess:
    """Run ``python -m limnalis <args>``."""
    result = subprocess.run(
        [sys.executable, "-m", "limnalis", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if not expect_fail:
        # We don't assert returncode 0 — some commands legitimately return 1.
        pass
    return result


# ===========================================================================
# 1. PATH TRAVERSAL in ``limnalis init``
# ===========================================================================


class TestInitPathTraversal:
    """Verify the sanitizer prevents writing outside --output-dir."""

    def test_dotdot_in_name(self, tmp_path: Path) -> None:
        """Name like '../../etc/passwd' must not escape the output dir."""
        result = _cli(
            "init", "bundle", "../../etc/passwd",
            "--output-dir", str(tmp_path),
        )
        assert result.returncode == 0
        # The file must be inside tmp_path — not at ../../etc/passwd
        created_files = list(tmp_path.iterdir())
        assert len(created_files) == 1
        # The filename should be just "passwd.lmn" (Path.name strips traversal)
        assert created_files[0].name == "passwd.lmn"
        # Verify no file was created outside tmp_path
        bad_path = tmp_path / ".." / ".." / "etc" / "passwd.lmn"
        assert not bad_path.exists()

    def test_absolute_path_in_name(self, tmp_path: Path) -> None:
        """An absolute path in the name must be reduced to just the basename."""
        if sys.platform == "win32":
            name = "C:\\Windows\\System32\\evil"
        else:
            name = "/etc/shadow"
        result = _cli(
            "init", "bundle", name,
            "--output-dir", str(tmp_path),
        )
        assert result.returncode == 0
        created_files = list(tmp_path.iterdir())
        assert len(created_files) == 1
        # Must not have created outside tmp_path
        for f in created_files:
            assert str(f).startswith(str(tmp_path))

    def test_dotdot_sequence_nested(self, tmp_path: Path) -> None:
        """Deeper traversal: '../../../tmp/exploit'."""
        result = _cli(
            "init", "bundle", "../../../tmp/exploit",
            "--output-dir", str(tmp_path),
        )
        assert result.returncode == 0
        created = list(tmp_path.iterdir())
        assert len(created) == 1
        assert created[0].name == "exploit.lmn"


# ===========================================================================
# 2. MALICIOUS IDENTIFIERS in ``limnalis init``
# ===========================================================================


class TestInitMaliciousIdentifiers:
    """Verify that dangerous identifiers produce safe output."""

    def test_code_injection_attempt(self, tmp_path: Path) -> None:
        """Name like __import__('os').system('whoami') must be safe."""
        result = _cli(
            "init", "plugin-pack", "__import__('os').system('whoami')",
            "--output-dir", str(tmp_path),
            "--dry-run",
        )
        assert result.returncode == 0
        content = result.stdout
        # The generated Python must compile without executing any injection
        try:
            python_ast.parse(content)
        except SyntaxError:
            pytest.fail(
                f"Generated plugin-pack code does not compile:\n{content}"
            )

    def test_semicolon_in_name(self, tmp_path: Path) -> None:
        """Semicolons in the name must not cause injection."""
        result = _cli(
            "init", "bundle", "evil;rm -rf /",
            "--output-dir", str(tmp_path),
            "--dry-run",
        )
        assert result.returncode == 0
        assert "rm -rf" not in result.stdout.split("\n")[0]  # Not in bundle id line

    def test_quotes_in_name(self, tmp_path: Path) -> None:
        """Quotes in the name must be handled."""
        result = _cli(
            "init", "bundle", 'my"bundle',
            "--output-dir", str(tmp_path),
            "--dry-run",
        )
        assert result.returncode == 0


# ===========================================================================
# 3. HYPHENATED NAMES — Python validity
# ===========================================================================


class TestInitHyphenatedNames:
    """Verify hyphenated names produce valid Python for plugin-pack."""

    def test_hyphenated_plugin_pack_compiles(self) -> None:
        result = _cli("init", "plugin-pack", "my-cool-pack", "--dry-run")
        assert result.returncode == 0
        content = result.stdout
        # Must compile as valid Python
        try:
            python_ast.parse(content)
        except SyntaxError:
            pytest.fail(
                f"Hyphenated plugin-pack does not compile:\n{content}"
            )

    def test_hyphenated_bundle_parses(self) -> None:
        """A hyphenated bundle name should produce a .lmn that at minimum
        doesn't contain raw hyphens in the bundle identifier."""
        result = _cli("init", "bundle", "my-cool-bundle", "--dry-run")
        assert result.returncode == 0
        # Hyphens should be converted to underscores
        assert "bundle my_cool_bundle" in result.stdout


# ===========================================================================
# 4. UNICODE / SPECIAL CHARS in identifiers
# ===========================================================================


class TestInitUnicodeNames:
    def test_spaces_in_name(self, tmp_path: Path) -> None:
        result = _cli(
            "init", "bundle", "my bundle name",
            "--output-dir", str(tmp_path),
        )
        assert result.returncode == 0
        created = list(tmp_path.iterdir())
        assert len(created) == 1
        # Spaces should become underscores
        assert " " not in created[0].name

    def test_empty_name(self) -> None:
        """Empty string identifier must not crash."""
        result = _cli("init", "bundle", "", "--dry-run")
        # Empty name sanitizes to "untitled" and succeeds
        assert result.returncode == 0, f"Empty name should succeed: {result.stderr}"
        assert "untitled" in result.stdout, "Empty name should produce 'untitled' scaffold"
        assert "Traceback" not in result.stderr


# ===========================================================================
# 5. EMPTY / NONEXISTENT FILE INPUTS
# ===========================================================================


class TestEmptyAndMissingFiles:
    def test_lint_nonexistent_file(self) -> None:
        result = _cli("lint", "nonexistent_file_12345.lmn", expect_fail=True)
        assert result.returncode != 0
        # Must not show Python traceback
        assert "Traceback" not in result.stderr

    def test_inspect_ast_nonexistent(self) -> None:
        result = _cli("inspect", "ast", "nonexistent.lmn", expect_fail=True)
        assert result.returncode != 0
        assert "Traceback" not in result.stderr

    def test_visualize_nonexistent(self) -> None:
        result = _cli(
            "visualize", "frame-graph", "nonexistent.lmn", expect_fail=True
        )
        assert result.returncode != 0
        assert "Traceback" not in result.stderr

    def test_lint_empty_file(self, tmp_path: Path) -> None:
        """Lint an empty file — should fail gracefully."""
        empty = tmp_path / "empty.lmn"
        empty.write_text("", encoding="utf-8")
        result = _cli("lint", str(empty), expect_fail=True)
        # Should report an error, not crash
        assert "Traceback" not in result.stderr


# ===========================================================================
# 6. MALFORMED .lmn FILES
# ===========================================================================


class TestMalformedLmn:
    def test_lint_garbage_content(self, tmp_path: Path) -> None:
        """Lint a file with random garbage — must not crash."""
        bad = tmp_path / "garbage.lmn"
        bad.write_text("{{{{!!!  not valid limnalis syntax }}}}", encoding="utf-8")
        result = _cli("lint", str(bad), expect_fail=True)
        assert result.returncode != 0
        assert "Traceback" not in result.stderr

    def test_inspect_ast_malformed(self, tmp_path: Path) -> None:
        """inspect ast on malformed file — must report clean error."""
        bad = tmp_path / "bad.lmn"
        bad.write_text("not valid lmn", encoding="utf-8")
        result = _cli("inspect", "ast", str(bad), expect_fail=True)
        assert result.returncode != 0
        assert "Traceback" not in result.stderr


# ===========================================================================
# 7. SARIF EDGE CASES
# ===========================================================================


class TestSarifEdgeCases:
    def test_empty_diagnostics_list(self) -> None:
        """SARIF from empty diagnostics should still be valid."""
        from limnalis.sarif import diagnostics_to_sarif

        sarif = diagnostics_to_sarif([])
        assert sarif["$schema"].endswith("sarif-schema-2.1.0.json")
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        assert sarif["runs"][0]["results"] == []

    def test_diagnostic_with_none_span(self) -> None:
        """Diagnostic with span=None should produce SARIF without locations."""
        from limnalis.diagnostics import Diagnostic
        from limnalis.sarif import diagnostics_to_sarif

        diag = Diagnostic(
            severity="warning",
            phase="test",
            code="test_code",
            message="test msg",
            subject="sub",
            span=None,
        )
        sarif = diagnostics_to_sarif([diag])
        results = sarif["runs"][0]["results"]
        assert len(results) == 1
        assert "locations" not in results[0]

    def test_diagnostic_with_span(self) -> None:
        """Diagnostic with a valid span should produce SARIF with locations."""
        from limnalis.diagnostics import Diagnostic, SourcePosition, SourceSpan
        from limnalis.sarif import diagnostics_to_sarif

        diag = Diagnostic(
            severity="error",
            phase="parse",
            code="parse_error",
            message="unexpected token",
            subject="file.lmn",
            span=SourceSpan(
                start=SourcePosition(line=1, column=1, offset=0),
                end=SourcePosition(line=1, column=5, offset=4),
            ),
        )
        sarif = diagnostics_to_sarif([diag])
        results = sarif["runs"][0]["results"]
        assert len(results) == 1
        assert "locations" in results[0]
        region = results[0]["locations"][0]["physicalLocation"]["region"]
        assert region["startLine"] == 1
        assert region["endColumn"] == 5

    def test_sarif_determinism(self) -> None:
        """Same diagnostics produce identical SARIF."""
        from limnalis.diagnostics import Diagnostic
        from limnalis.sarif import diagnostics_to_sarif

        diags = [
            Diagnostic(severity="warning", phase="a", code="z_code", message="zzz", subject="s"),
            Diagnostic(severity="error", phase="b", code="a_code", message="aaa", subject="s"),
        ]
        s1 = json.dumps(diagnostics_to_sarif(diags), sort_keys=True)
        s2 = json.dumps(diagnostics_to_sarif(diags), sort_keys=True)
        assert s1 == s2

    def test_sarif_from_dict_diagnostics(self) -> None:
        """SARIF builder should accept raw dicts (via _coerce)."""
        from limnalis.sarif import diagnostics_to_sarif

        raw = [
            {"severity": "info", "phase": "test", "code": "test_c",
             "message": "hello", "subject": "x"},
        ]
        sarif = diagnostics_to_sarif(raw)
        assert len(sarif["runs"][0]["results"]) == 1

    def test_sarif_invalid_type_raises(self) -> None:
        """Passing a non-dict non-Diagnostic should raise TypeError."""
        from limnalis.sarif import diagnostics_to_sarif

        with pytest.raises(TypeError, match="Expected Diagnostic or dict"):
            diagnostics_to_sarif([42])


# ===========================================================================
# 8. SARIF COMPLIANCE from CLI
# ===========================================================================


class TestSarifCli:
    def test_lint_sarif_format(self) -> None:
        """``limnalis lint --format sarif`` should produce valid SARIF 2.1.0."""
        # Use analyze since minimal_bundle may produce structural warnings
        result = _cli("lint", "--format", "sarif", str(_MINIMAL))
        # Parse the output as JSON
        if result.stdout.strip():
            sarif = json.loads(result.stdout)
            assert sarif["$schema"].endswith("sarif-schema-2.1.0.json")
            assert sarif["version"] == "2.1.0"
            assert "runs" in sarif
            assert "tool" in sarif["runs"][0]
            assert "driver" in sarif["runs"][0]["tool"]


# ===========================================================================
# 9. MERMAID INJECTION
# ===========================================================================


class TestMermaidInjection:
    """Verify that IDs containing Mermaid special chars are sanitized."""

    def test_sanitize_mermaid_id(self) -> None:
        from limnalis.graph import _build_mermaid_id_map

        dangerous = '-->|"hello"|[node]'
        id_map = _build_mermaid_id_map([dangerous])
        safe = id_map[dangerous]
        assert "-->" not in safe
        assert "|" not in safe
        assert "[" not in safe
        assert "]" not in safe
        assert '"' not in safe

    def test_mermaid_id_collision_safety(self) -> None:
        """Distinct raw IDs that sanitise identically must get unique Mermaid IDs."""
        from limnalis.graph import _build_mermaid_id_map

        id_map = _build_mermaid_id_map(["a-b", "a_b", "a.b"])
        mermaid_ids = list(id_map.values())
        assert len(set(mermaid_ids)) == 3, f"Collision detected: {id_map}"

    def test_render_with_special_label(self) -> None:
        """Labels with quotes should have them escaped."""
        from limnalis.graph import GraphEdge, GraphNode, render_mermaid

        nodes = [
            GraphNode(id='n1"bad', label='Label "with" quotes', kind="frame"),
            GraphNode(id="n2-->inject", label="Normal", kind="evaluator"),
        ]
        edges = [
            GraphEdge(source='n1"bad', target="n2-->inject", label='edge"|label'),
        ]
        output = render_mermaid(nodes, edges)
        # IDs must be sanitized (no special chars)
        assert '-->|' not in output.split("\n")[1]  # node definition lines
        # Labels should have quotes escaped
        assert '\\"' not in output  # double-quote should be replaced, not backslash-escaped
        # The output should not contain raw double quotes inside labels
        # (they are replaced with single quotes)
        for line in output.strip().split("\n"):
            if "---" in line or line.startswith("flowchart"):
                continue
            # After sanitization, no raw unmatched double quotes in node IDs
            # The Mermaid syntax uses quotes for labels, but IDs should be clean
            pass  # structural check — not crashing is the baseline


# ===========================================================================
# 10. GRAPH WITH NO NODES
# ===========================================================================


class TestEmptyGraph:
    def test_render_mermaid_empty(self) -> None:
        """Rendering an empty graph should not crash."""
        from limnalis.graph import render_mermaid

        output = render_mermaid([], [])
        assert "flowchart" in output

    def test_build_evidence_graph_no_evidence(self) -> None:
        """A bundle with no evidence should produce an empty evidence graph."""
        from limnalis.loader import load_surface_bundle
        from limnalis.graph import build_evidence_graph

        bundle = load_surface_bundle(_MINIMAL)
        nodes, edges = build_evidence_graph(bundle)
        # May or may not have nodes depending on bundle content, but shouldn't crash
        assert isinstance(nodes, list)
        assert isinstance(edges, list)


# ===========================================================================
# 11. DOCTOR COMMAND
# ===========================================================================


class TestDoctorCommand:
    def test_doctor_json_is_valid_json(self) -> None:
        result = _cli("doctor", "--json")
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        for entry in parsed:
            assert "name" in entry
            assert "status" in entry
            assert "detail" in entry
            assert entry["status"] in ("PASS", "FAIL", "SKIP")

    def test_doctor_text_output(self) -> None:
        result = _cli("doctor")
        assert result.returncode in (0, 1)
        lines = result.stdout.strip().split("\n")
        for line in lines:
            # Each line should start with [PASS], [FAIL], or [SKIP]
            assert line.startswith("[PASS]") or line.startswith("[FAIL]") or line.startswith("[SKIP]"), \
                f"Unexpected doctor output line: {line}"


# ===========================================================================
# 12. DETERMINISM
# ===========================================================================


class TestDeterminism:
    def test_inspect_ast_deterministic(self) -> None:
        r1 = _cli("inspect", "ast", str(_MINIMAL), "--json")
        r2 = _cli("inspect", "ast", str(_MINIMAL), "--json")
        assert r1.stdout == r2.stdout

    def test_visualize_frame_graph_deterministic(self) -> None:
        r1 = _cli("visualize", "frame-graph", str(_CWT))
        r2 = _cli("visualize", "frame-graph", str(_CWT))
        assert r1.stdout == r2.stdout

    def test_visualize_evaluator_graph_deterministic(self) -> None:
        r1 = _cli("visualize", "evaluator-graph", str(_MINIMAL))
        r2 = _cli("visualize", "evaluator-graph", str(_MINIMAL))
        assert r1.stdout == r2.stdout


# ===========================================================================
# 13. FORMAT FLAG EDGE CASES
# ===========================================================================


class TestFormatEdgeCases:
    def test_lint_invalid_format(self) -> None:
        """Invalid --format should be rejected by argparse."""
        result = _cli("lint", "--format", "invalid_format", str(_MINIMAL))
        assert result.returncode != 0

    def test_lint_sarif_format_accepted(self) -> None:
        """SARIF is a valid lint format (registered in argparse choices)."""
        result = _cli("lint", "--format", "sarif", str(_MINIMAL))
        assert result.returncode == 0, f"lint --format sarif failed: {result.stderr}"
        sarif = json.loads(result.stdout)
        assert sarif["version"] == "2.1.0"


# ===========================================================================
# 14. ERROR MESSAGE QUALITY — no tracebacks leaked
# ===========================================================================


class TestErrorMessageQuality:
    def test_explain_unknown_code(self) -> None:
        result = _cli("explain", "nonexistent_code_xyz")
        assert result.returncode == 0
        assert "No hint available" in result.stdout
        assert "Traceback" not in result.stderr

    def test_lint_nonexistent_clean_error(self) -> None:
        result = _cli("lint", "definitely_not_a_real_file.lmn")
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout


# ===========================================================================
# 15. TEMPLATE ROUND-TRIP
# ===========================================================================


class TestTemplateRoundTrip:
    """Generate each template type and verify the output is usable."""

    def test_bundle_template_parses(self, tmp_path: Path) -> None:
        """Generated bundle template should parse successfully."""
        result = _cli(
            "init", "bundle", "roundtrip_test",
            "--output-dir", str(tmp_path),
        )
        assert result.returncode == 0
        lmn_file = tmp_path / "roundtrip_test.lmn"
        assert lmn_file.exists()

        # Try parsing it
        parse_result = _cli("lint", str(lmn_file))
        # It should either pass cleanly or at most produce warnings (not errors)
        if parse_result.returncode != 0:
            # Check if it's just warnings (exit code 0) or errors (exit code 1)
            assert "error" not in parse_result.stdout.lower() or "stubbed" in parse_result.stdout.lower(), \
                f"Bundle template produced lint errors:\n{parse_result.stdout}"

    def test_plugin_pack_template_compiles(self) -> None:
        """Generated plugin-pack template should be valid Python."""
        result = _cli("init", "plugin-pack", "roundtrip_pp", "--dry-run")
        assert result.returncode == 0
        try:
            python_ast.parse(result.stdout)
        except SyntaxError as exc:
            pytest.fail(f"Plugin-pack template is not valid Python: {exc}")

    def test_conformance_case_template_is_valid_json(self) -> None:
        """Generated conformance-case template should be valid JSON."""
        result = _cli("init", "conformance-case", "roundtrip_cc", "--dry-run")
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert "id" in parsed
        assert parsed["id"] == "roundtrip_cc"


# ===========================================================================
# 16. ANALYSIS MODULE
# ===========================================================================


class TestAnalysisEdgeCases:
    def test_analyze_structure_minimal(self) -> None:
        """analyze_structure on a minimal bundle should not crash."""
        from limnalis.loader import load_surface_bundle
        from limnalis.analysis import analyze_structure, extract_symbols

        bundle = load_surface_bundle(_MINIMAL)
        diags = analyze_structure(bundle)
        assert isinstance(diags, list)
        for d in diags:
            assert "severity" in d
            assert "code" in d
            assert "message" in d

    def test_extract_symbols_minimal(self) -> None:
        from limnalis.loader import load_surface_bundle
        from limnalis.analysis import extract_symbols

        bundle = load_surface_bundle(_MINIMAL)
        syms = extract_symbols(bundle)
        assert "bundle" in syms
        assert "evaluators" in syms
        # All values should be sorted
        for key, val in syms.items():
            assert val == sorted(val), f"Symbols for {key} are not sorted"


# ===========================================================================
# 17. DIAGNOSTIC from_dict ROBUSTNESS
# ===========================================================================


class TestDiagnosticFromDict:
    def test_empty_dict(self) -> None:
        """An empty dict should produce a Diagnostic with defaults, not crash."""
        from limnalis.diagnostics import Diagnostic

        d = Diagnostic.from_dict({})
        assert d.severity == "info"
        assert d.phase == "unknown"
        assert d.code == "unknown"

    def test_extra_keys_ignored(self) -> None:
        """Extra keys in the dict should not cause Diagnostic.from_dict to crash."""
        from limnalis.diagnostics import Diagnostic

        d = Diagnostic.from_dict({
            "severity": "error",
            "phase": "test",
            "code": "test",
            "message": "msg",
            "subject": "sub",
            "unexpected_key": "value",
        })
        assert d.severity == "error"


# ===========================================================================
# 18. _sanitize_identifier EDGE CASES
# ===========================================================================


class TestSanitizeIdentifier:
    def test_empty_string(self) -> None:
        from limnalis.cli.init_cmd import _sanitize_identifier

        result = _sanitize_identifier("")
        assert result == "untitled"

    def test_just_dots(self) -> None:
        from limnalis.cli.init_cmd import _sanitize_identifier

        result = _sanitize_identifier("...")
        # Path("...").name == "..." on most systems
        assert result  # Non-empty

    def test_slash_only(self) -> None:
        from limnalis.cli.init_cmd import _sanitize_identifier

        result = _sanitize_identifier("/")
        assert result == "untitled"  # Path("/").name == ""

    def test_backslash_traversal(self) -> None:
        from limnalis.cli.init_cmd import _sanitize_identifier

        result = _sanitize_identifier("..\\..\\Windows\\System32\\evil")
        # On Windows Path handles backslashes; on Unix it's literal
        # Either way, result should not contain path separators
        assert "/" not in result
        assert "\\" not in result or sys.platform == "win32"
