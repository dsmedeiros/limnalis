from __future__ import annotations

import json

from limnalis.cli import main


def test_plugins_list_runs(capsys) -> None:
    """'limnalis plugins list' exits 0 and produces table output."""
    code = main(["plugins", "list"])
    captured = capsys.readouterr()

    assert code == 0
    # Should contain the header
    assert "KIND" in captured.out
    assert "PLUGIN ID" in captured.out
    # Should list at least the grid example plugins
    assert "ev_grid::predicate" in captured.out


def test_plugins_list_json(capsys) -> None:
    """'limnalis plugins list --json' outputs valid JSON."""
    code = main(["plugins", "list", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    rows = json.loads(captured.out)
    assert isinstance(rows, list)
    assert len(rows) > 0
    # Each row has expected keys
    for row in rows:
        assert "kind" in row
        assert "plugin_id" in row
        assert "version" in row
        assert "description" in row


def test_plugins_list_kind_filter(capsys) -> None:
    """'limnalis plugins list --kind evaluator_binding' filters correctly."""
    code = main(["plugins", "list", "--kind", "evaluator_binding"])
    captured = capsys.readouterr()

    assert code == 0
    assert "evaluator_binding" in captured.out
    # Should not contain evidence_policy entries
    assert "evidence_policy" not in captured.out


def test_plugins_list_kind_filter_json(capsys) -> None:
    """'limnalis plugins list --kind evaluator_binding --json' returns only matching kind."""
    code = main(["plugins", "list", "--kind", "evaluator_binding", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    rows = json.loads(captured.out)
    assert len(rows) > 0
    for row in rows:
        assert row["kind"] == "evaluator_binding"


def test_plugins_show_found(capsys) -> None:
    """'limnalis plugins show' displays details for a known plugin."""
    code = main(["plugins", "show", "evaluator_binding", "ev_grid::predicate"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Kind:" in captured.out
    assert "Plugin ID:" in captured.out
    assert "ev_grid::predicate" in captured.out


def test_plugins_show_json(capsys) -> None:
    """'limnalis plugins show --json' returns valid JSON."""
    code = main(["plugins", "show", "evaluator_binding", "ev_grid::predicate", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    data = json.loads(captured.out)
    assert data["kind"] == "evaluator_binding"
    assert data["plugin_id"] == "ev_grid::predicate"
    assert "handler" in data


def test_plugins_list_nonexistent_kind_exits_0(capsys) -> None:
    """'limnalis plugins list --kind nonexistent' exits 0 (empty list is valid)."""
    code = main(["plugins", "list", "--kind", "nonexistent"])
    captured = capsys.readouterr()

    assert code == 0


def test_plugins_list_nonexistent_kind_json_returns_empty_array(capsys) -> None:
    """'limnalis plugins list --kind nonexistent --json' returns []."""
    code = main(["plugins", "list", "--kind", "nonexistent", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    rows = json.loads(captured.out)
    assert isinstance(rows, list)
    assert len(rows) == 0


def test_plugins_show_not_found(capsys) -> None:
    """'limnalis plugins show' with unknown plugin exits non-zero with error."""
    code = main(["plugins", "show", "evaluator_binding", "nonexistent"])
    captured = capsys.readouterr()

    assert code == 1
    assert "error:" in captured.err
    assert "plugin not found" in captured.err
