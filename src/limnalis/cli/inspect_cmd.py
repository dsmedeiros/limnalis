"""Inspect subcommands for structural exploration of .lmn bundles.

Provides ``limnalis inspect {ast,normalized,trace,machine-state,license}``
for exploring parsed/normalized ASTs, evaluation traces, machine state,
and license breakdowns.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lark import UnexpectedInput

from ..loader import normalize_surface_file
from ..normalizer import NormalizationError
from ..schema import SchemaValidationError
from . import _error


# ---------------------------------------------------------------------------
# Shared evaluation helper
# ---------------------------------------------------------------------------


def _run_default_evaluation(path: Path) -> tuple[Any, Any, int]:
    """Normalize *path* and run a default evaluation.

    Returns ``(bundle_node, bundle_result, exit_code)``.  When *exit_code*
    is non-zero the first two values are ``None``.
    """
    from ..runtime.models import EvaluationEnvironment, SessionConfig, StepConfig
    from ..runtime.runner import run_bundle

    try:
        result = normalize_surface_file(path, validate_schema=True)
    except FileNotFoundError:
        _error(f"file not found: {path}")
        return None, None, 1
    except UnexpectedInput as exc:
        _error(f"parse error in {path}", detail=str(exc))
        return None, None, 1
    except NormalizationError as exc:
        _error(f"normalization error in {path}", detail=str(exc))
        return None, None, 1
    except SchemaValidationError as exc:
        _error(
            f"schema validation failed for {path}",
            detail="\n".join(f"  {v.path}: {v.message}" for v in exc.violations),
        )
        return None, None, 1
    except Exception as exc:
        _error(f"failed to load {path}: {type(exc).__name__}: {exc}")
        return None, None, 1

    if result.canonical_ast is None:
        _error("normalization produced no canonical AST")
        return None, None, 1

    bundle = result.canonical_ast

    sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
    env = EvaluationEnvironment()

    try:
        eval_result = run_bundle(bundle, sessions, env)
    except Exception as exc:
        _error(f"evaluation failed: {type(exc).__name__}: {exc}")
        return None, None, 1

    return bundle, eval_result, 0


def _normalize_only(path: Path) -> tuple[Any, int]:
    """Normalize *path* and return ``(bundle_node, exit_code)``.

    When *exit_code* is non-zero the bundle is ``None``.
    """
    try:
        result = normalize_surface_file(path, validate_schema=True)
    except FileNotFoundError:
        _error(f"file not found: {path}")
        return None, 1
    except UnexpectedInput as exc:
        _error(f"parse error in {path}", detail=str(exc))
        return None, 1
    except NormalizationError as exc:
        _error(f"normalization error in {path}", detail=str(exc))
        return None, 1
    except SchemaValidationError as exc:
        _error(
            f"schema validation failed for {path}",
            detail="\n".join(f"  {v.path}: {v.message}" for v in exc.violations),
        )
        return None, 1
    except Exception as exc:
        _error(f"failed to load {path}: {type(exc).__name__}: {exc}")
        return None, 1

    if result.canonical_ast is None:
        _error("normalization produced no canonical AST")
        return None, 1

    return result.canonical_ast, 0


# ---------------------------------------------------------------------------
# inspect ast
# ---------------------------------------------------------------------------


def _inspect_ast(args: argparse.Namespace) -> int:
    """Print a structural summary of the BundleNode."""
    bundle, rc = _normalize_only(args.path)
    if rc != 0:
        return rc

    evaluator_ids = [e.id for e in bundle.evaluators]
    bridge_ids = [b.id for b in bundle.bridges]
    anchor_ids = [a.id for a in bundle.anchors]

    blocks_info = []
    total_claims = 0
    for block in bundle.claimBlocks:
        claim_count = len(block.claims)
        total_claims += claim_count
        blocks_info.append({
            "block_id": block.id,
            "stratum": block.stratum,
            "claim_count": claim_count,
        })

    if getattr(args, "json_output", False):
        payload = {
            "bundle_id": bundle.id,
            "evaluator_count": len(evaluator_ids),
            "evaluator_ids": evaluator_ids,
            "claim_block_count": len(blocks_info),
            "claim_blocks": blocks_info,
            "total_claims": total_claims,
            "bridge_count": len(bridge_ids),
            "bridge_ids": bridge_ids,
            "anchor_count": len(anchor_ids),
            "anchor_ids": anchor_ids,
            "evidence_count": len(bundle.evidence),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Bundle: {bundle.id}")
        print(f"  Evaluators ({len(evaluator_ids)}):")
        for eid in evaluator_ids:
            print(f"    - {eid}")
        print(f"  Claim Blocks ({len(blocks_info)}):")
        for bi in blocks_info:
            print(f"    - {bi['block_id']} [stratum={bi['stratum']}, claims={bi['claim_count']}]")
        print(f"  Total Claims: {total_claims}")
        print(f"  Bridges ({len(bridge_ids)}):")
        for bid in bridge_ids:
            print(f"    - {bid}")
        print(f"  Anchors ({len(anchor_ids)}):")
        for aid in anchor_ids:
            print(f"    - {aid}")
        print(f"  Evidence: {len(bundle.evidence)}")

    return 0


# ---------------------------------------------------------------------------
# inspect normalized
# ---------------------------------------------------------------------------


def _inspect_normalized(args: argparse.Namespace) -> int:
    """Print the full normalized AST JSON."""
    bundle, rc = _normalize_only(args.path)
    if rc != 0:
        return rc

    print(bundle.model_dump_json(indent=2, exclude_none=True))
    return 0


# ---------------------------------------------------------------------------
# inspect trace
# ---------------------------------------------------------------------------


def _inspect_trace(args: argparse.Namespace) -> int:
    """Print the PrimitiveTraceEvent list from evaluation."""
    _, eval_result, rc = _run_default_evaluation(args.path)
    if rc != 0:
        return rc

    # Collect all trace events across sessions and steps
    all_traces: list[dict[str, Any]] = []
    for session in eval_result.session_results:
        for step in session.step_results:
            for event in step.trace:
                all_traces.append(event.model_dump())

    if getattr(args, "json_output", False):
        print(json.dumps(all_traces, indent=2))
    else:
        if not all_traces:
            print("No trace events recorded.")
        for t in all_traces:
            summary = t.get("result_summary", "") or ""
            print(f"Phase {t['phase']}: {t['primitive']} — {summary}")

    return 0


# ---------------------------------------------------------------------------
# inspect machine-state
# ---------------------------------------------------------------------------


def _inspect_machine_state(args: argparse.Namespace) -> int:
    """Print MachineState contents from evaluation."""
    _, eval_result, rc = _run_default_evaluation(args.path)
    if rc != 0:
        return rc

    # Use the machine state from the last step of the first session
    machine = None
    for session in eval_result.session_results:
        for step in session.step_results:
            machine = step.machine_state

    if machine is None:
        _error("no machine state available")
        return 1

    if getattr(args, "json_output", False):
        print(machine.model_dump_json(indent=2, exclude_none=True))
    else:
        # Resolution store
        print("Resolution Store:")
        if machine.resolution_store.results:
            for cid, eval_node in machine.resolution_store.results.items():
                print(f"  {cid}: truth={eval_node.truth}")
        else:
            print("  (empty)")

        # Baseline store
        print("Baseline Store:")
        if machine.baseline_store:
            for bid, bs in machine.baseline_store.items():
                if hasattr(bs, "status"):
                    print(f"  {bid}: status={bs.status}")
                else:
                    print(f"  {bid}: {bs}")
        else:
            print("  (empty)")

        # Adequacy store
        print("Adequacy Store:")
        filtered = {k: v for k, v in machine.adequacy_store.items() if not str(k).startswith("__fixture_")}
        if filtered:
            for key, val in filtered.items():
                print(f"  {key}: {val}")
        else:
            print("  (empty)")

        # Evidence views
        print("Evidence Views:")
        if machine.evidence_views:
            for cid, view in machine.evidence_views.items():
                explicit_count = len(view.explicit_evidence)
                related_count = len(view.related_evidence)
                print(f"  {cid}: explicit={explicit_count}, related={related_count}")
        else:
            print("  (empty)")

        # Transport store
        print("Transport Store:")
        if machine.transport_store:
            for tid, tr in machine.transport_store.items():
                print(f"  {tid}: status={tr.status}")
        else:
            print("  (empty)")

    return 0


# ---------------------------------------------------------------------------
# inspect license
# ---------------------------------------------------------------------------


def _inspect_license(args: argparse.Namespace) -> int:
    """Print per-claim LicenseResult breakdown."""
    _, eval_result, rc = _run_default_evaluation(args.path)
    if rc != 0:
        return rc

    # Collect license results from all steps
    licenses: dict[str, Any] = {}
    for session in eval_result.session_results:
        for step in session.step_results:
            for cid, lic in step.per_claim_licenses.items():
                licenses[cid] = lic

    if getattr(args, "json_output", False):
        payload = {
            cid: lic.model_dump(exclude_none=True)
            for cid, lic in licenses.items()
        }
        print(json.dumps(payload, indent=2))
    else:
        if not licenses:
            print("No license results available.")
        for cid, lic in licenses.items():
            print(f"Claim: {cid}")
            print(f"  Overall: truth={lic.overall.truth}")
            if lic.overall.reason:
                print(f"           reason={lic.overall.reason}")
            if lic.individual:
                print("  Individual Anchors:")
                for entry in lic.individual:
                    print(f"    - {entry.anchor_id} [{entry.task}]: truth={entry.truth}")
            if lic.joint:
                print("  Joint Entries:")
                for entry in lic.joint:
                    anchors_str = ", ".join(entry.anchors)
                    print(f"    - {entry.joint_id} [{anchors_str}]: truth={entry.truth}")

    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``inspect`` subcommand group on *subparsers*."""
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect bundle structure, traces, and evaluation state",
        description=(
            "Structural inspection subcommands for .lmn bundles.\n\n"
            "Example: limnalis inspect ast examples/minimal_bundle.lmn --json"
        ),
    )
    inspect_sub = inspect_parser.add_subparsers(dest="inspect_command", required=True)

    # inspect ast
    ast_cmd = inspect_sub.add_parser(
        "ast",
        help="Print structural summary of a bundle",
        description="Parse+normalize a .lmn file and print a structural summary.",
    )
    ast_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    ast_cmd.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")

    # inspect normalized
    norm_cmd = inspect_sub.add_parser(
        "normalized",
        help="Print full normalized AST JSON",
        description="Parse+normalize a .lmn file and print the canonical AST.",
    )
    norm_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")

    # inspect trace
    trace_cmd = inspect_sub.add_parser(
        "trace",
        help="Print evaluation trace events",
        description="Run evaluation and print PrimitiveTraceEvent list.",
    )
    trace_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    trace_cmd.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")

    # inspect machine-state
    ms_cmd = inspect_sub.add_parser(
        "machine-state",
        help="Print MachineState contents after evaluation",
        description="Run evaluation and print the MachineState.",
    )
    ms_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    ms_cmd.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")

    # inspect license
    lic_cmd = inspect_sub.add_parser(
        "license",
        help="Print per-claim license breakdown",
        description="Run evaluation and print per-claim LicenseResult.",
    )
    lic_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    lic_cmd.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")


def dispatch_inspect(args: argparse.Namespace) -> int:
    """Route parsed inspect args to the appropriate handler."""
    cmd = args.inspect_command
    if cmd == "ast":
        return _inspect_ast(args)
    if cmd == "normalized":
        return _inspect_normalized(args)
    if cmd == "trace":
        return _inspect_trace(args)
    if cmd == "machine-state":
        return _inspect_machine_state(args)
    if cmd == "license":
        return _inspect_license(args)
    _error(f"unknown inspect subcommand: {cmd}")
    return 1
