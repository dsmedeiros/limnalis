"""Tests for the public API surface (limnalis.api.*) and version metadata.

T6: Public API import tests + packaging smoke tests.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# T6.1 – All api submodules import cleanly
# ---------------------------------------------------------------------------


class TestApiSubmoduleImports:
    """Verify that all limnalis.api.* submodules can be imported without error."""

    @pytest.mark.parametrize(
        "submodule",
        ["limnalis.api", "limnalis.api.parser", "limnalis.api.normalizer",
         "limnalis.api.evaluator", "limnalis.api.conformance"],
    )
    def test_submodule_imports_cleanly(self, submodule: str) -> None:
        mod = importlib.import_module(submodule)
        assert mod is not None


# ---------------------------------------------------------------------------
# T6.2 – __all__ is complete and matches actual exports
# ---------------------------------------------------------------------------


class TestApiAllExports:
    """Verify that each __all__ in api submodules is complete."""

    @pytest.mark.parametrize(
        "submodule",
        ["limnalis.api", "limnalis.api.parser", "limnalis.api.normalizer",
         "limnalis.api.evaluator", "limnalis.api.conformance"],
    )
    def test_all_matches_actual_exports(self, submodule: str) -> None:
        mod = importlib.import_module(submodule)
        assert hasattr(mod, "__all__"), f"{submodule} has no __all__"
        declared = set(mod.__all__)

        # Every name in __all__ must be resolvable
        for name in declared:
            assert hasattr(mod, name), f"{submodule}.__all__ declares {name!r} but it is not importable"

    @pytest.mark.parametrize(
        "submodule,expected_names",
        [
            ("limnalis.api.parser", ["LimnalisParser"]),
            ("limnalis.api.normalizer", [
                "NormalizationError", "NormalizationResult", "Normalizer",
                "normalize_surface_file", "normalize_surface_text",
            ]),
            ("limnalis.api.evaluator", [
                "BundleResult", "EvaluationResult", "PrimitiveSet",
                "SessionResult", "StepResult", "run_bundle", "run_session", "run_step",
            ]),
            ("limnalis.api.conformance", [
                "FixtureCase", "compare_case", "load_corpus",
                "load_corpus_from_default", "run_case",
            ]),
        ],
    )
    def test_all_contains_expected_names(
        self, submodule: str, expected_names: list[str]
    ) -> None:
        mod = importlib.import_module(submodule)
        declared = set(mod.__all__)
        for name in expected_names:
            assert name in declared, f"{name!r} missing from {submodule}.__all__"


# ---------------------------------------------------------------------------
# T6.3 – Minimal end-to-end usage via public API only
# ---------------------------------------------------------------------------


class TestMinimalPublicApiUsage:
    """Parse, normalize, and validate a minimal .lmn file using only public API."""

    def test_parse_normalize_validate_minimal_bundle(self) -> None:
        from limnalis.api.parser import LimnalisParser
        from limnalis.api.normalizer import normalize_surface_file

        minimal_lmn = ROOT / "examples" / "minimal_bundle.lmn"
        assert minimal_lmn.exists(), f"Missing fixture: {minimal_lmn}"

        # Parse
        parser = LimnalisParser()
        tree = parser.parse_file(minimal_lmn)
        assert tree is not None

        # Normalize
        result = normalize_surface_file(minimal_lmn, validate_schema=True)
        assert result.canonical_ast is not None
        assert result.canonical_ast.id == "minimal_bundle"

    def test_evaluate_via_public_api(self) -> None:
        from limnalis.api.evaluator import run_bundle, BundleResult
        from limnalis.api.normalizer import normalize_surface_file
        from limnalis.runtime.models import EvaluationEnvironment, SessionConfig, StepConfig

        minimal_lmn = ROOT / "examples" / "minimal_bundle.lmn"
        result = normalize_surface_file(minimal_lmn, validate_schema=True)
        assert result.canonical_ast is not None

        sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
        env = EvaluationEnvironment()
        bundle_result = run_bundle(result.canonical_ast, sessions, env)
        assert isinstance(bundle_result, BundleResult)


# ---------------------------------------------------------------------------
# T6.4 – __version__ exists and matches expected format
# ---------------------------------------------------------------------------


class TestVersionMetadata:
    """Verify limnalis.__version__ and version.get_version_info()."""

    def test_version_exists(self) -> None:
        import limnalis
        assert hasattr(limnalis, "__version__")
        assert isinstance(limnalis.__version__, str)

    def test_version_format(self) -> None:
        import limnalis
        # Should match PEP 440 format like 0.2.2rc1 or 0.2.2
        assert re.match(r"^\d+\.\d+\.\d+", limnalis.__version__), (
            f"Version {limnalis.__version__!r} does not match expected format"
        )

    def test_get_version_info_returns_dict_with_expected_keys(self) -> None:
        from limnalis.version import get_version_info

        info = get_version_info()
        assert isinstance(info, dict)
        expected_keys = {"package", "spec", "schema", "corpus"}
        assert set(info.keys()) == expected_keys, (
            f"get_version_info keys: {set(info.keys())} != expected {expected_keys}"
        )
        for key in expected_keys:
            assert isinstance(info[key], str), f"info[{key!r}] is not a string"

    def test_version_consistency(self) -> None:
        import limnalis
        from limnalis.version import get_version_info

        info = get_version_info()
        assert limnalis.__version__ == info["package"]
