from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from lark import UnexpectedInput

from .loader import load_ast_bundle, load_fixture_corpus, normalize_surface_file
from .normalizer import NormalizationError
from .schema import SchemaValidationError, load_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="limnalis", description="Limnalis tooling scaffold")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print spec, schema, and package version info and exit",
    )
    sub = parser.add_subparsers(dest="command")

    parse_cmd = sub.add_parser("parse", help="Parse Limnalis surface source (raw parse tree only)")
    parse_cmd.add_argument("path", type=Path)

    normalize_cmd = sub.add_parser(
        "normalize", help="Normalize Limnalis surface source into canonical AST JSON"
    )
    normalize_cmd.add_argument("path", type=Path)

    validate_source_cmd = sub.add_parser(
        "validate-source",
        help="Parse, normalize, and schema-validate Limnalis surface source",
    )
    validate_source_cmd.add_argument("path", type=Path)

    ast_cmd = sub.add_parser("validate-ast", help="Validate a canonical AST JSON/YAML payload")
    ast_cmd.add_argument("path", type=Path)

    fixtures_cmd = sub.add_parser("validate-fixtures", help="Validate the fixture corpus JSON/YAML")
    fixtures_cmd.add_argument("path", type=Path)

    schema_cmd = sub.add_parser("print-schema", help="Print a vendored schema")
    schema_cmd.add_argument("name", choices=["ast", "fixture_corpus", "conformance_result"])

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle --version flag
    if args.version:
        from .interop.types import SCHEMA_VERSION, SPEC_VERSION, get_package_version

        info = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
        }
        print(json.dumps(info, indent=2))
        return 0

    if args.command is None:
        parser.error("a command is required")
        return 2

    if args.command == "parse":
        from .parser import LimnalisParser

        tree = LimnalisParser().parse_file(args.path)
        print(tree.pretty())
        return 0

    if args.command == "normalize":
        return _run_surface_pipeline(args.path, emit_payload=True)

    if args.command == "validate-source":
        return _run_surface_pipeline(args.path, emit_payload=False)

    if args.command == "validate-ast":
        bundle = load_ast_bundle(args.path)
        print(bundle.model_dump_json(indent=2, exclude_none=True))
        return 0

    if args.command == "validate-fixtures":
        corpus = load_fixture_corpus(args.path)
        print(json.dumps({"status": "ok", "version": corpus.get("version")}, indent=2))
        return 0

    if args.command == "print-schema":
        print(json.dumps(load_schema(args.name), indent=2))
        return 0

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

    parser.error("unknown command")
    return 2


# ---------------------------------------------------------------------------
# Export command handlers
# ---------------------------------------------------------------------------


def _cmd_export_ast(args: argparse.Namespace) -> int:
    from .interop import export_ast

    try:
        output = export_ast(args.path, output_format=args.format)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(output)
    return 0


def _cmd_export_result(args: argparse.Namespace) -> int:
    from .interop import export_result

    try:
        data = _load_data_file(args.path)
        output = export_result(data, output_format=args.format)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
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
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
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
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1
    return 0


def _cmd_package_inspect(args: argparse.Namespace) -> int:
    from .interop import inspect_package

    try:
        metadata = inspect_package(args.path)
        print(json.dumps(metadata.manifest.model_dump(mode="json"), indent=2))
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1
    return 0


def _cmd_package_validate(args: argparse.Namespace) -> int:
    from .interop import validate_package

    try:
        issues = validate_package(args.path)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
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
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# LinkML projection handler
# ---------------------------------------------------------------------------


def _cmd_project_linkml(args: argparse.Namespace) -> int:
    from .interop import project_linkml_schema

    try:
        result = project_linkml_schema(args.target, output_path=args.output)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
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


def _run_surface_pipeline(path: Path, *, emit_payload: bool) -> int:
    try:
        result = normalize_surface_file(path, validate_schema=True)
    except UnexpectedInput as exc:
        print(json.dumps(_surface_error_payload("parse", str(exc)), indent=2))
        return 1
    except NormalizationError as exc:
        print(json.dumps(_surface_error_payload("normalize", str(exc)), indent=2))
        return 1
    except SchemaValidationError as exc:
        print(
            json.dumps(
                _surface_error_payload(
                    "schema",
                    str(exc),
                    violations=[asdict(violation) for violation in exc.violations],
                ),
                indent=2,
            )
        )
        return 1

    assert result.canonical_ast is not None

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


def _surface_error_payload(
    phase: str, message: str, *, violations: list[dict[str, str]] | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "error",
        "phase": phase,
        "message": message,
    }
    if violations:
        payload["violations"] = violations
    return payload
