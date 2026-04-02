"""``limnalis init`` subcommands for generating authoring scaffolds.

Supports:
    limnalis init bundle <name>
    limnalis init plugin-pack <name>
    limnalis init conformance-case <case-id>

Options:
    --output-dir DIR    Target directory (default: cwd)
    --dry-run           Print to stdout instead of writing a file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..templates import bundle_template, conformance_case_template, plugin_pack_template


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

_GENERATORS: dict[str, dict[str, object]] = {
    "bundle": {
        "fn": bundle_template,
        "ext": ".lmn",
        "meta_var": "name",
    },
    "plugin-pack": {
        "fn": plugin_pack_template,
        "ext": ".py",
        "meta_var": "name",
    },
    "conformance-case": {
        "fn": conformance_case_template,
        "ext": ".json",
        "meta_var": "case_id",
    },
}


def _run_init(args: argparse.Namespace) -> int:
    kind: str = args.init_kind
    identifier: str = args.identifier
    gen = _GENERATORS[kind]
    content: str = gen["fn"](identifier)  # type: ignore[operator]

    if args.dry_run:
        sys.stdout.write(content)
        return 0

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = identifier + gen["ext"]  # type: ignore[operator]
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    print(str(out_path))
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register ``limnalis init`` on *subparsers*."""
    init_parser = subparsers.add_parser(
        "init",
        help="Generate authoring scaffolds (bundles, plugin packs, conformance cases)",
        description="Generate authoring scaffolds for Limnalis development.",
    )
    init_parser.add_argument(
        "init_kind",
        choices=list(_GENERATORS),
        metavar="KIND",
        help="Template kind: bundle, plugin-pack, or conformance-case",
    )
    init_parser.add_argument(
        "identifier",
        metavar="IDENTIFIER",
        help="Name or case-id for the generated scaffold",
    )
    init_parser.add_argument(
        "--output-dir",
        default=".",
        help="Target directory (default: current directory)",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print to stdout instead of writing a file",
    )
    init_parser.set_defaults(func=_run_init)
