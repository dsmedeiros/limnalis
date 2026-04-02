"""CLI commands for graph visualization of Limnalis bundles.

Subcommands:
    limnalis visualize frame-graph <path>
    limnalis visualize evaluator-graph <path>
    limnalis visualize evidence-graph <path>

Each accepts ``--format mermaid|json`` (default: mermaid).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import _error


def register_commands(sub: argparse._SubParsersAction) -> None:
    """Register the ``visualize`` subcommand group."""
    vis = sub.add_parser(
        "visualize",
        help="Render bundle structure graphs",
        description="Build and render structure graphs from a normalized .lmn bundle.",
    )
    vis_sub = vis.add_subparsers(dest="visualize_command", required=True)

    for name, help_text in [
        ("frame-graph", "Render frame-to-frame bridge graph"),
        ("evaluator-graph", "Render evaluator-to-claim-block graph"),
        ("evidence-graph", "Render evidence relation graph"),
    ]:
        cmd = vis_sub.add_parser(name, help=help_text)
        cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
        cmd.add_argument(
            "--format",
            dest="output_format",
            choices=["mermaid", "json"],
            default="mermaid",
            help="Output format (default: mermaid)",
        )


def dispatch_visualize(args: argparse.Namespace) -> int:
    """Execute the selected visualize subcommand. Returns exit code."""
    from ..graph import (
        build_evidence_graph,
        build_evaluator_graph,
        build_frame_graph,
        graph_to_json,
        render_mermaid,
    )
    from ..loader import load_surface_bundle

    path: Path = args.path
    if not path.exists():
        _error(f"file not found: {path}")
        return 1

    try:
        bundle = load_surface_bundle(path)
    except Exception as exc:
        _error(f"failed to normalize {path}: {exc}")
        return 1

    builders = {
        "frame-graph": ("Frame Graph", build_frame_graph),
        "evaluator-graph": ("Evaluator Graph", build_evaluator_graph),
        "evidence-graph": ("Evidence Graph", build_evidence_graph),
    }

    title, builder = builders[args.visualize_command]
    nodes, edges = builder(bundle)

    if args.output_format == "json":
        print(graph_to_json(nodes, edges))
    else:
        print(render_mermaid(nodes, edges, title=title), end="")

    return 0
