"""Limnalis CLI package.

Public API:
    main(argv)      — CLI entry point (returns exit code)
    build_parser()  — construct the argparse.ArgumentParser
"""
from __future__ import annotations

import argparse
import json
import sys

from ..version import PACKAGE_VERSION, get_version_info


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _error(message: str, *, detail: str | None = None) -> None:
    """Print an error message to stderr."""
    print(f"error: {message}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="limnalis",
        description="Limnalis surface-syntax toolchain: parse, normalize, validate, and evaluate .lmn files.",
    )
    parser.add_argument(
        "--version", action="version", version=f"limnalis {PACKAGE_VERSION}"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable ANSI color output",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Register all existing commands
    from ._existing import register_commands

    register_commands(sub)

    # Inspect subcommands
    from .inspect_cmd import register_commands as register_inspect

    register_inspect(sub)

    # Lint / analyze / symbols / explain subcommands
    from .lint_cmd import register_commands as register_lint

    register_lint(sub)

    # Init subcommands
    from .init_cmd import register_commands as register_init

    register_init(sub)

    # Visualize subcommands
    from .visualize_cmd import register_commands as register_visualize

    register_visualize(sub)

    # Doctor subcommand
    from .doctor_cmd import register_commands as register_doctor

    register_doctor(sub)

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(json.dumps(get_version_info(), indent=2))
        return 0

    if args.command == "inspect":
        from .inspect_cmd import dispatch_inspect

        return dispatch_inspect(args)

    _LINT_COMMANDS = {"lint", "analyze", "symbols", "explain"}
    if args.command in _LINT_COMMANDS:
        from .lint_cmd import _cmd_analyze, _cmd_explain, _cmd_lint, _cmd_symbols

        _lint_dispatch = {
            "lint": _cmd_lint,
            "analyze": _cmd_analyze,
            "symbols": _cmd_symbols,
            "explain": _cmd_explain,
        }
        return _lint_dispatch[args.command](args)

    if args.command == "init":
        return args.func(args)

    if args.command == "visualize":
        from .visualize_cmd import dispatch_visualize

        return dispatch_visualize(args)

    if args.command == "doctor":
        return args.func(args)

    from ._existing import dispatch

    return dispatch(args, parser)
