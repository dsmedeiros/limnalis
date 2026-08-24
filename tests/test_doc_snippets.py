"""Executable-documentation gate: run the marked Python snippets in covered docs.

Milestone 8 checkpoint 1 introduced this test after an audit found the wiring
docs full of snippets that could not execute against the real API (wrong
attributes, wrong signatures, nonexistent paths); checkpoint 2 extended
coverage to the interop/transport docs and added the README CLI-table drift
canary at the bottom of this file. Every fixed snippet is marked for
extraction, so any future drift between the docs and the API fails the suite
instead of silently misleading integrators.

Marker convention
-----------------
A fenced ```python block in a covered doc is extracted when the line
IMMEDIATELY above its opening fence is one of these HTML comments (invisible
in rendered Markdown):

    <!-- doc-snippet: runnable -->     Executed as its own test, in a namespace
                                       seeded with the accumulated `setup`
                                       blocks that appear EARLIER in the same
                                       document.
    <!-- doc-snippet: setup -->        Shared preamble: executed, in document
                                       order, into the namespace handed to
                                       every later marked block of the same
                                       document (used for multi-step tutorials
                                       whose steps build on each other).
    <!-- doc-snippet: illustrative --> Explicitly excluded from execution
                                       (pseudo-code or a deliberate fragment).

Unmarked fenced blocks are never extracted. An unknown marker value, or a
marker not immediately followed by a ```python fence, fails collection so a
typo cannot silently drop a snippet out of the gate.

Execution contract: snippets run with cwd = repository root (they reference
repo-relative paths such as ``examples/minimal_bundle.lmn``) and must not
write files anywhere but a tmp path -- prefer snippets that only read and
print.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The docs covered by this gate: the three wiring docs (M8 checkpoint 1) plus
# the interop/transport docs whose fixed snippets were marked in checkpoint 2.
# Every ``runnable`` snippet in these files is executed; each file must contain
# at least one so the gate cannot be emptied by quietly deleting markers.
COVERED_DOCS = [
    "docs/downstream_usage_examples.md",
    "docs/plugin_sdk_overview.md",
    "docs/cookbook/custom_plugin.md",
    "docs/export_formats.md",
    "docs/downstream_artifact_consumption.md",
    "docs/writing_a_transport_handler.md",
]

_MARKER_RE = re.compile(r"^\s*<!--\s*doc-snippet:\s*([a-z]+)\s*-->\s*$")
_KNOWN_KINDS = {"runnable", "setup", "illustrative"}
_PYTHON_FENCE = "```python"
_FENCE_CLOSE = "```"


@dataclass
class Snippet:
    doc: str  # repo-relative doc path
    index: int  # ordinal among marked blocks in the doc (0-based)
    kind: str  # "runnable" | "setup" | "illustrative"
    code: str
    line: int  # 1-based line number of the opening fence


def _extract_snippets(doc: str) -> list[Snippet]:
    """Parse one doc into its ordered list of marked snippets."""
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    lines = text.splitlines()
    snippets: list[Snippet] = []
    i = 0
    while i < len(lines):
        match = _MARKER_RE.match(lines[i])
        if match is None:
            i += 1
            continue
        kind = match.group(1)
        if kind not in _KNOWN_KINDS:
            raise ValueError(
                f"{doc}:{i + 1}: unknown doc-snippet kind {kind!r} "
                f"(expected one of {sorted(_KNOWN_KINDS)})"
            )
        fence_line = i + 1
        if fence_line >= len(lines) or lines[fence_line].strip() != _PYTHON_FENCE:
            raise ValueError(
                f"{doc}:{i + 1}: doc-snippet marker must be immediately "
                f"followed by a {_PYTHON_FENCE} fence"
            )
        body: list[str] = []
        j = fence_line + 1
        while j < len(lines) and lines[j].strip() != _FENCE_CLOSE:
            body.append(lines[j])
            j += 1
        if j >= len(lines):
            raise ValueError(f"{doc}:{fence_line + 1}: unterminated fenced block")
        snippets.append(
            Snippet(
                doc=doc,
                index=len(snippets),
                kind=kind,
                code="\n".join(body) + "\n",
                line=fence_line + 1,
            )
        )
        i = j + 1
    return snippets


def _all_snippets() -> dict[str, list[Snippet]]:
    return {doc: _extract_snippets(doc) for doc in COVERED_DOCS}


_SNIPPETS_BY_DOC = _all_snippets()

_RUNNABLE_PARAMS = [
    pytest.param(snippet, id=f"{snippet.doc.removeprefix('docs/')}#{snippet.index}-L{snippet.line}")
    for snippets in _SNIPPETS_BY_DOC.values()
    for snippet in snippets
    if snippet.kind == "runnable"
]


def _exec_snippet(snippet: Snippet, namespace: dict) -> None:
    code = compile(snippet.code, f"<doc-snippet {snippet.doc}:L{snippet.line}>", "exec")
    exec(code, namespace)  # noqa: S102 -- executing our own documentation is the point


@pytest.fixture()
def repo_root_cwd(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Snippets reference repo-relative paths; run them from the repo root."""
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT


@pytest.mark.parametrize("snippet", _RUNNABLE_PARAMS)
def test_doc_snippet_executes(snippet: Snippet, repo_root_cwd: Path) -> None:
    """Each runnable snippet must execute against the current public API."""
    namespace: dict = {"__name__": f"doc_snippet_{snippet.index}"}
    for earlier in _SNIPPETS_BY_DOC[snippet.doc]:
        if earlier.kind == "setup" and earlier.index < snippet.index:
            _exec_snippet(earlier, namespace)
    _exec_snippet(snippet, namespace)


def test_every_covered_doc_has_runnable_snippets() -> None:
    """The gate stays armed: deleting all markers from a wiring doc is a failure,
    not a silent exemption."""
    for doc, snippets in _SNIPPETS_BY_DOC.items():
        runnable = [s for s in snippets if s.kind == "runnable"]
        assert runnable, f"{doc} has no '<!-- doc-snippet: runnable -->' blocks"


def test_negative_control_old_broken_attribute_raises(repo_root_cwd: Path) -> None:
    """Prove the gate discriminates: the pre-M7 audited defect (`result.bundle`)
    must genuinely fail against the current API. The real field is
    `NormalizationResult.canonical_ast`; if `bundle` ever silently starts
    working, the snippet fixes (and this gate's premise) need re-review."""
    from limnalis.api.normalizer import normalize_surface_file

    result = normalize_surface_file("examples/minimal_bundle.lmn")
    assert result.canonical_ast is not None
    with pytest.raises(AttributeError):
        _ = result.bundle  # noqa: B018 -- attribute access is the assertion


# ---------------------------------------------------------------------------
# CLI drift canary (M8 checkpoint 2, PRD item 11)
# ---------------------------------------------------------------------------


def _iter_subparser_actions(parser):  # type: ignore[no-untyped-def]
    import argparse

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            yield action


def _cli_command_exists(parser, tokens: list[str]) -> bool:  # type: ignore[no-untyped-def]
    """True if the (possibly multi-token, e.g. 'conformance run') command path
    exists in the argparse subparser tree."""
    current = parser
    for token in tokens:
        found = None
        for action in _iter_subparser_actions(current):
            if token in action.choices:
                found = action.choices[token]
                break
        if found is None:
            return False
        current = found
    return True


def test_readme_cli_table_lists_only_real_commands() -> None:
    """Drift canary: every command named in README's '## CLI Commands' table
    must exist in ``build_parser()``. Subset semantics, not equality -- the
    README table may stay curated, but a command that does not exist is the
    bug class this canary catches."""
    from limnalis.cli import build_parser

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## CLI Commands\n(.*?)(?=^## )", readme, re.M | re.S)
    assert match, "README.md no longer has a '## CLI Commands' section"
    section = match.group(1)

    rows = re.findall(r"^\|\s*`([a-z][a-z0-9 _-]*)`\s*\|", section, re.M)
    assert rows, "No command rows found in README's CLI Commands table"

    parser = build_parser()
    unknown = [cmd for cmd in rows if not _cli_command_exists(parser, cmd.split())]
    assert not unknown, f"README CLI table names nonexistent commands: {unknown}"


# ---------------------------------------------------------------------------
# Documentation index canaries (M8 checkpoint 3, PRD item 12)
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def test_docs_index_references_every_doc() -> None:
    """Every markdown file under docs/ must be reachable from docs/README.md.

    New docs must be added to the index; orphaned documentation was an audited
    defect class (16 orphans at the M8 recount). Matching is by the file's
    path relative to docs/, so a listing anywhere in the index counts."""
    index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    missing = []
    for doc in sorted((REPO_ROOT / "docs").rglob("*.md")):
        rel = doc.relative_to(REPO_ROOT / "docs").as_posix()
        if rel == "README.md":
            continue
        if rel not in index:
            missing.append(rel)
    assert not missing, f"docs/README.md does not reference: {missing}"


def test_doc_index_relative_links_resolve() -> None:
    """Every relative link in the navigation docs must point at a real file or
    directory: docs/README.md, the root README.md, spec/README.md, and the
    spec errata."""
    nav_files = [
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "README.md",
        REPO_ROOT / "spec" / "README.md",
        REPO_ROOT / "spec" / "Limnalis-v0.2.2-errata.md",
    ]
    broken = []
    for nav in nav_files:
        text = nav.read_text(encoding="utf-8")
        for target in _LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue  # pure in-page anchor
            resolved = (nav.parent / path).resolve()
            if not resolved.exists():
                broken.append(f"{nav.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, f"Broken relative links: {broken}"
