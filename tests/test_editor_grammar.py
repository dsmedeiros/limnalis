"""Tests for Limnalis VS Code extension files (TextMate grammar, snippets, package.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

EDITOR_DIR = Path(__file__).resolve().parent.parent / "editor" / "vscode"
TM_GRAMMAR_PATH = EDITOR_DIR / "syntaxes" / "limnalis.tmLanguage.json"
PACKAGE_JSON_PATH = EDITOR_DIR / "package.json"
SNIPPETS_PATH = EDITOR_DIR / "snippets" / "limnalis.json"
LANG_CONFIG_PATH = EDITOR_DIR / "language-configuration.json"
LARK_GRAMMAR_PATH = Path(__file__).resolve().parent.parent / "grammar" / "limnalis.lark"


# ---------------------------------------------------------------------------
# Helper: extract all keyword-like tokens mentioned in the TextMate grammar
# ---------------------------------------------------------------------------

def _extract_tm_keywords(tm_data: dict) -> set[str]:
    """Walk the TextMate grammar JSON and collect every bare word in match/begin patterns."""
    words: set[str] = set()
    _walk_patterns(tm_data.get("patterns", []), words)
    for _key, repo_entry in tm_data.get("repository", {}).items():
        _walk_patterns(repo_entry.get("patterns", []), words)
    return words


def _walk_patterns(patterns: list, out: set[str]) -> None:
    for pat in patterns:
        for field in ("match", "begin"):
            raw = pat.get(field, "")
            # Extract words from alternation groups like (bundle|frame|...)
            for m in re.finditer(r"\(([^)]+)\)", raw):
                for token in m.group(1).split("|"):
                    cleaned = token.strip()
                    if re.match(r"^[a-zA-Z_]\w*$", cleaned):
                        out.add(cleaned)
        _walk_patterns(pat.get("patterns", []), out)


# ---------------------------------------------------------------------------
# Tests: JSON validity
# ---------------------------------------------------------------------------

class TestJsonValidity:
    """All editor JSON files must be valid JSON."""

    def test_tmgrammar_is_valid_json(self) -> None:
        data = json.loads(TM_GRAMMAR_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "tmLanguage must be a JSON object"

    def test_package_json_is_valid_json(self) -> None:
        data = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "package.json must be a JSON object"

    def test_snippets_is_valid_json(self) -> None:
        data = json.loads(SNIPPETS_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "snippets must be a JSON object"

    def test_language_config_is_valid_json(self) -> None:
        data = json.loads(LANG_CONFIG_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "language-configuration must be a JSON object"


# ---------------------------------------------------------------------------
# Tests: package.json structure
# ---------------------------------------------------------------------------

class TestPackageJson:
    """The VS Code extension manifest must have required fields."""

    @pytest.fixture()
    def pkg(self) -> dict:
        return json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))

    def test_has_name(self, pkg: dict) -> None:
        assert pkg.get("name") == "limnalis-language"

    def test_has_display_name(self, pkg: dict) -> None:
        assert "displayName" in pkg

    def test_has_version(self, pkg: dict) -> None:
        assert "version" in pkg

    def test_has_engines(self, pkg: dict) -> None:
        assert "engines" in pkg
        assert "vscode" in pkg["engines"]

    def test_contributes_languages(self, pkg: dict) -> None:
        languages = pkg.get("contributes", {}).get("languages", [])
        assert len(languages) >= 1
        lang = languages[0]
        assert lang["id"] == "limnalis"
        assert ".lmn" in lang.get("extensions", [])

    def test_contributes_grammars(self, pkg: dict) -> None:
        grammars = pkg.get("contributes", {}).get("grammars", [])
        assert len(grammars) >= 1
        assert grammars[0]["scopeName"] == "source.limnalis"

    def test_contributes_snippets(self, pkg: dict) -> None:
        snippets = pkg.get("contributes", {}).get("snippets", [])
        assert len(snippets) >= 1
        assert snippets[0]["language"] == "limnalis"


# ---------------------------------------------------------------------------
# Tests: TextMate grammar scopes
# ---------------------------------------------------------------------------

class TestTmGrammar:
    """The TextMate grammar must have proper structure and scopes."""

    @pytest.fixture()
    def tm(self) -> dict:
        return json.loads(TM_GRAMMAR_PATH.read_text(encoding="utf-8"))

    def test_scope_name(self, tm: dict) -> None:
        assert tm["scopeName"] == "source.limnalis"

    def test_has_patterns(self, tm: dict) -> None:
        assert "patterns" in tm
        assert len(tm["patterns"]) > 0

    def test_has_repository(self, tm: dict) -> None:
        assert "repository" in tm

    def test_comment_scopes_exist(self, tm: dict) -> None:
        """Hash and double-slash comments must be scoped."""
        repo = tm["repository"]
        comments = repo.get("comments", {})
        patterns = comments.get("patterns", [])
        scope_names = [p.get("name", "") for p in patterns]
        assert "comment.line.hash.limnalis" in scope_names
        assert "comment.line.double-slash.limnalis" in scope_names

    def test_string_scope_exists(self, tm: dict) -> None:
        repo = tm["repository"]
        strings = repo.get("strings", {})
        patterns = strings.get("patterns", [])
        assert any(
            p.get("name") == "string.quoted.double.limnalis" for p in patterns
        )

    def test_keyword_control_scope(self, tm: dict) -> None:
        repo = tm["repository"]
        kc = repo.get("keywords-control", {})
        patterns = kc.get("patterns", [])
        assert any(
            p.get("name") == "keyword.control.limnalis" for p in patterns
        )

    def test_keyword_operator_scope(self, tm: dict) -> None:
        repo = tm["repository"]
        ko = repo.get("keywords-operator", {})
        patterns = ko.get("patterns", [])
        assert any(
            p.get("name") == "keyword.operator.limnalis" for p in patterns
        )

    def test_type_scope(self, tm: dict) -> None:
        repo = tm["repository"]
        tn = repo.get("type-names", {})
        patterns = tn.get("patterns", [])
        assert any(
            p.get("name") == "entity.name.type.limnalis" for p in patterns
        )

    def test_inline_pattern_scope(self, tm: dict) -> None:
        repo = tm["repository"]
        ip = repo.get("inline-patterns", {})
        patterns = ip.get("patterns", [])
        assert any(
            p.get("name") == "constant.other.pattern.limnalis" for p in patterns
        )


# ---------------------------------------------------------------------------
# Tests: Keyword coverage against the Lark grammar
# ---------------------------------------------------------------------------

class TestKeywordCoverage:
    """All control keywords from the task specification must appear in the TextMate grammar."""

    REQUIRED_CONTROL_KEYWORDS = {
        "bundle", "frame", "evaluator", "baseline", "anchor",
        "fictional_anchor", "bridge", "local", "systemic", "meta",
        "evidence", "evidence_relation", "resolution_policy",
        "joint_adequacy", "session", "step", "judged_by", "transport",
        "claims",
    }

    REQUIRED_OPERATORS = {
        "AND", "OR", "IMPLIES", "IFF", "declare", "as", "within",
    }

    REQUIRED_TYPES = {
        "idealization", "placeholder", "proxy", "aggregate",
        "point", "set", "manifold", "moving", "fixed", "on_reference",
        "tracked", "single", "paraconsistent_union", "priority_order",
        "adjudicated", "primary", "adversarial", "audit", "auxiliary",
    }

    @pytest.fixture()
    def tm_keywords(self) -> set[str]:
        tm = json.loads(TM_GRAMMAR_PATH.read_text(encoding="utf-8"))
        return _extract_tm_keywords(tm)

    def test_all_control_keywords_covered(self, tm_keywords: set[str]) -> None:
        missing = self.REQUIRED_CONTROL_KEYWORDS - tm_keywords
        assert not missing, f"Control keywords missing from TextMate grammar: {missing}"

    def test_all_operators_covered(self, tm_keywords: set[str]) -> None:
        missing = self.REQUIRED_OPERATORS - tm_keywords
        assert not missing, f"Operators missing from TextMate grammar: {missing}"

    def test_all_type_names_covered(self, tm_keywords: set[str]) -> None:
        missing = self.REQUIRED_TYPES - tm_keywords
        assert not missing, f"Type names missing from TextMate grammar: {missing}"


# ---------------------------------------------------------------------------
# Tests: Snippets
# ---------------------------------------------------------------------------

class TestSnippets:
    """Snippets must be valid and have expected prefixes."""

    EXPECTED_PREFIXES = {"bundle", "evaluator", "claims-local", "bridge", "anchor", "frame"}

    @pytest.fixture()
    def snippets(self) -> dict:
        return json.loads(SNIPPETS_PATH.read_text(encoding="utf-8"))

    def test_expected_prefixes_present(self, snippets: dict) -> None:
        actual_prefixes = {s.get("prefix") for s in snippets.values()}
        missing = self.EXPECTED_PREFIXES - actual_prefixes
        assert not missing, f"Missing snippet prefixes: {missing}"

    def test_each_snippet_has_body(self, snippets: dict) -> None:
        for name, snippet in snippets.items():
            assert "body" in snippet, f"Snippet '{name}' missing body"
            assert isinstance(snippet["body"], list), f"Snippet '{name}' body must be a list"
            assert len(snippet["body"]) > 0, f"Snippet '{name}' has empty body"

    def test_each_snippet_has_description(self, snippets: dict) -> None:
        for name, snippet in snippets.items():
            assert "description" in snippet, f"Snippet '{name}' missing description"
