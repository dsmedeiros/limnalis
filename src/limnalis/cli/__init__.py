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
    sub = parser.add_subparsers(dest="command", required=True)

    # Register all existing commands
    from ._existing import register_commands

    register_commands(sub)

    # Wave 2 commands will be registered here:
    # from ._inspect_cmd import register_commands as register_inspect
    # register_inspect(sub)

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

    from ._existing import dispatch

    return dispatch(args, parser)
