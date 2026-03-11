from __future__ import annotations

import copy
import json
from importlib.abc import Traversable
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator

SchemaName = Literal["ast", "fixture_corpus", "conformance_result"]

_SCHEMA_FILES = {
    "ast": "limnalis_ast_schema_v0.2.2.json",
    "fixture_corpus": "limnalis_fixture_corpus_schema_v0.2.2.json",
    "conformance_result": "limnalis_conformance_result_schema_v0.2.2.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def schemas_dir() -> Path:
    return repo_root() / "schemas"


def fixtures_dir() -> Path:
    return repo_root() / "fixtures"


def _resource_candidates(*parts: str) -> list[Traversable | Path]:
    return [
        files("limnalis").joinpath("_data", *parts),
        repo_root().joinpath(*parts),
    ]


def _read_resource_text(*parts: str) -> str:
    candidates = _resource_candidates(*parts)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    attempted = ", ".join(str(candidate) for candidate in candidates)
    joined = "/".join(parts)
    raise FileNotFoundError(f"Unable to locate bundled resource {joined}; looked in {attempted}")


def load_json_or_yaml(path: str | Path) -> Any:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _repair_ast_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Patch the known upstream `$ref` typo without mutating the vendored file."""

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            repaired = {}
            for key, value in node.items():
                if key == "$ref" and value == "#/$defs/FixtureTimeSpec":
                    repaired[key] = "#/$defs/TimeCtxNode"
                else:
                    repaired[key] = walk(value)
            return repaired
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(copy.deepcopy(schema))


def load_schema(name: SchemaName, *, repair_ast_refs: bool = True) -> dict[str, Any]:
    schema = json.loads(_read_resource_text("schemas", _SCHEMA_FILES[name]))
    if name == "ast" and repair_ast_refs:
        schema = _repair_ast_schema_refs(schema)
    return schema


def make_validator(name: SchemaName, *, repair_ast_refs: bool = True) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name, repair_ast_refs=repair_ast_refs))


def validate_payload(
    payload: Any, schema_name: SchemaName, *, repair_ast_refs: bool = True
) -> None:
    validator = make_validator(schema_name, repair_ast_refs=repair_ast_refs)
    validator.validate(payload)
