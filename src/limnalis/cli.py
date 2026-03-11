from __future__ import annotations

import argparse
import json
from pathlib import Path

from .loader import load_ast_bundle, load_fixture_corpus
from .parser import LimnalisParser
from .schema import load_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="limnalis", description="Limnalis tooling scaffold")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse Limnalis surface source (raw parse tree only)")
    parse_cmd.add_argument("path", type=Path)

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
        tree = LimnalisParser().parse_file(args.path)
        print(tree.pretty())
        return 0

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
