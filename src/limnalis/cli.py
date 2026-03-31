from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lark import UnexpectedInput

from .version import PACKAGE_VERSION, get_version_info
from .loader import load_ast_bundle, load_fixture_corpus, normalize_surface_file
from .normalizer import NormalizationError
from .schema import SchemaValidationError, load_json_or_yaml, load_schema


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

    sub.add_parser(
        "version",
        help="Print version info as JSON",
        description="Print package, spec, schema, and corpus version metadata as JSON.",
    )

    parse_cmd = sub.add_parser(
        "parse",
        help="Parse a .lmn file and print the raw parse tree",
        description=(
            "Parse Limnalis surface source into a raw Lark parse tree.\n\n"
            "Example: limnalis parse examples/minimal_bundle.lmn"
        ),
    )
    parse_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    parse_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output parse tree as JSON instead of pretty-printed text",
    )

    normalize_cmd = sub.add_parser(
        "normalize",
        help="Normalize a .lmn file into canonical AST JSON",
        description=(
            "Parse and normalize Limnalis surface source into canonical AST JSON.\n\n"
            "Example: limnalis normalize examples/minimal_bundle.lmn"
        ),
    )
    normalize_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    normalize_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output as machine-parseable JSON (default behavior; accepted for explicitness)",
    )

    validate_source_cmd = sub.add_parser(
        "validate-source",
        help="Parse, normalize, and schema-validate a .lmn file",
        description=(
            "Full validation pipeline: parse, normalize, and schema-validate surface source.\n\n"
            "Example: limnalis validate-source examples/minimal_bundle.lmn"
        ),
    )
    validate_source_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    validate_source_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output as machine-parseable JSON (default behavior; accepted for explicitness)",
    )

    ast_cmd = sub.add_parser(
        "validate-ast",
        help="Validate a canonical AST JSON/YAML payload against the schema",
        description=(
            "Load and validate a canonical AST JSON or YAML file against the vendored schema.\n\n"
            "Example: limnalis validate-ast examples/minimal_bundle_ast.json"
        ),
    )
    ast_cmd.add_argument("path", type=Path, help="Path to a canonical AST JSON or YAML file")
    ast_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output a compact machine-readable status JSON instead of the full bundle payload",
    )

    fixtures_cmd = sub.add_parser(
        "validate-fixtures",
        help="Validate a fixture corpus JSON/YAML file",
        description=(
            "Load and validate a fixture corpus file against the vendored schema.\n\n"
            "Example: limnalis validate-fixtures fixtures/limnalis_fixture_corpus_v0.2.2.json"
        ),
    )
    fixtures_cmd.add_argument("path", type=Path, help="Path to a fixture corpus JSON or YAML file")
    fixtures_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output as machine-parseable JSON (default behavior; accepted for explicitness)",
    )

    eval_cmd = sub.add_parser(
        "evaluate",
        help="Run the full evaluation pipeline and output JSON result",
        description=(
            "Parse, normalize, and evaluate a Limnalis bundle, producing a JSON evaluation result.\n\n"
            "Example: limnalis evaluate examples/minimal_bundle.lmn\n"
            "         limnalis evaluate --normalized examples/minimal_bundle_ast.json"
        ),
    )
    eval_cmd.add_argument("path", type=Path, help="Path to a .lmn file or normalized AST JSON/YAML")
    eval_cmd.add_argument(
        "--normalized",
        action="store_true",
        default=False,
        help="Treat input as normalized AST JSON/YAML instead of surface source",
    )
    eval_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output as machine-parseable JSON (default behavior; accepted for explicitness)",
    )

    schema_cmd = sub.add_parser(
        "print-schema",
        help="Print a vendored JSON Schema",
        description=(
            "Print one of the vendored Limnalis JSON Schemas to stdout.\n\n"
            "Example: limnalis print-schema ast"
        ),
    )
    schema_cmd.add_argument(
        "name",
        choices=["ast", "fixture_corpus", "conformance_result"],
        help="Schema to print: ast, fixture_corpus, or conformance_result",
    )

    # Conformance subcommands
    conf_cmd = sub.add_parser(
        "conformance",
        help="Conformance harness commands",
        description="Run, inspect, and report on conformance fixture cases.",
    )
    conf_sub = conf_cmd.add_subparsers(dest="conf_command", required=True)

    conf_sub.add_parser(
        "list",
        help="List all available fixture cases",
        description="List all fixture cases from the default conformance corpus.",
    )

    conf_show = conf_sub.add_parser(
        "show",
        help="Show details for a fixture case",
        description=(
            "Show detailed information about a specific fixture case.\n\n"
            "Example: limnalis conformance show A1"
        ),
    )
    conf_show.add_argument("case_id", type=str, help="Case ID (e.g. A1, B2)")

    conf_run = conf_sub.add_parser(
        "run",
        help="Run conformance cases and report pass/fail",
        description=(
            "Execute conformance cases and print pass/fail results.\n\n"
            "Example: limnalis conformance run\n"
            "         limnalis conformance run --cases A1,A2\n"
            "         limnalis conformance run --strict"
        ),
    )
    conf_run.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Comma-separated list of case IDs to run (default: all)",
    )
    conf_run.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Run all cases (default behavior, accepted for explicitness)",
    )
    conf_run.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail (exit 1) if ANY case fails, even if covered by allowlist",
    )
    conf_run.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Path to a JSON/YAML file listing known deviation case IDs with reasons",
    )

    conf_report = conf_sub.add_parser(
        "report",
        help="Generate a conformance report",
        description=(
            "Generate a full conformance report in JSON or Markdown format.\n\n"
            "Example: limnalis conformance report --format json\n"
            "         limnalis conformance report --format markdown"
        ),
    )
    conf_report.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    conf_report.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail (exit 1) if ANY case fails, even if covered by allowlist",
    )
    conf_report.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Path to a JSON/YAML file listing known deviation case IDs with reasons",
    )

    # Plugins subcommands
    plugins_parser = sub.add_parser(
        "plugins",
        help="Manage and inspect plugins",
        description="List and inspect registered plugins.",
    )
    plugins_sub = plugins_parser.add_subparsers(dest="plugins_command", required=True)

    plugins_list_cmd = plugins_sub.add_parser(
        "list",
        help="List registered plugins",
        description="List all registered plugins from available plugin packs.",
    )
    plugins_list_cmd.add_argument("--kind", help="Filter by plugin kind")
    plugins_list_cmd.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    plugins_show_cmd = plugins_sub.add_parser(
        "show",
        help="Show details for a specific plugin",
        description="Show detailed information about a specific registered plugin.",
    )
    plugins_show_cmd.add_argument("kind", help="Plugin kind")
    plugins_show_cmd.add_argument("plugin_id", help="Plugin ID")
    plugins_show_cmd.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # --- Export commands ---
    export_ast_cmd = sub.add_parser(
        "export-ast",
        help="Parse/normalize a .lmn file and export as an AST envelope",
    )
    export_ast_cmd.add_argument("path", type=Path, help="Path to .lmn source file")
    export_ast_cmd.add_argument(
        "--format", choices=["json", "yaml"], default="json", help="Output format (default: json)"
    )

    export_result_cmd = sub.add_parser(
        "export-result",
        help="Wrap a JSON/YAML result file in a ResultEnvelope",
    )
    export_result_cmd.add_argument("path", type=Path, help="Path to result JSON/YAML file")
    export_result_cmd.add_argument(
        "--format", choices=["json", "yaml"], default="json", help="Output format (default: json)"
    )

    export_conformance_cmd = sub.add_parser(
        "export-conformance",
        help="Wrap a JSON/YAML conformance report in a ConformanceEnvelope",
    )
    export_conformance_cmd.add_argument(
        "path", type=Path, help="Path to conformance report JSON/YAML file"
    )
    export_conformance_cmd.add_argument(
        "--format", choices=["json", "yaml"], default="json", help="Output format (default: json)"
    )
    export_conformance_cmd.add_argument(
        "--corpus-version", default=None, help="Corpus version to embed in envelope"
    )

    # --- Package commands ---
    package_create_cmd = sub.add_parser(
        "package-create",
        help="Create an exchange package from artifact files",
    )
    package_create_cmd.add_argument("output", type=Path, help="Output path for the package")
    package_create_cmd.add_argument(
        "--source", nargs="*", default=[], help="Source .lmn files to include"
    )
    package_create_cmd.add_argument(
        "--ast", nargs="*", default=[], help="AST JSON/YAML files to include"
    )
    package_create_cmd.add_argument(
        "--result", nargs="*", default=[], help="Result JSON/YAML files to include"
    )
    package_create_cmd.add_argument(
        "--conformance", nargs="*", default=[], help="Conformance report files to include"
    )
    package_create_cmd.add_argument(
        "--format",
        choices=["directory", "zip"],
        default="directory",
        help="Package format (default: directory)",
    )

    package_inspect_cmd = sub.add_parser(
        "package-inspect",
        help="Inspect an exchange package and print its manifest",
    )
    package_inspect_cmd.add_argument("path", type=Path, help="Path to package directory or zip")

    package_validate_cmd = sub.add_parser(
        "package-validate",
        help="Validate an exchange package for integrity",
    )
    package_validate_cmd.add_argument("path", type=Path, help="Path to package directory or zip")

    package_extract_cmd = sub.add_parser(
        "package-extract",
        help="Extract an exchange package to a directory",
    )
    package_extract_cmd.add_argument("path", type=Path, help="Path to package directory or zip")
    package_extract_cmd.add_argument("output_dir", type=Path, help="Output directory")

    # --- LinkML projection command ---
    project_linkml_cmd = sub.add_parser(
        "project-linkml",
        help="Project Limnalis Pydantic models to LinkML schema",
    )
    project_linkml_cmd.add_argument(
        "--target",
        choices=["ast", "evaluation_result", "conformance_report"],
        default="ast",
        help="Source model to project (default: ast)",
    )
    project_linkml_cmd.add_argument(
        "--output", type=Path, default=None, help="Output file path (prints to stdout if omitted)"
    )

    # --- Summary commands ---
    summarize_cmd = sub.add_parser(
        "summarize",
        help="Run a summary policy on an evaluated bundle",
        description=(
            "Parse, normalize, evaluate a .lmn bundle, then run a summary policy.\n\n"
            "Example: limnalis summarize examples/minimal_bundle.lmn\n"
            "         limnalis summarize examples/minimal_bundle.lmn --policy severity_max"
        ),
    )
    summarize_cmd.add_argument("path", type=Path, help="Path to a .lmn surface source file")
    summarize_cmd.add_argument(
        "--policy",
        type=str,
        default="passthrough_normative",
        help="Summary policy ID (default: passthrough_normative)",
    )
    summarize_cmd.add_argument(
        "--scope",
        type=str,
        default="bundle",
        choices=["claim_collection", "block", "bundle", "session"],
        help="Summary scope (default: bundle)",
    )
    summarize_cmd.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output as machine-parseable JSON (default behavior; accepted for explicitness)",
    )

    sub.add_parser(
        "list-summary-policies",
        help="List available built-in summary policies",
        description="List the IDs of all built-in summary policies.",
    )

    return parser


# ---------------------------------------------------------------------------
# Allowlist loading
# ---------------------------------------------------------------------------


def _load_allowlist(path: Path | None) -> dict[str, str]:
    """Load a deviation allowlist from a JSON/YAML file.

    Returns a dict mapping case_id -> reason.
    Raises on file/parse errors so command handlers can return exit codes.
    """
    if path is None:
        return {}
    raw = load_json_or_yaml(path)

    if isinstance(raw, dict):
        # Accept both {case_id: reason} and {"deviations": [{id, reason}]}
        deviations = raw.get("deviations")
        if isinstance(deviations, list):
            return {
                entry["id"]: entry.get("reason", "")
                for entry in deviations
                if isinstance(entry, dict) and "id" in entry
            }
        return {k: str(v) for k, v in raw.items()}
    elif isinstance(raw, list):
        # List of dicts with "id" keys
        if raw and isinstance(raw[0], dict):
            return {
                entry["id"]: entry.get("reason", "")
                for entry in raw
                if isinstance(entry, dict) and "id" in entry
            }
        # Plain list of strings — treat each as a case ID
        if raw and isinstance(raw[0], str):
            return {str(entry): "listed in allowlist" for entry in raw if isinstance(entry, str)}
        # Empty list is fine
        if not raw:
            return {}

    print(f"warning: unrecognized allowlist format in {path}", file=sys.stderr)
    return {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(json.dumps(get_version_info(), indent=2))
        return 0

    if args.command == "parse":
        return _cmd_parse(args)

    if args.command == "normalize":
        return _run_surface_pipeline(args.path, emit_payload=True, json_output=getattr(args, "json_output", False))

    if args.command == "validate-source":
        return _run_surface_pipeline(args.path, emit_payload=False, json_output=getattr(args, "json_output", False))

    if args.command == "validate-ast":
        return _cmd_validate_ast(args)

    if args.command == "validate-fixtures":
        return _cmd_validate_fixtures(args)

    if args.command == "evaluate":
        return _run_evaluate(args)

    if args.command == "print-schema":
        return _cmd_print_schema(args)

    if args.command == "conformance":
        return _run_conformance(args)

    if args.command == "plugins":
        return _run_plugins(args)

    # --- Export commands ---
    if args.command == "export-ast":
        return _cmd_export_ast(args)

    if args.command == "export-result":
        return _cmd_export_result(args)

    if args.command == "export-conformance":
        return _cmd_export_conformance(args)

    # --- Package commands ---
    if args.command == "package-create":
        return _cmd_package_create(args)

    if args.command == "package-inspect":
        return _cmd_package_inspect(args)

    if args.command == "package-validate":
        return _cmd_package_validate(args)

    if args.command == "package-extract":
        return _cmd_package_extract(args)

    # --- LinkML projection ---
    if args.command == "project-linkml":
        return _cmd_project_linkml(args)

    # --- Summary commands ---
    if args.command == "summarize":
        return _cmd_summarize(args)

    if args.command == "list-summary-policies":
        return _cmd_list_summary_policies()

    parser.error("unknown command")


# ---------------------------------------------------------------------------
# Command: parse
# ---------------------------------------------------------------------------


def _cmd_parse(args: argparse.Namespace) -> int:
    """Parse a .lmn file and print the raw parse tree."""
    from .parser import LimnalisParser

    try:
        tree = LimnalisParser().parse_file(args.path)
    except FileNotFoundError:
        _error(f"file not found: {args.path}")
        return 1
    except UnexpectedInput as exc:
        _error(f"parse error in {args.path}", detail=str(exc))
        return 1
    except Exception as exc:
        _error(f"unexpected error parsing {args.path}: {type(exc).__name__}: {exc}")
        return 1

    if getattr(args, "json_output", False):
        # Serialize the tree to a JSON-compatible structure
        def _tree_to_dict(node):  # type: ignore[no-untyped-def]
            if hasattr(node, "data"):
                return {
                    "type": str(node.data),
                    "children": [_tree_to_dict(c) for c in node.children],
                }
            return str(node)

        print(json.dumps(_tree_to_dict(tree), indent=2))
    else:
        print(tree.pretty())
    return 0


# ---------------------------------------------------------------------------
# Command: validate-ast
# ---------------------------------------------------------------------------


def _cmd_validate_ast(args: argparse.Namespace) -> int:
    """Validate a canonical AST JSON/YAML payload."""
    try:
        bundle = load_ast_bundle(args.path)
    except FileNotFoundError:
        _error(f"file not found: {args.path}")
        return 1
    except Exception as exc:
        if isinstance(exc, json.JSONDecodeError):
            _error(f"invalid JSON in {args.path}", detail=str(exc))
        elif isinstance(exc, SchemaValidationError):
            _error(
                f"schema validation failed for {args.path}",
                detail="\n".join(
                    f"  {v.path}: {v.message}" for v in exc.violations
                ),
            )
        else:
            _error(f"failed to load {args.path}: {type(exc).__name__}: {exc}")
        return 1

    if getattr(args, "json_output", False):
        print(json.dumps({"status": "ok", "bundle": bundle.id}, indent=2))
    else:
        print(bundle.model_dump_json(indent=2, exclude_none=True))
    return 0


# ---------------------------------------------------------------------------
# Command: validate-fixtures
# ---------------------------------------------------------------------------


def _cmd_validate_fixtures(args: argparse.Namespace) -> int:
    """Validate a fixture corpus JSON/YAML file."""
    try:
        corpus = load_fixture_corpus(args.path)
    except FileNotFoundError:
        _error(f"file not found: {args.path}")
        return 1
    except Exception as exc:
        if isinstance(exc, json.JSONDecodeError):
            _error(f"invalid JSON in {args.path}", detail=str(exc))
        elif isinstance(exc, SchemaValidationError):
            _error(
                f"schema validation failed for {args.path}",
                detail="\n".join(
                    f"  {v.path}: {v.message}" for v in exc.violations
                ),
            )
        else:
            _error(f"failed to load {args.path}: {type(exc).__name__}: {exc}")
        return 1

    print(json.dumps({"status": "ok", "version": corpus.get("version")}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Command: print-schema
# ---------------------------------------------------------------------------


def _cmd_print_schema(args: argparse.Namespace) -> int:
    """Print a vendored schema."""
    try:
        print(json.dumps(load_schema(args.name), indent=2))
    except FileNotFoundError:
        _error(f"schema not found: {args.name}")
        return 1
    except Exception as exc:
        _error(f"failed to load schema {args.name}: {type(exc).__name__}: {exc}")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Pipeline: normalize / validate-source
# ---------------------------------------------------------------------------


def _run_surface_pipeline(path: Path, *, emit_payload: bool, json_output: bool = False) -> int:
    def _emit_error(message: str, *, detail: str | None = None) -> int:
        if json_output:
            payload: dict[str, str] = {"status": "error", "error": message}
            if detail:
                payload["detail"] = detail
            print(json.dumps(payload, indent=2))
        else:
            _error(message, detail=detail)
        return 1

    try:
        result = normalize_surface_file(path, validate_schema=True)
    except FileNotFoundError:
        return _emit_error(f"file not found: {path}")
    except UnexpectedInput as exc:
        return _emit_error(f"parse error in {path}", detail=str(exc))
    except NormalizationError as exc:
        return _emit_error(f"normalization error in {path}", detail=str(exc))
    except SchemaValidationError as exc:
        return _emit_error(
            f"schema validation failed for {path}",
            detail="\n".join(
                f"  {v.path}: {v.message}" for v in exc.violations
            ),
        )
    except Exception as exc:
        return _emit_error(f"unexpected error processing {path}: {type(exc).__name__}: {exc}")

    if result.canonical_ast is None:
        return _emit_error("normalization produced no canonical AST")

    if emit_payload:
        print(json.dumps(result.canonical_ast.to_schema_data(), indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "bundle": result.canonical_ast.id,
                    "diagnostics": result.diagnostics,
                },
                indent=2,
            )
        )
    return 0


# ---------------------------------------------------------------------------
# Command: evaluate
# ---------------------------------------------------------------------------


def _run_evaluate(args: argparse.Namespace) -> int:
    """Run the evaluate pipeline: parse -> normalize -> evaluate -> JSON output."""
    from .runtime.models import EvaluationEnvironment, SessionConfig, StepConfig
    from .runtime.runner import run_bundle

    json_output = getattr(args, "json_output", False)

    def _emit_error(message: str, *, detail: str | None = None) -> int:
        if json_output:
            payload: dict[str, str] = {"status": "error", "error": message}
            if detail:
                payload["detail"] = detail
            print(json.dumps(payload, indent=2))
        else:
            _error(message, detail=detail)
        return 1

    try:
        if args.normalized:
            bundle = load_ast_bundle(args.path)
        else:
            result = normalize_surface_file(args.path, validate_schema=True)
            if result.canonical_ast is None:
                return _emit_error("normalization produced no canonical AST")
            bundle = result.canonical_ast
    except FileNotFoundError:
        return _emit_error(f"file not found: {args.path}")
    except UnexpectedInput as exc:
        return _emit_error(f"parse error in {args.path}", detail=str(exc))
    except NormalizationError as exc:
        return _emit_error(f"normalization error in {args.path}", detail=str(exc))
    except SchemaValidationError as exc:
        return _emit_error(
            f"schema validation failed for {args.path}",
            detail="\n".join(
                f"  {v.path}: {v.message}" for v in exc.violations
            ),
        )
    except json.JSONDecodeError as exc:
        return _emit_error(f"invalid JSON in {args.path}", detail=str(exc))
    except Exception as exc:
        return _emit_error(f"failed to load {args.path}: {type(exc).__name__}: {exc}")

    # Run evaluation with a single default session
    sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
    env = EvaluationEnvironment()

    try:
        eval_result = run_bundle(bundle, sessions, env)
    except Exception as exc:
        return _emit_error(f"evaluation failed: {type(exc).__name__}: {exc}")

    print(eval_result.model_dump_json(indent=2, exclude_none=True))
    return 0


# ---------------------------------------------------------------------------
# Command: conformance
# ---------------------------------------------------------------------------


def _run_conformance(args: argparse.Namespace) -> int:
    from .conformance.compare import compare_case
    from .conformance.fixtures import load_corpus_from_default
    from .conformance.runner import run_case

    try:
        corpus = load_corpus_from_default()
    except FileNotFoundError as exc:
        _error("conformance fixture corpus not found", detail=str(exc))
        return 1
    except Exception as exc:
        _error(f"failed to load conformance corpus: {type(exc).__name__}: {exc}")
        return 1

    if args.conf_command == "list":
        for case in corpus.cases:
            print(case.summary())
        return 0

    if args.conf_command == "show":
        case = corpus.get_case(args.case_id)
        if case is None:
            _error(
                f"case not found: {args.case_id}",
                detail=f"Available cases: {', '.join(corpus.case_ids())}",
            )
            return 1
        print(f"Case: {case.id}")
        print(f"Name: {case.name}")
        print(f"Track: {case.track}")
        print(f"Focus: {', '.join(case.focus)}")
        print()
        print("Expected sessions:")
        for si, sess in enumerate(case.expected_sessions()):
            sess_id = sess.get("id", f"session_{si}")
            steps = sess.get("steps", [])
            print(f"  Session {sess_id}: {len(steps)} step(s)")
            for step in steps:
                step_id = step.get("id", "?")
                claims = step.get("claims", {})
                blocks = step.get("blocks", {})
                transports = step.get("transports", {})
                print(
                    f"    Step {step_id}: "
                    f"{len(claims)} claim(s), "
                    f"{len(blocks)} block(s), "
                    f"{len(transports)} transport(s)"
                )
        diags = case.expected_diagnostics()
        if diags:
            print(f"\nExpected diagnostics: {len(diags)}")
            for d in diags:
                parts = [d.get("severity", "?"), d.get("code", "?")]
                subj = d.get("subject")
                if subj:
                    parts.append(f"subject={subj}")
                print(f"  {' / '.join(parts)}")
        baseline_states = case.expected_baseline_states()
        if baseline_states:
            print(f"\nExpected baseline states:")
            for bl_id, status in baseline_states.items():
                print(f"  {bl_id}: {status}")
        adequacy = case.expected_adequacy_expectations()
        if adequacy:
            print(f"\nExpected adequacy:")
            for adeq_id, vals in adequacy.items():
                print(f"  {adeq_id}: {vals}")
        return 0

    if args.conf_command == "report":
        return _run_conformance_report(args, corpus)

    if args.conf_command == "run":
        return _run_conformance_run(args, corpus)

    raise AssertionError(f"unreachable: unknown conformance subcommand {args.conf_command!r}")


# ---------------------------------------------------------------------------
# Conformance: run
# ---------------------------------------------------------------------------


def _run_conformance_run(args: argparse.Namespace, corpus: object) -> int:
    """Run conformance cases and report pass/fail."""
    from .conformance.compare import compare_case
    from .conformance.runner import run_case, validate_result_schema

    strict = getattr(args, "strict", False)
    allowlist_path = getattr(args, "allowlist", None)
    try:
        allowlist = _load_allowlist(allowlist_path)
    except FileNotFoundError:
        _error(f"allowlist file not found: {allowlist_path}")
        return 1
    except Exception as exc:
        _error(f"failed to parse allowlist: {allowlist_path}", detail=str(exc))
        return 1

    case_ids: list[str] | None = None
    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(",")]
        unknown = [c for c in case_ids if corpus.get_case(c) is None]
        if unknown:
            _error(
                f"unknown case(s): {', '.join(unknown)}",
                detail=f"Available cases: {', '.join(corpus.case_ids())}",
            )
            return 1

    if case_ids:
        cases_to_run = [corpus.get_case(cid) for cid in case_ids]
    else:
        cases_to_run = corpus.cases

    total = len(cases_to_run)
    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    for case in cases_to_run:
        try:
            run_result = run_case(case, corpus)
            comparison = compare_case(case, run_result)
            schema_violations = validate_result_schema(run_result)
        except Exception as exc:
            print(f"  ERROR {case.id}: {case.name}", file=sys.stderr)
            print(f"        crash: {type(exc).__name__}: {exc}", file=sys.stderr)
            errors += 1
            continue

        if comparison.error:
            print(f"  ERROR {case.id}: {case.name}", file=sys.stderr)
            print(f"        {comparison.error}", file=sys.stderr)
            errors += 1
        elif comparison.passed and not schema_violations:
            print(f"  PASS  {case.id}: {case.name}")
            passed += 1
        elif case.id in allowlist:
            reason = allowlist[case.id]
            print(f"  KNOWN {case.id}: {case.name} (deviation: {reason})")
            skipped += 1
        else:
            print(f"  FAIL  {case.id}: {case.name}")
            for m in comparison.mismatches:
                print(f"        {m}")
            if schema_violations:
                print(f"        Schema violations:")
                for v in schema_violations:
                    print(f"          {v['path']}: {v['message']}")
            failed += 1

    print()
    summary_parts = [
        f"{passed} passed",
        f"{failed} failed",
    ]
    if skipped:
        summary_parts.append(f"{skipped} known deviations")
    summary_parts.append(f"{errors} errors out of {total} cases")
    print(f"Results: {', '.join(summary_parts)}")

    if strict:
        return 0 if (failed == 0 and errors == 0 and skipped == 0) else 1
    return 0 if (failed == 0 and errors == 0) else 1


# ---------------------------------------------------------------------------
# Conformance: report
# ---------------------------------------------------------------------------


def _run_conformance_report(args: argparse.Namespace, corpus: object) -> int:
    """Generate a conformance report in JSON or Markdown format."""
    from .conformance.compare import compare_case
    from .conformance.runner import run_case, validate_result_schema

    strict = getattr(args, "strict", False)
    allowlist_path = getattr(args, "allowlist", None)
    try:
        allowlist = _load_allowlist(allowlist_path)
    except FileNotFoundError:
        _error(f"allowlist file not found: {allowlist_path}")
        return 1
    except Exception as exc:
        _error(f"failed to parse allowlist: {allowlist_path}", detail=str(exc))
        return 1
    version_info = get_version_info()

    case_results: list[dict[str, object]] = []
    total = len(corpus.cases)
    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    for case in corpus.cases:
        try:
            run_result = run_case(case, corpus)
            comparison = compare_case(case, run_result)
            schema_violations = validate_result_schema(run_result)
        except Exception as exc:
            errors += 1
            case_results.append({
                "case_id": case.id,
                "name": case.name,
                "status": "error",
                "mismatches": [],
                "diagnostics_count": 0,
                "error": f"crash: {type(exc).__name__}: {exc}",
            })
            continue

        if comparison.error:
            status = "error"
            errors += 1
        elif comparison.passed and not schema_violations:
            status = "pass"
            passed += 1
        elif case.id in allowlist:
            status = "known_deviation"
            skipped += 1
        else:
            status = "fail"
            failed += 1

        # Count actual diagnostics from the runner output
        actual_diag_count = 0
        if run_result.bundle_result is not None:
            br = run_result.bundle_result
            actual_diag_count += len(br.diagnostics)
            for sess in br.session_results:
                actual_diag_count += len(sess.diagnostics)
                for step in sess.step_results:
                    actual_diag_count += len(step.diagnostics)

        case_entry: dict[str, object] = {
            "case_id": case.id,
            "name": case.name,
            "status": status,
            "mismatches": [str(m) for m in comparison.mismatches],
            "diagnostics_count": actual_diag_count,
        }
        if schema_violations:
            case_entry["schema_violations"] = schema_violations
        if comparison.error:
            case_entry["error"] = comparison.error
        if status == "known_deviation":
            case_entry["deviation_reason"] = allowlist.get(case.id, "")

        case_results.append(case_entry)

    if args.format == "json":
        legacy_failed = failed + skipped
        report = {
            "version": version_info,
            # Backward-compatible top-level counters.
            "total": total,
            "passed": passed,
            "failed": legacy_failed,
            "errors": errors,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "errors": errors,
            },
            "cases": case_results,
        }
        print(json.dumps(report, indent=2))
    elif args.format == "markdown":
        print(f"# Conformance Report")
        print()
        print(f"**Implementation:** limnalis {version_info['package']}")
        print(f"**Spec:** {version_info['spec']} | **Schema:** {version_info['schema']} | **Corpus:** {version_info['corpus']}")
        print()
        print(f"## Summary")
        print()
        print(f"| Metric | Count |")
        print(f"|--------|-------|")
        print(f"| Total  | {total} |")
        print(f"| Passed | {passed} |")
        print(f"| Failed | {failed} |")
        if skipped:
            print(f"| Known Deviations | {skipped} |")
        print(f"| Errors | {errors} |")
        print()
        print(f"## Results")
        print()
        print("| Case | Name | Status | Mismatches | Diagnostics |")
        print("|------|------|--------|------------|-------------|")
        for entry in case_results:
            mismatch_count = len(entry["mismatches"])
            print(
                f"| {entry['case_id']} | {entry['name']} | {entry['status']} "
                f"| {mismatch_count} | {entry['diagnostics_count']} |"
            )

        # Show failures detail
        has_failures = any(e["status"] == "fail" for e in case_results)
        if has_failures:
            print()
            print("## Failures")
            print()
            for entry in case_results:
                if entry["status"] != "fail":
                    continue
                print(f"### {entry['case_id']}: {entry['name']}")
                for m in entry["mismatches"]:
                    print(f"- {m}")
                violations = entry.get("schema_violations", [])
                if violations:
                    print()
                    print("**Schema Violations:**")
                    for v in violations:
                        print(f"- `{v['path']}`: {v['message']}")
                print()

        # Show known deviations
        has_deviations = any(e["status"] == "known_deviation" for e in case_results)
        if has_deviations:
            print()
            print("## Known Deviations")
            print()
            print("| Case | Name | Reason |")
            print("|------|------|--------|")
            for entry in case_results:
                if entry["status"] != "known_deviation":
                    continue
                reason = entry.get("deviation_reason", "")
                print(f"| {entry['case_id']} | {entry['name']} | {reason} |")

        # Show schema violations
        has_schema_issues = any("schema_violations" in e for e in case_results if e["status"] != "fail")
        if has_schema_issues:
            print()
            print("## Schema Violations")
            print()
            for entry in case_results:
                if entry["status"] == "fail":
                    continue  # already shown above
                violations = entry.get("schema_violations", [])
                if violations:
                    print(f"### {entry['case_id']}: {entry['name']}")
                    for v in violations:
                        print(f"- `{v['path']}`: {v['message']}")

    if strict:
        return 0 if (failed == 0 and errors == 0 and skipped == 0) else 1
    return 0 if (failed == 0 and errors == 0) else 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_data_file(path: Path) -> dict:
    """Load a JSON or YAML file and return its contents as a dict."""
    import yaml

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        result = yaml.safe_load(text)
    else:
        result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON/YAML object, got {type(result).__name__}")
    return result


# ---------------------------------------------------------------------------
# Export command handlers
# ---------------------------------------------------------------------------


def _cmd_export_ast(args: argparse.Namespace) -> int:
    from .interop import export_ast

    try:
        output = export_ast(args.path, output_format=args.format)
    except Exception as exc:
        _error(f"export-ast failed: {exc}")
        return 1
    print(output)
    return 0


def _cmd_export_result(args: argparse.Namespace) -> int:
    from .interop import export_result

    try:
        data = _load_data_file(args.path)
        output = export_result(data, output_format=args.format)
    except Exception as exc:
        _error(f"export-result failed: {exc}")
        return 1
    print(output)
    return 0


def _cmd_export_conformance(args: argparse.Namespace) -> int:
    from .interop import export_conformance

    try:
        data = _load_data_file(args.path)
        output = export_conformance(
            data, output_format=args.format, corpus_version=args.corpus_version
        )
    except Exception as exc:
        _error(f"export-conformance failed: {exc}")
        return 1
    print(output)
    return 0


# ---------------------------------------------------------------------------
# Package command handlers
# ---------------------------------------------------------------------------


def _cmd_package_create(args: argparse.Namespace) -> int:
    from .interop import create_package

    try:
        metadata = create_package(
            args.output,
            source_files=args.source or None,
            ast_files=args.ast or None,
            result_files=args.result or None,
            conformance_files=args.conformance or None,
            output_format=args.format,
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "root_path": metadata.root_path,
                    "artifact_types": metadata.manifest.artifact_types,
                },
                indent=2,
            )
        )
    except (ValueError, OSError, RuntimeError) as exc:
        _error(f"package-create failed: {exc}")
        return 1
    return 0


def _cmd_package_inspect(args: argparse.Namespace) -> int:
    from .interop import inspect_package

    try:
        metadata = inspect_package(args.path)
        print(json.dumps(metadata.manifest.model_dump(mode="json"), indent=2))
    except (ValueError, OSError, RuntimeError) as exc:
        _error(f"package-inspect failed: {exc}")
        return 1
    return 0


def _cmd_package_validate(args: argparse.Namespace) -> int:
    from .interop import validate_package

    try:
        issues = validate_package(args.path)
    except (ValueError, OSError, RuntimeError) as exc:
        _error(f"package-validate failed: {exc}")
        return 1

    if issues:
        print(json.dumps({"status": "invalid", "issues": issues}, indent=2))
        return 1
    print(json.dumps({"status": "ok"}, indent=2))
    return 0


def _cmd_package_extract(args: argparse.Namespace) -> int:
    from .interop import extract_package

    try:
        result_path = extract_package(args.path, args.output_dir)
        print(json.dumps({"status": "ok", "output_dir": str(result_path)}, indent=2))
    except (ValueError, OSError, RuntimeError) as exc:
        _error(f"package-extract failed: {exc}")
        return 1
    return 0


# ---------------------------------------------------------------------------
# LinkML projection handler
# ---------------------------------------------------------------------------


def _cmd_project_linkml(args: argparse.Namespace) -> int:
    from .interop import project_linkml_schema

    try:
        if args.output is None:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_output = Path(tmp_dir) / "projected.linkml.yaml"
                project_linkml_schema(args.target, output_path=tmp_output)
                print(tmp_output.read_text(encoding="utf-8"))
            return 0

        result = project_linkml_schema(args.target, output_path=args.output)
    except (ValueError, OSError, RuntimeError) as exc:
        _error(f"project-linkml failed: {exc}")
        return 1

    summary = {
        "status": "ok",
        "target_format": result.target_format,
        "source_model": result.source_model,
        "artifact_path": result.artifact_path,
        "warnings_count": len(result.warnings),
        "lossy_fields_count": len(result.lossy_fields),
    }
    if result.warnings:
        summary["warnings"] = result.warnings
    if result.lossy_fields:
        summary["lossy_fields"] = result.lossy_fields
    print(json.dumps(summary, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Command: plugins
# ---------------------------------------------------------------------------


def _build_demo_registry():
    """Build a registry with available example plugin packs."""
    from limnalis.plugins import PluginRegistry

    registry = PluginRegistry()

    # Try importing each known plugin pack
    try:
        from limnalis.plugins.grid_example import register_grid_plugins

        register_grid_plugins(registry)
    except ImportError:
        pass

    try:
        from limnalis.plugins.jwt_example import register_jwt_plugins

        register_jwt_plugins(registry)
    except ImportError:
        pass

    return registry


def _run_plugins(args: argparse.Namespace) -> int:
    """Dispatch plugins subcommands."""
    if args.plugins_command == "list":
        return _cmd_plugins_list(args)
    if args.plugins_command == "show":
        return _cmd_plugins_show(args)
    raise AssertionError(f"unreachable: unknown plugins subcommand {args.plugins_command!r}")


def _cmd_plugins_list(args: argparse.Namespace) -> int:
    """List registered plugins."""
    registry = _build_demo_registry()
    kind_filter = getattr(args, "kind", None)
    json_output = getattr(args, "json_output", False)

    plugins = registry.list_plugins(kind=kind_filter)

    if json_output:
        rows = [
            {
                "kind": m.kind,
                "plugin_id": m.plugin_id,
                "version": m.version,
                "description": m.description,
            }
            for m in plugins
        ]
        print(json.dumps(rows, indent=2))
    else:
        # Table output
        header = f"{'KIND':<20s}{'PLUGIN ID':<35s}{'VERSION':<10s}DESCRIPTION"
        print(header)
        for m in plugins:
            print(f"{m.kind:<20s}{m.plugin_id:<35s}{m.version:<10s}{m.description}")

    return 0


def _cmd_plugins_show(args: argparse.Namespace) -> int:
    """Show details for a specific plugin."""
    registry = _build_demo_registry()
    kind = args.kind
    plugin_id = args.plugin_id
    json_output = getattr(args, "json_output", False)

    if not registry.has(kind, plugin_id):
        _error(f"plugin not found: kind={kind!r}, id={plugin_id!r}")
        return 1

    meta = registry.get_metadata(kind, plugin_id)

    if json_output:
        print(
            json.dumps(
                {
                    "kind": meta.kind,
                    "plugin_id": meta.plugin_id,
                    "version": meta.version,
                    "description": meta.description,
                    "handler": repr(meta.handler),
                },
                indent=2,
            )
        )
    else:
        print(f"Kind:        {meta.kind}")
        print(f"Plugin ID:   {meta.plugin_id}")
        print(f"Version:     {meta.version}")
        print(f"Description: {meta.description}")
        print(f"Handler:     {meta.handler!r}")

    return 0


# ---------------------------------------------------------------------------
# Command: summarize
# ---------------------------------------------------------------------------


def _cmd_summarize(args: argparse.Namespace) -> int:
    """Parse, normalize, evaluate, then run a summary policy."""
    from .runtime.models import EvaluationEnvironment, SessionConfig, StepConfig
    from .runtime.runner import run_bundle
    from .runtime import get_builtin_summary_policies, execute_summary
    from .models.conformance import SummaryRequest

    json_output = getattr(args, "json_output", False)

    def _emit_error(message: str, *, detail: str | None = None) -> int:
        if json_output:
            payload: dict[str, str] = {"status": "error", "error": message}
            if detail:
                payload["detail"] = detail
            print(json.dumps(payload, indent=2))
        else:
            _error(message, detail=detail)
        return 1

    # --- Load and evaluate the bundle ---
    try:
        result = normalize_surface_file(args.path, validate_schema=True)
        if result.canonical_ast is None:
            return _emit_error("normalization produced no canonical AST")
        bundle = result.canonical_ast
    except FileNotFoundError:
        return _emit_error(f"file not found: {args.path}")
    except UnexpectedInput as exc:
        return _emit_error(f"parse error in {args.path}", detail=str(exc))
    except NormalizationError as exc:
        return _emit_error(f"normalization error in {args.path}", detail=str(exc))
    except SchemaValidationError as exc:
        return _emit_error(
            f"schema validation failed for {args.path}",
            detail="\n".join(
                f"  {v.path}: {v.message}" for v in exc.violations
            ),
        )
    except Exception as exc:
        return _emit_error(f"failed to load {args.path}: {type(exc).__name__}: {exc}")

    sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
    env = EvaluationEnvironment()

    try:
        eval_result = run_bundle(bundle, sessions, env)
    except Exception as exc:
        return _emit_error(f"evaluation failed: {type(exc).__name__}: {exc}")

    # --- Run the summary policy ---
    policies = get_builtin_summary_policies()
    policy_id = args.policy
    if policy_id not in policies:
        available = ", ".join(sorted(policies.keys()))
        return _emit_error(
            f"unknown summary policy: {policy_id!r}",
            detail=f"available policies: {available}",
        )

    request = SummaryRequest(
        policy_id=policy_id,
        scope=args.scope,
    )

    try:
        eval_dict = eval_result.model_dump() if hasattr(eval_result, "model_dump") else eval_result
        summary_result = execute_summary(request, eval_dict, {}, policies)
    except Exception as exc:
        return _emit_error(f"summary execution failed: {type(exc).__name__}: {exc}")

    print(summary_result.model_dump_json(indent=2, exclude_none=True))
    return 0


# ---------------------------------------------------------------------------
# Command: list-summary-policies
# ---------------------------------------------------------------------------


def _cmd_list_summary_policies() -> int:
    """List available built-in summary policies."""
    from .runtime import get_builtin_summary_policies

    policies = get_builtin_summary_policies()
    for policy_id in sorted(policies.keys()):
        print(policy_id)
    return 0
