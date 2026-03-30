"""Load fixture corpus cases and build structured case objects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import SPEC_VERSION
from ..schema import fixtures_dir, load_json_or_yaml


# ---------------------------------------------------------------------------
# Data classes for fixture cases
# ---------------------------------------------------------------------------


@dataclass
class FixtureBinding:
    """A fixture-level evaluator/baseline/bridge/policy binding."""

    id: str
    type: str
    behavior: Any
    used_by: list[str] = field(default_factory=list)


@dataclass
class FixtureCase:
    """A single conformance test case from the corpus."""

    id: str
    track: str
    name: str
    focus: list[str]
    source: str
    environment: dict[str, Any]
    expected: dict[str, Any]
    normalized_ast_expectations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary for listing."""
        return f"{self.id}: {self.name} ({', '.join(self.focus)})"

    def expected_sessions(self) -> list[dict[str, Any]]:
        return self.expected.get("sessions", [])

    def expected_diagnostics(self) -> list[dict[str, Any]]:
        return self.expected.get("diagnostics", [])

    def expected_baseline_states(self) -> dict[str, str]:
        return self.expected.get("baseline_states", {})

    def expected_adequacy_expectations(self) -> dict[str, dict[str, Any]]:
        return self.expected.get("adequacy_expectations", {})


@dataclass
class FixtureCorpus:
    """Parsed fixture corpus with cases and bindings."""

    version: str
    cases: list[FixtureCase]
    bindings: list[FixtureBinding]
    cases_by_id: dict[str, FixtureCase] = field(default_factory=dict)
    bindings_by_id: dict[str, FixtureBinding] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cases_by_id = {c.id: c for c in self.cases}
        self.bindings_by_id = {b.id: b for b in self.bindings}

    def get_case(self, case_id: str) -> FixtureCase | None:
        return self.cases_by_id.get(case_id)

    def case_ids(self) -> list[str]:
        return [c.id for c in self.cases]

    def bindings_for_case(self, case_id: str) -> list[FixtureBinding]:
        return [b for b in self.bindings if case_id in b.used_by]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_DEFAULT_CORPUS_FILENAME = f"limnalis_fixture_corpus_{SPEC_VERSION}.json"


def load_corpus(path: str | Path) -> FixtureCorpus:
    """Load a fixture corpus from a JSON or YAML file."""
    raw = load_json_or_yaml(path)
    return _parse_corpus(raw)


def load_corpus_from_default() -> FixtureCorpus:
    """Load the default fixture corpus from the fixtures directory."""
    path = fixtures_dir() / _DEFAULT_CORPUS_FILENAME
    return load_corpus(path)


def _parse_corpus(raw: dict[str, Any]) -> FixtureCorpus:
    """Parse raw corpus dict into structured objects."""
    version = raw.get("version", "unknown")

    bindings = [
        FixtureBinding(
            id=f["id"],
            type=f["type"],
            behavior=f.get("behavior"),
            used_by=f.get("used_by", []),
        )
        for f in raw.get("fixtures", [])
    ]

    cases = [
        FixtureCase(
            id=c["id"],
            track=c.get("track", ""),
            name=c.get("name", ""),
            focus=c.get("focus", []),
            source=c.get("source", ""),
            environment=c.get("environment", {}),
            expected=c.get("expected", {}),
            normalized_ast_expectations=c.get("normalized_ast_expectations", []),
        )
        for c in raw.get("cases", [])
    ]

    return FixtureCorpus(version=version, cases=cases, bindings=bindings)
