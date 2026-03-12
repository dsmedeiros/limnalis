from __future__ import annotations

from pathlib import Path

from limnalis.loader import load_surface_bundle, normalize_surface_file

ROOT = Path(__file__).resolve().parents[1]


def test_normalize_surface_file_returns_validated_bundle_and_diagnostics() -> None:
    result = normalize_surface_file(ROOT / "examples" / "minimal_bundle.lmn")

    assert result.canonical_ast is not None
    assert result.canonical_ast.id == "minimal_bundle"
    assert [diagnostic["code"] for diagnostic in result.diagnostics] == [
        "resolution_policy_defaulted"
    ]


def test_load_surface_bundle_returns_canonical_bundle_model() -> None:
    bundle = load_surface_bundle(ROOT / "examples" / "minimal_bundle.lmn")

    assert bundle.id == "minimal_bundle"
    assert bundle.resolutionPolicy.id == "rp0"
    assert bundle.claimBlocks[0].id == "local#1"
