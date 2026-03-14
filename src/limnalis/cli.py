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

    # Conformance subcommands
    conf_cmd = sub.add_parser("conformance", help="Conformance harness commands")
    conf_sub = conf_cmd.add_subparsers(dest="conf_command", required=True)

    conf_list = conf_sub.add_parser("list", help="List all available fixture cases")

    conf_show = conf_sub.add_parser("show", help="Show details for a fixture case")
    conf_show.add_argument("case_id", type=str, help="Case ID (e.g. A1, B2)")

    conf_run = conf_sub.add_parser("run", help="Run conformance cases and report pass/fail")
    conf_run.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Comma-separated list of case IDs to run (default: all)",
    )

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

    if args.command == "conformance":
        return _run_conformance(args)

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


def _run_conformance(args: argparse.Namespace) -> int:
    from .conformance.compare import compare_case
    from .conformance.fixtures import load_corpus_from_default
    from .conformance.runner import run_case

    corpus = load_corpus_from_default()

    if args.conf_command == "list":
        for case in corpus.cases:
            print(case.summary())
        return 0

    if args.conf_command == "show":
        case = corpus.get_case(args.case_id)
        if case is None:
            print(f"Case not found: {args.case_id}")
            print(f"Available cases: {', '.join(corpus.case_ids())}")
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

    if args.conf_command == "run":
        case_ids: list[str] | None = None
        if args.cases:
            case_ids = [c.strip() for c in args.cases.split(",")]
            # Validate case IDs
            unknown = [c for c in case_ids if corpus.get_case(c) is None]
            if unknown:
                print(f"Unknown case(s): {', '.join(unknown)}")
                print(f"Available cases: {', '.join(corpus.case_ids())}")
                return 1

        cases_to_run = (
            [corpus.get_case(cid) for cid in case_ids if corpus.get_case(cid) is not None]
            if case_ids
            else corpus.cases
        )

        total = len(cases_to_run)
        passed = 0
        failed = 0
        errors = 0

        for case in cases_to_run:
            run_result = run_case(case, corpus)
            comparison = compare_case(case, run_result)

            if comparison.passed:
                print(f"  PASS  {case.id}: {case.name}")
                passed += 1
            elif comparison.error:
                print(f"  ERROR {case.id}: {case.name}")
                print(f"        {comparison.error}")
                errors += 1
            else:
                print(f"  FAIL  {case.id}: {case.name}")
                for m in comparison.mismatches:
                    print(f"        {m}")
                failed += 1

        print()
        print(f"Results: {passed} passed, {failed} failed, {errors} errors out of {total} cases")

        return 0 if (failed == 0 and errors == 0) else 1

    return 2
