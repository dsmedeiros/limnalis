"""Lint, analyze, symbols, and explain CLI commands.

Public API:
    register_commands(subparsers)  — add lint/analyze/symbols/explain subcommands
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lark import UnexpectedInput

from ..analysis import analyze_structure, extract_symbols
from ..diagnostic_fmt import REMEDIATION_HINTS, format_diagnostics
from ..diagnostics import Diagnostic
from ..loader import normalize_surface_file
from ..normalizer import NormalizationError
from ..schema import SchemaValidationError, validate_payload
from . import _error


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _lint_file(path: Path) -> tuple[Any, list[dict]]:
    """Parse, normalize, and schema-validate a surface file.

    Returns ``(bundle_or_none, diagnostics_list)``.
    """
    diagnostics: list[dict] = []

    try:
        result = normalize_surface_file(path, validate_schema=False)
    except (UnexpectedInput, NormalizationError) as exc:
        diagnostics.append({
            "severity": "error",
            "phase": "parse",
            "code": "parse_error",
            "subject": str(path),
            "message": str(exc),
        })
        return None, diagnostics

    diagnostics.extend(result.diagnostics)

    if result.canonical_ast is not None:
        try:
            validate_payload(result.canonical_ast.to_schema_data(), "ast")
        except SchemaValidationError as exc:
            diagnostics.append({
                "severity": "error",
                "phase": "schema",
                "code": "schema_validation_error",
                "subject": str(path),
                "message": str(exc),
            })

    return result.canonical_ast, diagnostics


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_lint(args: argparse.Namespace) -> int:
    """Handler for ``limnalis lint``."""
    _bundle, diagnostics = _lint_file(args.path)

    typed = [Diagnostic.from_dict(d) if isinstance(d, dict) else d for d in diagnostics]

    use_color = not getattr(args, "no_color", False)
    if typed:
        output = format_diagnostics(typed, mode=args.format, color=use_color)
        print(output)

    has_errors = any(d.severity == "error" for d in typed)
    return 1 if has_errors else 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Handler for ``limnalis analyze``."""
    bundle, diagnostics = _lint_file(args.path)

    if bundle is not None:
        structural = analyze_structure(bundle)
        diagnostics.extend(structural)

    typed = [Diagnostic.from_dict(d) if isinstance(d, dict) else d for d in diagnostics]

    use_color = not getattr(args, "no_color", False)
    if typed:
        output = format_diagnostics(typed, mode=args.format, color=use_color)
        print(output)

    has_errors = any(d.severity == "error" for d in typed)
    return 1 if has_errors else 0


def _cmd_symbols(args: argparse.Namespace) -> int:
    """Handler for ``limnalis symbols``."""
    bundle, diagnostics = _lint_file(args.path)

    if bundle is None:
        typed = [Diagnostic.from_dict(d) if isinstance(d, dict) else d for d in diagnostics]
        if typed:
            use_color = not getattr(args, "no_color", False)
            output = format_diagnostics(typed, mode="plain", color=use_color)
            print(output, file=sys.stderr)
        return 1

    symbols = extract_symbols(bundle)

    if args.json_output:
        print(json.dumps(symbols, indent=2, sort_keys=True))
    else:
        for group_name in [
            "bundle",
            "evaluators",
            "claim_blocks",
            "claims",
            "bridges",
            "anchors",
            "evidence",
            "baselines",
        ]:
            ids = symbols.get(group_name, [])
            if ids:
                print(f"{group_name}:")
                for sym_id in ids:
                    print(f"  {sym_id}")

    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    """Handler for ``limnalis explain``."""
    code = args.code
    hint = REMEDIATION_HINTS.get(code)
    if hint is None:
        print(f"No hint available for code: {code}")
    else:
        print(f"{code}: {hint}")
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_commands(sub: argparse._SubParsersAction) -> None:
    """Register lint, analyze, symbols, and explain subcommands."""

    # lint
    lint_cmd = sub.add_parser(
        "lint",
        help="Lint a .lmn file (parse + normalize + schema-validate)",
        description=(
            "Parse, normalize, and schema-validate a .lmn surface file.\n"
            "Collect and format all diagnostics.\n\n"
            "Example: limnalis lint examples/minimal_bundle.lmn"
        ),
    )
    lint_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    lint_cmd.add_argument(
        "--format",
        choices=["plain", "json", "grouped"],
        default="grouped",
        help="Output format (default: grouped)",
    )

    # analyze
    analyze_cmd = sub.add_parser(
        "analyze",
        help="Lint + structural analysis of a .lmn file",
        description=(
            "Run lint checks plus structural analysis on a .lmn surface file.\n\n"
            "Example: limnalis analyze examples/minimal_bundle.lmn"
        ),
    )
    analyze_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    analyze_cmd.add_argument(
        "--format",
        choices=["plain", "json", "grouped"],
        default="grouped",
        help="Output format (default: grouped)",
    )

    # symbols
    symbols_cmd = sub.add_parser(
        "symbols",
        help="Extract and list all named symbols from a .lmn file",
        description=(
            "Parse, normalize, and extract all named IDs grouped by type.\n\n"
            "Example: limnalis symbols examples/minimal_bundle.lmn"
        ),
    )
    symbols_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    symbols_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output as machine-readable JSON",
    )

    # explain
    explain_cmd = sub.add_parser(
        "explain",
        help="Look up a diagnostic code and show its remediation hint",
        description=(
            "Print the remediation hint for a diagnostic code.\n\n"
            "Example: limnalis explain stubbed_primitive"
        ),
    )
    explain_cmd.add_argument("code", help="The diagnostic code to explain")
