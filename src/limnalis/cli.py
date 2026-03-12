from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from lark import UnexpectedInput

from .loader import load_ast_bundle, load_fixture_corpus, normalize_surface_file
from .normalizer import NormalizationError
from .schema import SchemaValidationError, load_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="limnalis", description="Limnalis tooling scaffold")
    sub = parser.add_subparsers(dest="command", required=True)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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

    parser.error("unknown command")
    return 2


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
