from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from limnalis.interop import (
    SCHEMA_VERSION,
    SPEC_VERSION,
    ExchangePackageMetadata,
    create_package,
    export_ast,
    export_result,
    extract_package,
    get_package_version,
    inspect_package,
    validate_package,
)

ROOT = Path(__file__).resolve().parents[1]
MINIMAL_BUNDLE = ROOT / "examples" / "minimal_bundle.lmn"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    """Create a sample source file for packaging."""
    p = tmp_path / "sample.lmn"
    p.write_text("# sample source content", encoding="utf-8")
    return p


@pytest.fixture()
def ast_file(tmp_path: Path) -> Path:
    """Create a sample AST JSON file for packaging."""
    p = tmp_path / "sample_ast.json"
    exported = export_ast(MINIMAL_BUNDLE, format="json")
    p.write_text(exported, encoding="utf-8")
    return p


@pytest.fixture()
def result_file(tmp_path: Path) -> Path:
    """Create a sample result JSON file for packaging."""
    p = tmp_path / "sample_result.json"
    exported = export_result({"status": "pass"}, format="json")
    p.write_text(exported, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# create_package
# ---------------------------------------------------------------------------


class TestCreatePackage:
    def test_create_directory_package(
        self, tmp_path: Path, source_file: Path, ast_file: Path
    ) -> None:
        pkg_dir = tmp_path / "pkg_dir"
        meta = create_package(
            pkg_dir, source_files=[source_file], ast_files=[ast_file], format="directory"
        )
        assert isinstance(meta, ExchangePackageMetadata)
        assert (pkg_dir / "manifest.json").is_file()
        assert (pkg_dir / "source" / source_file.name).is_file()
        assert (pkg_dir / "ast" / ast_file.name).is_file()

    def test_create_zip_package(
        self, tmp_path: Path, source_file: Path, ast_file: Path
    ) -> None:
        zip_path = tmp_path / "pkg.zip"
        meta = create_package(
            zip_path, source_files=[source_file], ast_files=[ast_file], format="zip"
        )
        assert isinstance(meta, ExchangePackageMetadata)
        assert zip_path.is_file()

    def test_create_with_source_ast_result(
        self, tmp_path: Path, source_file: Path, ast_file: Path, result_file: Path
    ) -> None:
        pkg_dir = tmp_path / "full_pkg"
        meta = create_package(
            pkg_dir,
            source_files=[source_file],
            ast_files=[ast_file],
            result_files=[result_file],
            format="directory",
        )
        assert "ast" in meta.manifest.artifact_types
        assert "source" in meta.manifest.artifact_types
        assert "evaluation_result" in meta.manifest.artifact_types
        assert (pkg_dir / "results" / result_file.name).is_file()

    def test_manifest_version_metadata(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        pkg_dir = tmp_path / "version_pkg"
        meta = create_package(
            pkg_dir, source_files=[source_file], format="directory"
        )
        assert meta.manifest.spec_version == SPEC_VERSION
        assert meta.manifest.schema_version == SCHEMA_VERSION
        assert meta.manifest.package_version == get_package_version()

    def test_manifest_checksums_are_valid_sha256(
        self, tmp_path: Path, source_file: Path, ast_file: Path
    ) -> None:
        pkg_dir = tmp_path / "checksum_pkg"
        meta = create_package(
            pkg_dir, source_files=[source_file], ast_files=[ast_file], format="directory"
        )
        for rel_path, expected_hash in meta.manifest.checksums.items():
            assert len(expected_hash) == 64, f"SHA256 hex should be 64 chars: {rel_path}"
            actual = hashlib.sha256(
                (pkg_dir / rel_path).read_bytes()
            ).hexdigest()
            assert actual == expected_hash


# ---------------------------------------------------------------------------
# inspect_package
# ---------------------------------------------------------------------------


class TestInspectPackage:
    def test_inspect_directory_package(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        pkg_dir = tmp_path / "inspect_dir"
        create_package(pkg_dir, source_files=[source_file], format="directory")
        meta = inspect_package(pkg_dir)
        assert isinstance(meta, ExchangePackageMetadata)
        assert "source" in meta.manifest.artifact_types

    def test_inspect_zip_package(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        zip_path = tmp_path / "inspect.zip"
        create_package(zip_path, source_files=[source_file], format="zip")
        meta = inspect_package(zip_path)
        assert isinstance(meta, ExchangePackageMetadata)
        assert "source" in meta.manifest.artifact_types


# ---------------------------------------------------------------------------
# validate_package
# ---------------------------------------------------------------------------


class TestValidatePackage:
    def test_valid_directory_package(
        self, tmp_path: Path, source_file: Path, ast_file: Path
    ) -> None:
        pkg_dir = tmp_path / "valid_pkg"
        create_package(
            pkg_dir, source_files=[source_file], ast_files=[ast_file], format="directory"
        )
        issues = validate_package(pkg_dir)
        assert issues == []

    def test_valid_zip_package(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        zip_path = tmp_path / "valid.zip"
        create_package(zip_path, source_files=[source_file], format="zip")
        issues = validate_package(zip_path)
        assert issues == []

    def test_catches_missing_manifest(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "no_manifest"
        pkg_dir.mkdir()
        issues = validate_package(pkg_dir)
        assert any("manifest.json not found" in i for i in issues)

    def test_catches_checksum_mismatch(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        pkg_dir = tmp_path / "bad_checksum_pkg"
        create_package(pkg_dir, source_files=[source_file], format="directory")
        # Tamper with the packaged file to break the checksum
        packaged_file = pkg_dir / "source" / source_file.name
        packaged_file.write_text("tampered content", encoding="utf-8")
        issues = validate_package(pkg_dir)
        assert any("Checksum mismatch" in i for i in issues)

    def test_catches_missing_files(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        pkg_dir = tmp_path / "missing_file_pkg"
        create_package(pkg_dir, source_files=[source_file], format="directory")
        # Delete the packaged file so it no longer exists
        packaged_file = pkg_dir / "source" / source_file.name
        packaged_file.unlink()
        issues = validate_package(pkg_dir)
        assert any("not found" in i for i in issues)


# ---------------------------------------------------------------------------
# extract_package
# ---------------------------------------------------------------------------


class TestExtractPackage:
    def test_extract_from_zip(
        self, tmp_path: Path, source_file: Path, ast_file: Path
    ) -> None:
        zip_path = tmp_path / "extract_test.zip"
        create_package(
            zip_path, source_files=[source_file], ast_files=[ast_file], format="zip"
        )
        extract_dir = tmp_path / "extracted"
        result = extract_package(zip_path, extract_dir)
        assert result == extract_dir
        assert (extract_dir / "manifest.json").is_file()
        assert (extract_dir / "source" / source_file.name).is_file()
        assert (extract_dir / "ast" / ast_file.name).is_file()

    def test_extract_from_directory(
        self, tmp_path: Path, source_file: Path
    ) -> None:
        pkg_dir = tmp_path / "dir_extract_src"
        create_package(pkg_dir, source_files=[source_file], format="directory")
        extract_dir = tmp_path / "dir_extracted"
        result = extract_package(pkg_dir, extract_dir)
        assert result == extract_dir
        assert (extract_dir / "manifest.json").is_file()
        assert (extract_dir / "source" / source_file.name).is_file()


# ---------------------------------------------------------------------------
# Full round-trip: create -> inspect -> validate -> extract
# ---------------------------------------------------------------------------


class TestPackageRoundTrip:
    def test_full_round_trip_directory(
        self, tmp_path: Path, source_file: Path, ast_file: Path, result_file: Path
    ) -> None:
        pkg_dir = tmp_path / "rt_dir"
        create_meta = create_package(
            pkg_dir,
            source_files=[source_file],
            ast_files=[ast_file],
            result_files=[result_file],
            format="directory",
        )

        inspect_meta = inspect_package(pkg_dir)
        assert inspect_meta.manifest.spec_version == create_meta.manifest.spec_version
        assert (
            sorted(inspect_meta.manifest.artifact_types)
            == sorted(create_meta.manifest.artifact_types)
        )

        issues = validate_package(pkg_dir)
        assert issues == []

        extract_dir = tmp_path / "rt_extracted"
        extract_package(pkg_dir, extract_dir)
        assert (extract_dir / "manifest.json").is_file()
        assert (extract_dir / "source" / source_file.name).is_file()
        assert (extract_dir / "ast" / ast_file.name).is_file()
        assert (extract_dir / "results" / result_file.name).is_file()

    def test_full_round_trip_zip(
        self, tmp_path: Path, source_file: Path, ast_file: Path
    ) -> None:
        zip_path = tmp_path / "rt.zip"
        create_meta = create_package(
            zip_path,
            source_files=[source_file],
            ast_files=[ast_file],
            format="zip",
        )

        inspect_meta = inspect_package(zip_path)
        assert inspect_meta.manifest.checksums == create_meta.manifest.checksums

        issues = validate_package(zip_path)
        assert issues == []

        extract_dir = tmp_path / "rt_zip_extracted"
        extract_package(zip_path, extract_dir)
        assert (extract_dir / "manifest.json").is_file()

        # Validate extracted directory too
        issues_extracted = validate_package(extract_dir)
        assert issues_extracted == []
