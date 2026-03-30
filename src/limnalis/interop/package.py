from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Literal

from limnalis.interop.types import (
    SCHEMA_VERSION,
    SPEC_VERSION,
    ExchangeManifest,
    ExchangePackageMetadata,
    get_package_version,
)

# Mapping from keyword argument names to subdirectory names
_ARTIFACT_DIRS: dict[str, str] = {
    "source_files": "source",
    "ast_files": "ast",
    "result_files": "results",
    "conformance_files": "conformance",
}

# Mapping from subdirectory names to artifact_types entries
_DIR_TO_ARTIFACT_TYPE: dict[str, str] = {
    "source": "source",
    "ast": "ast",
    "results": "evaluation_result",
    "conformance": "conformance_report",
}


def _is_safe_package_relpath(rel_path: str) -> bool:
    """Return True when rel_path is a normalized in-package relative path."""
    if not rel_path or "\\" in rel_path:
        return False
    p = PurePosixPath(rel_path)
    if p.is_absolute():
        return False
    if any(part in ("", ".", "..") for part in p.parts):
        return False
    return True


def _sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_zip_package(package_path: Path) -> bool:
    """Detect whether a package path points to a zip archive."""
    return package_path.is_file() and zipfile.is_zipfile(package_path)


def create_package(
    output_path: str | Path,
    *,
    source_files: list[str | Path] | None = None,
    ast_files: list[str | Path] | None = None,
    result_files: list[str | Path] | None = None,
    conformance_files: list[str | Path] | None = None,
    plugin_requirements: list[str] | None = None,
    corpus_version: str | None = None,
    output_format: Literal["directory", "zip"] = "directory",
) -> ExchangePackageMetadata:
    """Create an exchange package from provided artifact files.

    Creates a directory or zip with structure:
      manifest.json
      source/      (if source_files provided)
      ast/         (if ast_files provided)
      results/     (if result_files provided)
      conformance/ (if conformance_files provided)

    Generates manifest.json with SHA256 checksums for all included files.
    Returns ExchangePackageMetadata.
    """
    output_path = Path(output_path)
    file_groups: dict[str, list[str | Path] | None] = {
        "source_files": source_files,
        "ast_files": ast_files,
        "result_files": result_files,
        "conformance_files": conformance_files,
    }

    # Determine whether to build in a temp dir (for zip) or directly
    if output_format == "zip":
        tmp_dir_obj = tempfile.TemporaryDirectory()
        build_root = Path(tmp_dir_obj.name) / "package"
        build_root.mkdir()
    else:
        tmp_dir_obj = None
        build_root = output_path
        resolved_output = build_root.resolve()
        for files in file_groups.values():
            if not files:
                continue
            for src in files:
                src_resolved = Path(src).resolve()
                try:
                    src_resolved.relative_to(resolved_output)
                except ValueError:
                    continue
                raise ValueError(
                    "Input files must not be inside output_path when "
                    "output_format='directory'"
                )
        if build_root.exists():
            if build_root.is_dir():
                shutil.rmtree(build_root)
            else:
                build_root.unlink()
        build_root.mkdir(parents=True, exist_ok=True)

    try:
        checksums: dict[str, str] = {}
        artifact_types: list[str] = []

        for key, files in file_groups.items():
            if not files:
                continue
            sub_dir_name = _ARTIFACT_DIRS[key]
            sub_dir = build_root / sub_dir_name
            sub_dir.mkdir(exist_ok=True)
            artifact_types.append(_DIR_TO_ARTIFACT_TYPE[sub_dir_name])
            seen_names: set[str] = set()

            for src in files:
                src_path = Path(src)
                if src_path.name in seen_names:
                    raise ValueError(
                        f"Duplicate basename in {sub_dir_name} artifacts: {src_path.name}"
                    )
                seen_names.add(src_path.name)
                dest = sub_dir / src_path.name
                shutil.copy2(src_path, dest)
                rel = f"{sub_dir_name}/{src_path.name}"
                checksums[rel] = _sha256_file(dest)

        manifest = ExchangeManifest(
            spec_version=SPEC_VERSION,
            schema_version=SCHEMA_VERSION,
            package_version=get_package_version(),
            corpus_version=corpus_version,
            artifact_types=sorted(artifact_types),
            plugin_requirements=plugin_requirements or [],
            checksums=checksums,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        manifest_path = build_root / "manifest.json"
        manifest_data = manifest.model_dump(mode="json")
        manifest_path.write_text(
            json.dumps(manifest_data, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

        if output_format == "zip":
            # Ensure parent directory of output exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Create zip from build_root contents
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in sorted(build_root.rglob("*")):
                    if file.is_file():
                        zf.write(file, file.relative_to(build_root))
            root_str = str(output_path)
        else:
            root_str = str(build_root)

        return ExchangePackageMetadata(manifest=manifest, root_path=root_str)
    finally:
        if tmp_dir_obj is not None:
            tmp_dir_obj.cleanup()


def inspect_package(
    package_path: str | Path,
) -> ExchangePackageMetadata:
    """Read and return metadata from an existing exchange package.

    Handles both directory and zip formats by reading manifest.json from root.
    """
    package_path = Path(package_path)

    if _is_zip_package(package_path):
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                try:
                    manifest_text = zf.read("manifest.json").decode("utf-8")
                except KeyError as exc:
                    raise ValueError("manifest.json not found in package") from exc
        except zipfile.BadZipFile as exc:
            raise ValueError("Package is not a valid zip file") from exc
        root_str = str(package_path)
    else:
        manifest_file = package_path / "manifest.json"
        manifest_text = manifest_file.read_text(encoding="utf-8")
        root_str = str(package_path)

    manifest_data = json.loads(manifest_text)
    manifest = ExchangeManifest.model_validate(manifest_data)
    return ExchangePackageMetadata(manifest=manifest, root_path=root_str)


def validate_package(
    package_path: str | Path,
) -> list[str]:
    """Validate an exchange package.

    Returns a list of validation issues (empty list means valid).
    Checks:
    - manifest.json exists and parses
    - All files listed in checksums exist
    - All checksums match
    - Artifact type directories match manifest.artifact_types
    - Version fields are present
    """
    package_path = Path(package_path)
    issues: list[str] = []
    is_zip = _is_zip_package(package_path)

    # --- Read manifest (single zip open for the entire validation) ---
    if is_zip:
        try:
            zf = zipfile.ZipFile(package_path, "r")
        except zipfile.BadZipFile:
            issues.append("Package is not a valid zip file")
            return issues

        try:
            try:
                manifest_text = zf.read("manifest.json").decode("utf-8")
            except KeyError:
                issues.append("manifest.json not found in package")
                return issues

            # --- Parse manifest ---
            try:
                manifest_data = json.loads(manifest_text)
            except json.JSONDecodeError as e:
                issues.append(f"manifest.json is not valid JSON: {e}")
                return issues

            try:
                manifest = ExchangeManifest.model_validate(manifest_data)
            except Exception as e:
                issues.append(f"manifest.json does not conform to ExchangeManifest: {e}")
                return issues

            # --- Check version fields ---
            if not manifest.spec_version:
                issues.append("spec_version is empty")
            if not manifest.schema_version:
                issues.append("schema_version is empty")
            if not manifest.package_version:
                issues.append("package_version is empty")

            # --- Resolve file listing helper ---
            zip_names = set(zf.namelist())

            def _file_exists(rel: str) -> bool:
                return rel in zip_names

            def _read_bytes(rel: str) -> bytes:
                return zf.read(rel)

            def _list_dir(subdir: str) -> list[str]:
                prefix = subdir + "/"
                return [
                    n[len(prefix):]
                    for n in zip_names
                    if n.startswith(prefix) and n != prefix and "/" not in n[len(prefix):]
                ]

            packaged_files = {
                n for n in zip_names if n != "manifest.json" and not n.endswith("/")
            }

            # --- Check checksums ---
            for rel_path, expected_hash in manifest.checksums.items():
                if not _is_safe_package_relpath(rel_path):
                    issues.append(f"Checksum path escapes package root: {rel_path}")
                    continue
                if not _file_exists(rel_path):
                    issues.append(f"File listed in checksums not found: {rel_path}")
                    continue
                data = _read_bytes(rel_path)
                actual_hash = hashlib.sha256(data).hexdigest()
                if actual_hash != expected_hash:
                    issues.append(
                        f"Checksum mismatch for {rel_path}: "
                        f"expected {expected_hash}, got {actual_hash}"
                    )

            extra_files = sorted(packaged_files - set(manifest.checksums))
            for rel_path in extra_files:
                issues.append(f"File present but not listed in checksums: {rel_path}")

            # --- Check artifact_types vs directories ---
            type_to_dir = {v: k for k, v in _DIR_TO_ARTIFACT_TYPE.items()}
            expected_dirs = {type_to_dir[t] for t in manifest.artifact_types if t in type_to_dir}

            for subdir in ("source", "ast", "results", "conformance"):
                has_content = len(_list_dir(subdir)) > 0
                expected = subdir in expected_dirs
                if has_content and not expected:
                    issues.append(
                        f"Directory '{subdir}' has content but its artifact type "
                        f"is not listed in manifest.artifact_types"
                    )
                if expected and not has_content:
                    issues.append(
                        f"Artifact type for '{subdir}' is listed in manifest.artifact_types "
                        f"but directory has no content"
                    )
        finally:
            zf.close()
    else:
        manifest_file = package_path / "manifest.json"
        if not manifest_file.exists():
            issues.append("manifest.json not found in package")
            return issues
        manifest_text = manifest_file.read_text(encoding="utf-8")

        # --- Parse manifest ---
        try:
            manifest_data = json.loads(manifest_text)
        except json.JSONDecodeError as e:
            issues.append(f"manifest.json is not valid JSON: {e}")
            return issues

        try:
            manifest = ExchangeManifest.model_validate(manifest_data)
        except Exception as e:
            issues.append(f"manifest.json does not conform to ExchangeManifest: {e}")
            return issues

        # --- Check version fields ---
        if not manifest.spec_version:
            issues.append("spec_version is empty")
        if not manifest.schema_version:
            issues.append("schema_version is empty")
        if not manifest.package_version:
            issues.append("package_version is empty")

        # --- Resolve file listing helper ---
        resolved_package = package_path.resolve()

        def _list_dir(subdir: str) -> list[str]:
            d = package_path / subdir
            if not d.is_dir():
                return []
            return [f.name for f in d.iterdir() if f.is_file()]

        packaged_files = {
            str(p.relative_to(package_path)).replace("\\", "/")
            for p in package_path.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        }

        # --- Check checksums ---
        for rel_path, expected_hash in manifest.checksums.items():
            candidate = (resolved_package / rel_path).resolve()
            try:
                candidate.relative_to(resolved_package)
            except ValueError:
                issues.append(f"Checksum path escapes package root: {rel_path}")
                continue

            if not candidate.is_file():
                issues.append(f"File listed in checksums not found: {rel_path}")
                continue
            data = candidate.read_bytes()
            actual_hash = hashlib.sha256(data).hexdigest()
            if actual_hash != expected_hash:
                issues.append(
                    f"Checksum mismatch for {rel_path}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )

        extra_files = sorted(packaged_files - set(manifest.checksums))
        for rel_path in extra_files:
            issues.append(f"File present but not listed in checksums: {rel_path}")

        # --- Check artifact_types vs directories ---
        type_to_dir = {v: k for k, v in _DIR_TO_ARTIFACT_TYPE.items()}
        expected_dirs = {type_to_dir[t] for t in manifest.artifact_types if t in type_to_dir}

        for subdir in ("source", "ast", "results", "conformance"):
            has_content = len(_list_dir(subdir)) > 0
            expected = subdir in expected_dirs
            if has_content and not expected:
                issues.append(
                    f"Directory '{subdir}' has content but its artifact type "
                    f"is not listed in manifest.artifact_types"
                )
            if expected and not has_content:
                issues.append(
                    f"Artifact type for '{subdir}' is listed in manifest.artifact_types "
                    f"but directory has no content"
                )

    return issues


def extract_package(
    package_path: str | Path,
    output_dir: str | Path,
) -> Path:
    """Extract an exchange package to a directory.

    If package is zip, unzip to output_dir.
    If package is directory, copy to output_dir.
    Returns the output directory path.
    """
    package_path = Path(package_path)
    output_dir = Path(output_dir)

    if _is_zip_package(package_path):
        if output_dir.exists():
            resolved_output = output_dir.resolve()
            resolved_package = package_path.resolve()
            package_inside_output = False
            try:
                resolved_package.relative_to(resolved_output)
            except ValueError:
                package_inside_output = False
            else:
                package_inside_output = True
            if package_inside_output:
                raise ValueError("output_dir must not contain package_path when extracting zip")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path, "r") as zf:
            resolved_output = output_dir.resolve()
            for member in zf.namelist():
                member_path = (resolved_output / member).resolve()
                try:
                    member_path.relative_to(resolved_output)
                except ValueError:
                    raise ValueError(f"Path traversal detected in zip member: {member}")
            zf.extractall(output_dir)
    else:
        if package_path.resolve() == output_dir.resolve():
            raise ValueError("output_dir must be different from package_path")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.copytree(package_path, output_dir)

    return output_dir
