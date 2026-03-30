from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return completed


def test_wheel_install_loads_packaged_resources(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    target = tmp_path / "target"
    wheelhouse.mkdir()
    target.mkdir()

    env = os.environ.copy()
    env["TMP"] = str(tmp_path)
    env["TEMP"] = str(tmp_path)

    _run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheelhouse)],
        cwd=ROOT,
        env=env,
    )

    wheel = next(wheelhouse.glob("limnalis-*.whl"))
    _run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        cwd=ROOT,
        env=env,
    )

    script = f"""
from pathlib import Path

from limnalis.loader import load_ast_bundle, load_surface_bundle, normalize_surface_file

root = Path({str(ROOT)!r})
bundle = load_ast_bundle(root / \"examples\" / \"minimal_bundle_ast.json\")
assert bundle.id == \"minimal_bundle\"
result = normalize_surface_file(root / \"examples\" / \"minimal_bundle.lmn\")
assert result.canonical_ast is not None
assert result.diagnostics[0][\"code\"] == \"resolution_policy_defaulted\"
surface_bundle = load_surface_bundle(root / \"examples\" / \"minimal_bundle.lmn\")
assert surface_bundle.claimBlocks[0].id == \"local#1\"
"""

    installed_env = env.copy()
    installed_env["PYTHONPATH"] = str(target)

    _run([sys.executable, "-c", script], cwd=tmp_path, env=installed_env)


# ---------------------------------------------------------------------------
# T6.6 – Vendored grammar, schemas, and fixtures are accessible
# ---------------------------------------------------------------------------


def test_vendored_grammar_accessible() -> None:
    """Test that the grammar file is accessible via the resource loading mechanism."""
    from limnalis.schema import _read_resource_text

    grammar = _read_resource_text("grammar", "limnalis.lark")
    assert grammar
    assert "start" in grammar  # grammar must define a start rule


def test_vendored_schemas_accessible() -> None:
    """Test that all three vendored schemas can be loaded."""
    from limnalis.schema import load_schema

    for name in ("ast", "fixture_corpus", "conformance_result"):
        schema = load_schema(name)
        assert isinstance(schema, dict)
        assert "$schema" in schema or "title" in schema or "type" in schema


def test_vendored_fixture_corpus_accessible() -> None:
    """Test that the fixture corpus file is present and loadable."""
    from limnalis.schema import fixtures_dir

    corpus_dir = fixtures_dir()
    json_files = list(corpus_dir.glob("*.json"))
    assert len(json_files) >= 1, "No fixture JSON files found"


# ---------------------------------------------------------------------------
# T6.7 – Console scripts entry point is callable
# ---------------------------------------------------------------------------


def test_cli_main_is_callable() -> None:
    """Test that the CLI main function is importable and callable."""
    from limnalis.cli import main

    assert callable(main)
