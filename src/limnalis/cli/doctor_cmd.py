"""``limnalis doctor`` — environment sanity-check command."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CheckResult:
    """Result of a single doctor check."""

    name: str
    status: str  # "PASS", "FAIL", "SKIP"
    detail: str


def _check_python_version() -> CheckResult:
    vi = sys.version_info
    version_str = f"{vi.major}.{vi.minor}.{vi.micro}"
    if vi >= (3, 11):
        return CheckResult("Python version", "PASS", version_str)
    return CheckResult("Python version", "FAIL", f"{version_str} (requires >= 3.11)")


def _check_pydantic_version() -> CheckResult:
    try:
        import pydantic

        return CheckResult("Pydantic version", "PASS", pydantic.VERSION)
    except Exception as exc:
        return CheckResult("Pydantic version", "FAIL", str(exc))


def _check_lark_parser() -> CheckResult:
    try:
        from limnalis.parser import LimnalisParser

        LimnalisParser()
        return CheckResult("Lark parser", "PASS", "grammar loaded")
    except Exception as exc:
        return CheckResult("Lark parser", "FAIL", str(exc))


def _check_json_schemas() -> CheckResult:
    try:
        from limnalis.schema import load_schema

        load_schema("ast")
        return CheckResult("JSON schemas", "PASS", "ast schema loaded")
    except Exception as exc:
        return CheckResult("JSON schemas", "FAIL", str(exc))


def _check_fixture_corpus() -> CheckResult:
    try:
        from limnalis.conformance.fixtures import load_corpus_from_default

        corpus = load_corpus_from_default()
        return CheckResult(
            "Fixture corpus", "PASS", f"{len(corpus.bindings)} bindings"
        )
    except Exception as exc:
        return CheckResult("Fixture corpus", "FAIL", str(exc))


def _check_plugin_registry() -> CheckResult:
    try:
        from limnalis.plugins import PluginRegistry

        PluginRegistry()
        return CheckResult("Plugin registry", "PASS", "initialized")
    except Exception as exc:
        return CheckResult("Plugin registry", "FAIL", str(exc))


def _check_example_files() -> CheckResult:
    try:
        from limnalis.parser import LimnalisParser

        # Walk up from this file to find the project root
        candidate = Path(__file__).resolve()
        example_path: Path | None = None
        for _ in range(10):
            candidate = candidate.parent
            p = candidate / "examples" / "minimal_bundle.lmn"
            if p.exists():
                example_path = p
                break

        if example_path is None:
            return CheckResult(
                "Example files", "SKIP", "examples/minimal_bundle.lmn not found"
            )

        parser = LimnalisParser()
        parser.parse_file(example_path)
        return CheckResult("Example files", "PASS", str(example_path))
    except Exception as exc:
        return CheckResult("Example files", "FAIL", str(exc))


_ALL_CHECKS = [
    _check_python_version,
    _check_pydantic_version,
    _check_lark_parser,
    _check_json_schemas,
    _check_fixture_corpus,
    _check_plugin_registry,
    _check_example_files,
]


def _run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for check_fn in _ALL_CHECKS:
        try:
            results.append(check_fn())
        except Exception as exc:  # pragma: no cover — defensive
            results.append(CheckResult(check_fn.__name__, "FAIL", str(exc)))
    return results


def _format_text(results: list[CheckResult]) -> str:
    lines: list[str] = []
    for r in results:
        lines.append(f"[{r.status}] {r.name}: {r.detail}")
    return "\n".join(lines)


def _format_json(results: list[CheckResult]) -> str:
    return json.dumps([asdict(r) for r in results], indent=2)


def _cmd_doctor(args: argparse.Namespace) -> int:
    results = _run_checks()
    if getattr(args, "json_output", False):
        print(_format_json(results))
    else:
        print(_format_text(results))
    has_fail = any(r.status == "FAIL" for r in results)
    return 1 if has_fail else 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_commands(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    doctor = sub.add_parser(
        "doctor",
        help="Run environment sanity checks",
        description=(
            "Check that the Limnalis toolchain is correctly installed and configured.\n\n"
            "Example: limnalis doctor --json"
        ),
    )
    doctor.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output results as JSON array",
    )
    doctor.set_defaults(func=_cmd_doctor)
