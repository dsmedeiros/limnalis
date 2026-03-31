from __future__ import annotations

import importlib.metadata
from typing import Any

from pydantic import Field

from limnalis.models.base import LimnalisModel
from limnalis.version import SCHEMA_VERSION, SPEC_VERSION


def get_package_version() -> str:
    """Return the installed limnalis package version, or 'unknown' if not installed."""
    try:
        return importlib.metadata.version("limnalis")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class ExchangeManifest(LimnalisModel):
    """Manifest describing contents and versions for an exchange package."""

    format_version: str = "1.0"
    spec_version: str
    schema_version: str
    package_version: str
    corpus_version: str | None = None
    artifact_types: list[str]  # e.g. ["ast", "evaluation_result", "conformance_report"]
    plugin_requirements: list[str] = Field(default_factory=list)
    checksums: dict[str, str] = Field(default_factory=dict)  # filename -> sha256
    created_at: str | None = None  # ISO 8601


class ExchangePackageMetadata(LimnalisModel):
    """Metadata wrapper associating a manifest with its on-disk location."""

    manifest: ExchangeManifest
    root_path: str


class ProjectionResult(LimnalisModel):
    """Result of projecting a Limnalis artifact to another format."""

    target_format: str  # e.g. "linkml"
    source_model: str  # e.g. "ast", "evaluation_result"
    artifact_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    lossy_fields: list[str] = Field(default_factory=list)
