"""Tests for template generation and ``limnalis init`` CLI commands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from limnalis.cli import main
from limnalis.templates import (
    bundle_template,
    conformance_case_template,
    plugin_pack_template,
)


# ---------------------------------------------------------------------------
# Template content tests
# ---------------------------------------------------------------------------


def test_bundle_template_name_substitution() -> None:
    result = bundle_template("myproject")
    assert "bundle myproject {" in result
    assert "myproject:default::standard" in result
    assert "myproject://eval/default" in result


def test_bundle_template_roundtrip() -> None:
    """Generated bundle must parse and normalize without error."""
    from limnalis.loader import normalize_surface_text

    content = bundle_template("test")
    result = normalize_surface_text(content)
    ast = result.canonical_ast
    assert ast is not None
    assert ast.id == "test"
    assert ast.frame.node == "FramePattern"


def test_plugin_pack_template_compiles() -> None:
    source = plugin_pack_template("test")
    code = compile(source, "<template>", "exec")
    assert code is not None


def test_plugin_pack_template_name_substitution() -> None:
    source = plugin_pack_template("myplug")
    assert "def myplug_handler(" in source
    assert "def register_myplug_plugins(" in source
    assert '"myplug://eval/default"' in source


def test_conformance_case_template_valid_json() -> None:
    raw = conformance_case_template("T1")
    data = json.loads(raw)
    assert data["id"] == "T1"
    assert data["name"] == "T1 test case"
    assert "sessions" in data["expected"]
    assert len(data["expected"]["sessions"]) == 1


# ---------------------------------------------------------------------------
# CLI dry-run tests
# ---------------------------------------------------------------------------


def test_cli_init_bundle_dry_run(capsys) -> None:
    code = main(["init", "bundle", "scaffold_test", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "bundle scaffold_test {" in out


def test_cli_init_plugin_pack_dry_run(capsys) -> None:
    code = main(["init", "plugin-pack", "myplugin", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "def myplugin_handler(" in out


def test_cli_init_conformance_case_dry_run(capsys) -> None:
    code = main(["init", "conformance-case", "C1", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["id"] == "C1"


# ---------------------------------------------------------------------------
# CLI file-write tests
# ---------------------------------------------------------------------------


def test_cli_init_bundle_writes_file(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        code = main(["init", "bundle", "written", "--output-dir", tmpdir])
        assert code == 0
        out_path = Path(tmpdir) / "written.lmn"
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "bundle written {" in content


def test_cli_init_plugin_pack_writes_file(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        code = main(["init", "plugin-pack", "mypkg", "--output-dir", tmpdir])
        assert code == 0
        out_path = Path(tmpdir) / "mypkg.py"
        assert out_path.exists()


def test_cli_init_conformance_case_writes_file(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        code = main(["init", "conformance-case", "X1", "--output-dir", tmpdir])
        assert code == 0
        out_path = Path(tmpdir) / "X1.json"
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["id"] == "X1"
