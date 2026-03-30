"""Tests addressing red-team review findings (red-team-m6a.md).

Covers:
  H5 - Invalid envelope import (missing fields, wrong artifact_kind, extra fields)
  M4 - Empty package creation
  M5 - envelope_to_dict determinism
  M7 - CLI --version values match constants
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from limnalis.interop import (
    ASTEnvelope,
    ConformanceEnvelope,
    ResultEnvelope,
    SCHEMA_VERSION,
    SPEC_VERSION,
    create_package,
    envelope_to_dict,
    export_ast_from_dict,
    get_package_version,
    import_ast_envelope,
    import_conformance_envelope,
    import_result_envelope,
    inspect_package,
)
from limnalis.cli import main


# ---------------------------------------------------------------------------
# H5. Invalid envelope import tests
# ---------------------------------------------------------------------------


class TestInvalidEnvelopeImport:
    """Negative tests for importing malformed/invalid envelope data."""

    def test_ast_envelope_missing_spec_version(self) -> None:
        """Import an ASTEnvelope dict missing required `spec_version`."""
        raw = {
            # "spec_version" intentionally omitted
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "ast",
            "normalized_ast": {"id": "test"},
        }
        with pytest.raises(ValidationError):
            import_ast_envelope(raw)

    def test_ast_envelope_wrong_artifact_kind(self) -> None:
        """Import a dict with artifact_kind='evaluation_result' as ASTEnvelope."""
        raw = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "evaluation_result",
            "normalized_ast": {"id": "test"},
        }
        with pytest.raises(ValidationError):
            import_ast_envelope(raw)

    def test_result_envelope_missing_evaluation_result(self) -> None:
        """Import a ResultEnvelope dict missing required `evaluation_result`."""
        raw = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "evaluation_result",
            # "evaluation_result" intentionally omitted
        }
        with pytest.raises(ValidationError):
            import_result_envelope(raw)

    def test_conformance_envelope_extra_fields_rejected(self) -> None:
        """Import a ConformanceEnvelope dict with unknown extra fields (extra='forbid')."""
        raw = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "conformance_report",
            "report": {"total": 1, "passed": 1},
            "unknown_extra_field": "should be rejected",
        }
        with pytest.raises(ValidationError):
            import_conformance_envelope(raw)

    def test_ast_envelope_missing_normalized_ast(self) -> None:
        """Import an ASTEnvelope dict missing required `normalized_ast`."""
        raw = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "ast",
            # "normalized_ast" intentionally omitted
        }
        with pytest.raises(ValidationError):
            import_ast_envelope(raw)

    def test_conformance_envelope_missing_report(self) -> None:
        """Import a ConformanceEnvelope dict missing required `report`."""
        raw = {
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "package_version": get_package_version(),
            "artifact_kind": "conformance_report",
            # "report" intentionally omitted
        }
        with pytest.raises(ValidationError):
            import_conformance_envelope(raw)


# ---------------------------------------------------------------------------
# M4. Empty package creation
# ---------------------------------------------------------------------------


class TestEmptyPackageCreation:
    """Verify create_package with no artifact files produces valid package."""

    def test_create_package_with_no_artifacts(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "empty_pkg"
        meta = create_package(pkg_dir, output_format="directory")

        assert meta.manifest.artifact_types == []
        assert (pkg_dir / "manifest.json").is_file()

        # Manifest should be valid JSON with expected version fields
        manifest_data = json.loads(
            (pkg_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest_data["spec_version"] == SPEC_VERSION
        assert manifest_data["schema_version"] == SCHEMA_VERSION

    def test_empty_package_inspect_succeeds(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "empty_pkg_inspect"
        create_package(pkg_dir, output_format="directory")
        meta = inspect_package(pkg_dir)
        assert meta.manifest.artifact_types == []


# ---------------------------------------------------------------------------
# M5. envelope_to_dict determinism
# ---------------------------------------------------------------------------


class TestEnvelopeToDictDeterminism:
    """Verify envelope_to_dict produces deterministic dict key ordering."""

    def test_ast_envelope_dict_key_order_deterministic(self) -> None:
        env_a = ASTEnvelope(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            normalized_ast={"z_key": 1, "a_key": 2, "m_key": 3},
        )
        env_b = ASTEnvelope(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            normalized_ast={"z_key": 1, "a_key": 2, "m_key": 3},
        )
        dict_a = envelope_to_dict(env_a)
        dict_b = envelope_to_dict(env_b)

        # Key ordering must be identical
        assert list(dict_a.keys()) == list(dict_b.keys())
        # Deep equality
        assert dict_a == dict_b

    def test_result_envelope_dict_key_order_deterministic(self) -> None:
        env_a = ResultEnvelope(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            evaluation_result={"status": "pass", "details": ["ok"]},
        )
        env_b = ResultEnvelope(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            evaluation_result={"status": "pass", "details": ["ok"]},
        )
        dict_a = envelope_to_dict(env_a)
        dict_b = envelope_to_dict(env_b)

        assert list(dict_a.keys()) == list(dict_b.keys())
        assert dict_a == dict_b

    def test_conformance_envelope_dict_key_order_deterministic(self) -> None:
        env_a = ConformanceEnvelope(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            report={"total": 5, "passed": 5},
        )
        env_b = ConformanceEnvelope(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            report={"total": 5, "passed": 5},
        )
        dict_a = envelope_to_dict(env_a)
        dict_b = envelope_to_dict(env_b)

        assert list(dict_a.keys()) == list(dict_b.keys())
        assert dict_a == dict_b


# ---------------------------------------------------------------------------
# M7. CLI --version values match constants
# ---------------------------------------------------------------------------


class TestCLIVersionMatchesConstants:
    """Verify --version output values match SPEC_VERSION and SCHEMA_VERSION."""

    def test_version_values_match_constants(self, capsys) -> None:
        code = main(["--version"])
        captured = capsys.readouterr()
        assert code == 0

        payload = json.loads(captured.out)
        assert payload["spec_version"] == SPEC_VERSION
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["package_version"] == get_package_version()
