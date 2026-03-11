from __future__ import annotations

from pathlib import Path
from typing import Any

from .models.ast import BundleNode
from .schema import load_json_or_yaml, validate_payload


def load_data(path: str | Path) -> Any:
    return load_json_or_yaml(path)


def load_fixture_corpus(path: str | Path) -> dict[str, Any]:
    payload = load_json_or_yaml(path)
    validate_payload(payload, "fixture_corpus")
    return payload


def load_ast_bundle(path: str | Path) -> BundleNode:
    payload = load_json_or_yaml(path)
    validate_payload(payload, "ast")
    return BundleNode.model_validate(payload)
